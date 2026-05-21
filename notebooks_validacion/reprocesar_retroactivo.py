"""
Reprocesamiento retroactivo v20.0 — AndesAI

v20.0 cambios respecto a v19.0 (baseline FIX-CR19):
  - v20.0 Fase G: FIX-VAL-FRAMEWORK — cache S1-S4 + --solo-s5 (3.5h → ~4 min).
  - v20.0 Fase C: FIX-LLM-DETER — temperature=0.0, seed=42 en todos los LLM clients.
  - v20.0 Fase A: FIX-HN24-PROMO — HN24 → precip_efectiva en Alpes cuando supera ERA5.
  - v20.0 Fase F: FIX-IMIS-EXT — HS_cm, TA_C, VW_ms, VW_max_ms extraídos de IMIS JSON.
  - v20.0 Fase B: FIX-HN24-SIZE — graduación tamaño D3/D4/D5 por HN24 en Alpes.
  - v20.0 Fase E: FIX-CR7A-REFACTOR — compuerta condicional Andes reemplaza bloqueo
           absoluto CR-7A. Habilita EAWS Paso 1 cuando calma sostenida confirmada.
  - v20.0 Fase H: FIX-WN2-TRIGGERS — alertas WN2 ensemble → ventanas_criticas
           deterministas (NEVADA_WN2_CONFIRMADA, PLACA_VIENTO_WN2, VIENTO_WN2_FUERTE).
           Para fechas históricas WN2 retorna disponible=False (sin efecto).

v19.0 cambios respecto a v18.0 (baseline FIX-CR18):
  - v19.0: FIX-CR19 — nieve_nueva_cm = HN24_cm en condiciones_actuales.

v17.0 cambios respecto a v15.5 (baseline post-revert):
  - v17.0: FIX-CR17A — cap estabilidad base en 'fair' en Andes Chile cuando
           factor_meteorologico es neutro (CICLO_DIURNO_NORMAL/ESTABLE) y
           ventanas_criticas=0. El PINN siempre reporta 'poor' en La Parva
           (terreno potencial), pero sin trigger activo la estabilidad efectiva
           debe ser 'fair' → matriz EAWS ≤ nivel 2. No aplica a Alpes.

La Parva (H4): sin IMIS ni WN2 histórico → mejoras provienen de FIX-CR17A y FIX-CR7A-REFACTOR.

Prerequisito (solo Suiza): ejecutar antes de este script:
    python agentes/datos/backfill/cargar_imis_condiciones_actuales.py

Procesamiento CRONOLÓGICO para que REQ-01 (persistencia temporal) pueda
leer la cadena de predicciones anteriores al evaluar calma sostenida.

Fechas procesadas:
  H1/H3 Suiza : 3 estaciones × 10 fechas = 30 runs
  H4 Snowlab  : 3 sectores   × 30 fechas = 90 runs
  Total       : 120 runs × ~100s ≈ 3.5 horas

Uso:
    python notebooks_validacion/reprocesar_retroactivo.py
    python notebooks_validacion/reprocesar_retroactivo.py --solo-suiza
    python notebooks_validacion/reprocesar_retroactivo.py --solo-snowlab
    python notebooks_validacion/reprocesar_retroactivo.py --dry-run
"""

import argparse
import logging
import multiprocessing
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from google.cloud import bigquery

from agentes.orquestador.agente_principal import OrquestadorAvalancha
from agentes.salidas.almacenador import guardar_boletin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

GCP_PROJECT = "climas-chileno"

# ── Fechas de validación ──────────────────────────────────────────────────────
# v14.0: fechas del DEAPSnow test set (2018-2020), per-estación.
# Reemplaza las fechas 2023-2024 (WeatherAPI) que carecían de datos IMIS.

FECHAS_SUIZA_POR_ESTACION = {
    "Interlaken": [
        "2018-12-07", "2018-12-17", "2018-12-27",
        "2019-01-13", "2019-01-26",
        "2019-02-13", "2019-02-23",
        "2019-03-16",
        "2019-04-02", "2019-04-14",
    ],
    "Matterhorn Zermatt": [
        "2018-12-11", "2018-12-24",
        "2019-01-04", "2019-01-22",
        "2019-02-08", "2019-02-18",
        "2019-03-01", "2019-03-20",
        "2019-04-14",
        "2019-12-03",
    ],
    "St Moritz": [
        "2018-12-06", "2018-12-22",
        "2019-01-02", "2019-01-12",
        "2019-02-02", "2019-02-13",
        "2019-02-27",
        "2019-03-25",
        "2019-04-18",
        "2019-12-21",
    ],
}
# Alias plano para compatibilidad con funciones auxiliares
ESTACIONES_SUIZA = list(FECHAS_SUIZA_POR_ESTACION.keys())

# fecha_inicio de cada boletín Snowlab → fecha de referencia para AndesAI
FECHAS_SNOWLAB = [
    "2024-06-15", "2024-06-21", "2024-06-28",
    "2024-07-05", "2024-07-12", "2024-07-19", "2024-07-26",
    "2024-08-02", "2024-08-09", "2024-08-16", "2024-08-23",
    "2024-08-30", "2024-09-06", "2024-09-13",
    "2025-06-06", "2025-06-14", "2025-06-21", "2025-06-27",
    "2025-07-04", "2025-07-11", "2025-07-18", "2025-07-25",
    "2025-08-01", "2025-08-08", "2025-08-15", "2025-08-22",
    "2025-08-29", "2025-09-05", "2025-09-12", "2025-09-19",
]
TIMEOUT_POR_RUN_SEGUNDOS = 480  # 8 min — proceso hijo; .terminate() lo mata de verdad

SECTORES_LAPARVA = [
    "La Parva Sector Alto",
    "La Parva Sector Medio",
    "La Parva Sector Bajo",
]


def _worker(
    queue: multiprocessing.Queue,
    ubicacion: str,
    fecha_ref: datetime,
    cache_dir: str | None = None,
    solo_s5: bool = False,
    generar_cache: bool = False,
) -> None:
    """Proceso hijo aislado. Crea su propio orquestador y devuelve resultado via queue."""
    try:
        orquestador = OrquestadorAvalancha()
        resultado = orquestador.generar_boletin(
            nombre_ubicacion=ubicacion,
            fecha_referencia=fecha_ref,
            cache_dir=cache_dir,
            solo_s5=solo_s5,
            generar_cache=generar_cache,
        )
        nivel = resultado.get("nivel_eaws_24h", "?")
        guardado = guardar_boletin(resultado)
        queue.put(("ok", nivel, guardado))
    except Exception as exc:
        queue.put(("error", str(exc), {}))


def ya_procesado_v6(cliente: bigquery.Client, ubicacion: str, fecha_str: str) -> bool:
    """Retorna True si ya existe un boletín v22 para esta (ubicacion, fecha)."""
    q = f"""
        SELECT COUNT(*) AS n
        FROM `{GCP_PROJECT}.clima.boletines_riesgo`
        WHERE nombre_ubicacion = @loc
          AND DATE(fecha_emision) = @fecha
          AND STARTS_WITH(version_prompts, 'v22')
    """
    job = cliente.query(
        q,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("loc",   "STRING", ubicacion),
            bigquery.ScalarQueryParameter("fecha",  "DATE",   fecha_str),
        ]),
    )
    return list(job.result())[0]["n"] > 0


def construir_lista_runs(solo_suiza: bool, solo_snowlab: bool) -> list[tuple[str, str]]:
    """
    Construye la lista de (ubicacion, fecha_str) a procesar, ordenada
    cronológicamente para que REQ-01 pueda leer la cadena de predicciones anteriores.
    """
    runs: list[tuple[str, str]] = []

    if not solo_snowlab:
        for est, fechas in FECHAS_SUIZA_POR_ESTACION.items():
            for fecha in fechas:
                runs.append((est, fecha))

    if not solo_suiza:
        for fecha in FECHAS_SNOWLAB:
            for sector in SECTORES_LAPARVA:
                runs.append((sector, fecha))

    # Ordenar cronológicamente (por fecha, luego por ubicacion)
    runs.sort(key=lambda x: (x[1], x[0]))
    return runs


def ejecutar_replay(
    dry_run: bool,
    solo_suiza: bool,
    solo_snowlab: bool,
    cache_dir: str | None = None,
    solo_s5: bool = False,
    generar_cache: bool = False,
) -> None:
    from agentes.validacion.cache_subagentes import existe_cache

    cliente = bigquery.Client(project=GCP_PROJECT)

    runs = construir_lista_runs(solo_suiza, solo_snowlab)
    total = len(runs)

    modo = "solo-S5 (cache)" if solo_s5 else ("generar-cache" if generar_cache else "completo")
    est_seg = 3 if solo_s5 else 100
    print(f"\n{'='*65}")
    print(f"REPROCESAMIENTO RETROACTIVO v20.0 — {total} ejecuciones")
    print(f"Modo: {modo}")
    print(f"Estimado: ~{round(total * est_seg / 60)} min ({round(total * est_seg / 3600, 1)}h)")
    print(f"Dry-run: {dry_run}")
    if cache_dir:
        print(f"Cache dir: {cache_dir}")
    print(f"{'='*65}\n")

    ok = 0
    skip = 0
    err = 0
    t0_total = time.time()

    for i, (ubicacion, fecha_str) in enumerate(runs, start=1):
        prefijo = f"[{i:3d}/{total}]"

        if solo_s5:
            # En modo solo-S5 saltamos si no hay cache (no podemos ejecutar)
            if cache_dir and not existe_cache(cache_dir, ubicacion, fecha_str):
                logger.warning(
                    f"{prefijo} SKIP (sin cache) — {ubicacion} {fecha_str}"
                )
                skip += 1
                continue
        else:
            if ya_procesado_v6(cliente, ubicacion, fecha_str):
                logger.info(f"{prefijo} SKIP (ya v22) — {ubicacion} {fecha_str}")
                skip += 1
                continue

        if dry_run:
            logger.info(f"{prefijo} DRY-RUN — {ubicacion} {fecha_str}")
            ok += 1
            continue

        fecha_ref = datetime.fromisoformat(f"{fecha_str}T12:00:00+00:00")
        logger.info(f"\n{prefijo} INICIANDO — {ubicacion} {fecha_str}")

        t0 = time.time()
        queue: multiprocessing.Queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_worker,
            args=(queue, ubicacion, fecha_ref),
            kwargs={"cache_dir": cache_dir, "solo_s5": solo_s5, "generar_cache": generar_cache},
        )
        proc.start()
        proc.join(timeout=TIMEOUT_POR_RUN_SEGUNDOS)

        dur = round(time.time() - t0, 1)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=15)   # 15s para SIGTERM
            if proc.is_alive():
                proc.kill()         # SIGKILL — no se puede ignorar
                proc.join(timeout=10)  # macOS: proc.join() sin timeout puede colgar
            logger.error(
                f"{prefijo} TIMEOUT ({TIMEOUT_POR_RUN_SEGUNDOS}s) — {ubicacion} {fecha_str} "
                f"(proceso terminado, continuando con siguiente run)"
            )
            err += 1
        else:
            try:
                status, *rest = queue.get_nowait()
            except Exception:
                status, rest = "error", [f"queue vacía (exit_code={proc.exitcode})", {}]

            if status == "ok":
                nivel, guardado = rest
                estado_guardado = (
                    "BQ+GCS" if guardado.get("guardado_bigquery") and guardado.get("guardado_gcs") else
                    "BQ"     if guardado.get("guardado_bigquery") else
                    "GCS"    if guardado.get("guardado_gcs")      else "ERROR"
                )
                logger.info(
                    f"{prefijo} OK — nivel={nivel} dur={dur}s guardado={estado_guardado} "
                    f"({ubicacion} {fecha_str})"
                )
                ok += 1
            else:
                exc_str = rest[0] if rest else "desconocido"
                logger.error(f"{prefijo} ERROR — {ubicacion} {fecha_str} ({dur}s): {exc_str}")
                err += 1

        # Progreso parcial cada 10 ejecuciones
        if i % 10 == 0:
            elapsed = round(time.time() - t0_total)
            restantes = total - i
            eta_s = round(elapsed / i * restantes) if i > 0 else 0
            eta_m = round(eta_s / 60)
            logger.info(
                f"\n--- Progreso: {i}/{total} — "
                f"ok={ok} skip={skip} err={err} — "
                f"elapsed={elapsed}s ETA={eta_m}min ---\n"
            )

    elapsed_total = round(time.time() - t0_total)
    print(f"\n{'='*65}")
    print(f"COMPLETADO en {elapsed_total}s ({round(elapsed_total/60)}min)")
    print(f"  OK:   {ok}")
    print(f"  Skip: {skip} (ya v22)")
    print(f"  Err:  {err}")
    print(f"{'='*65}")

    if err > 0:
        print(f"\nWARNING: {err} ejecuciones fallaron — revisar logs")

    if not dry_run and ok > 0:
        print("\nPróximo paso — Validación v22.0:")
        print("  python notebooks_validacion/07_validacion_slf_suiza.py --version v22 --imis-gt")
        print("  python notebooks_validacion/08_validacion_snowlab.py --version v22")
        print("\nObjetivos v22.0 (FIX-WIND-UNITS + FIX-CR10B-RECAL):")
        print("  H3 QWK Suiza:   ≥ 0.350 (v21: 0.353)")
        print("  H4 QWK La Parva: ≥ 0.150 (v21: 0.220)")
        print("  H4 sesgo:        ≤ +0.400 (v21: +0.345)")


def main():
    parser = argparse.ArgumentParser(description="Reprocesamiento retroactivo v20.0")
    parser.add_argument("--dry-run", action="store_true",
                        help="Lista runs sin ejecutar")
    parser.add_argument("--solo-suiza", action="store_true",
                        help="Solo H1/H3 (30 runs Swiss)")
    parser.add_argument("--solo-snowlab", action="store_true",
                        help="Solo H4 (90 runs La Parva)")
    # FIX-VAL-FRAMEWORK (v20.0): flags para cache S1-S4
    parser.add_argument("--cache-dir", type=str, default=None,
                        help="Directorio local para cache outputs S1-S4. "
                             "Requerido con --solo-s5 y --generar-cache.")
    parser.add_argument("--solo-s5", action="store_true",
                        help="Cargar S1-S4 de --cache-dir y ejecutar solo S5. "
                             "Reduce ~3.5h → ~4 min. Requiere --cache-dir.")
    parser.add_argument("--generar-cache", action="store_true",
                        help="Ejecutar pipeline completo y guardar S1-S4 en --cache-dir "
                             "para uso posterior con --solo-s5. Requiere --cache-dir.")
    args = parser.parse_args()

    if (args.solo_s5 or args.generar_cache) and not args.cache_dir:
        parser.error("--solo-s5 y --generar-cache requieren --cache-dir")

    if args.solo_s5 and args.generar_cache:
        parser.error("--solo-s5 y --generar-cache son mutuamente excluyentes")

    ejecutar_replay(
        dry_run=args.dry_run,
        solo_suiza=args.solo_suiza,
        solo_snowlab=args.solo_snowlab,
        cache_dir=args.cache_dir,
        solo_s5=args.solo_s5,
        generar_cache=args.generar_cache,
    )


if __name__ == "__main__":
    main()
