"""
Reprocesamiento retroactivo v15.0 — AndesAI

v15.0 cambios acumulados respecto a v14.3 (última ronda validada con reproceso):
  - v15.0: integración WeatherNext 2 (WN2) como enriquecimiento opcional S3.
           Para fechas históricas WN2 retorna disponible=False (sin datos BQ).
  - v13.0: FIX-CA-WINDOW — ventana temporal condiciones_actuales ±12h (afecta Suiza).
  - v10.1: CR-10A+CR-10B — calibración ERA5 regional Alpes (precip 72h, viento 7m/s).
  - v7.5:  S1 eliminados triggers meteo; S5 determina EAWS Paso 1.

La Parva (H4): sin IMIS ni WN2 histórico → mejora proviene de cambios en S1 (v7.5)
  y S3 (nuevo prompt WN2 opcional que no altera flujo si disponible=False).

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


def _worker(queue: multiprocessing.Queue, ubicacion: str, fecha_ref: datetime) -> None:
    """Proceso hijo aislado. Crea su propio orquestador y devuelve resultado via queue."""
    try:
        orquestador = OrquestadorAvalancha()
        resultado = orquestador.generar_boletin(
            nombre_ubicacion=ubicacion,
            fecha_referencia=fecha_ref,
        )
        nivel = resultado.get("nivel_eaws_24h", "?")
        guardado = guardar_boletin(resultado)
        queue.put(("ok", nivel, guardado))
    except Exception as exc:
        queue.put(("error", str(exc), {}))


def ya_procesado_v6(cliente: bigquery.Client, ubicacion: str, fecha_str: str) -> bool:
    """Retorna True si ya existe un boletín v15 para esta (ubicacion, fecha)."""
    q = f"""
        SELECT COUNT(*) AS n
        FROM `{GCP_PROJECT}.clima.boletines_riesgo`
        WHERE nombre_ubicacion = @loc
          AND DATE(fecha_emision) = @fecha
          AND STARTS_WITH(version_prompts, 'v15')
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


def ejecutar_replay(dry_run: bool, solo_suiza: bool, solo_snowlab: bool) -> None:
    cliente = bigquery.Client(project=GCP_PROJECT)

    runs = construir_lista_runs(solo_suiza, solo_snowlab)
    total = len(runs)

    print(f"\n{'='*65}")
    print(f"REPROCESAMIENTO RETROACTIVO v15.0 — {total} ejecuciones")
    print(f"Estimado: ~{round(total * 100 / 60)} min ({round(total * 100 / 3600, 1)}h)")
    print(f"Dry-run: {dry_run}")
    print(f"{'='*65}\n")

    ok = 0
    skip = 0
    err = 0
    t0_total = time.time()

    for i, (ubicacion, fecha_str) in enumerate(runs, start=1):
        prefijo = f"[{i:3d}/{total}]"

        if ya_procesado_v6(cliente, ubicacion, fecha_str):
            logger.info(f"{prefijo} SKIP (ya v15) — {ubicacion} {fecha_str}")
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
            target=_worker, args=(queue, ubicacion, fecha_ref)
        )
        proc.start()
        proc.join(timeout=TIMEOUT_POR_RUN_SEGUNDOS)

        dur = round(time.time() - t0, 1)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=15)   # 15s para SIGTERM
            if proc.is_alive():
                proc.kill()         # SIGKILL — no se puede ignorar
                proc.join()
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
    print(f"  Skip: {skip} (ya v15)")
    print(f"  Err:  {err}")
    print(f"{'='*65}")

    if err > 0:
        print(f"\nWARNING: {err} ejecuciones fallaron — revisar logs")

    if not dry_run and ok > 0:
        print("\nPróximo paso — Ronda 10 validación v15.0:")
        print("  python notebooks_validacion/07_validacion_slf_suiza.py --version v15 --imis-gt")
        print("  python notebooks_validacion/08_validacion_snowlab.py --version v15")
        print("\nObjetivos v15.0:")
        print("  H3 QWK:  mantener ≥ +0.049 (no regresar desde v9.0)")
        print("  H4 QWK:  ≥ +0.028 (mantener desde v8.0)")
        print("  H4 MAE:  ≤ 0.828 (mantener desde v8.0)")


def main():
    parser = argparse.ArgumentParser(description="Reprocesamiento retroactivo v15.0")
    parser.add_argument("--dry-run", action="store_true",
                        help="Lista runs sin ejecutar")
    parser.add_argument("--solo-suiza", action="store_true",
                        help="Solo H1/H3 (30 runs Swiss)")
    parser.add_argument("--solo-snowlab", action="store_true",
                        help="Solo H4 (90 runs La Parva)")
    args = parser.parse_args()

    ejecutar_replay(
        dry_run=args.dry_run,
        solo_suiza=args.solo_suiza,
        solo_snowlab=args.solo_snowlab,
    )


if __name__ == "__main__":
    main()
