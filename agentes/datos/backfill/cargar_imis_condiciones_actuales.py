"""
Backfill IMIS → condiciones_actuales (v14.0)

Carga datos reales de estaciones IMIS (DEAPSnow RF2) en `condiciones_actuales`
para las 30 fechas de validación seleccionadas del test set 2018-2020.

Fuente: BigQuery `climas-chileno.validacion_avalanchas.slf_meteo_snowpack`
Destino: BigQuery `climas-chileno.clima.condiciones_actuales`

Mapeo IMIS → condiciones_actuales:
  TA (°C)              → temperatura
  VW (m/s) × 3.6      → velocidad_viento (km/h)
  DW (°)               → direccion_viento (N/NE/E/SE/S/SW/W/NW)
  HN24 (cm) / 10      → precipitacion_acumulada (mm SWE proxy)
  RH (%)               → humedad_relativa
  derivado de TA+VW    → sensacion_termica (wind chill)
  derivado de TA+HN24  → condicion_clima

Campos IMIS sin equivalente directo (almacenados en datos_json_crudo):
  Sclass2, pwl_100, base_pwl, HS_meas, HS_mod, SWE, wind_trans24,
  hoar_size, TSS_mod, TSS_meas — disponibles para CR-14+ en futuros prompts.

hora_actual: fecha T18:00:00+00:00 — recuperado por FIX-CA-WINDOW (±12h desde T12:00).

Uso:
    python agentes/datos/backfill/cargar_imis_condiciones_actuales.py
    python agentes/datos/backfill/cargar_imis_condiciones_actuales.py --dry-run
    python agentes/datos/backfill/cargar_imis_condiciones_actuales.py --estacion Interlaken
"""

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone

from google.cloud import bigquery

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get('GCP_PROJECT', 'climas-chileno')
DATASET_VALIDACION = 'validacion_avalanchas'
DATASET_CLIMA = 'clima'
TABLA_ORIGEN = 'slf_meteo_snowpack'
TABLA_DESTINO = 'condiciones_actuales'

# ── Configuración de estaciones ──────────────────────────────────────────────

ESTACIONES = {
    "Interlaken": {
        "sector_id": 4113,
        "latitud": 46.686,
        "longitud": 7.863,
        "zona_horaria": "Europe/Zurich",
        "fechas": [
            "2018-12-07", "2018-12-17", "2018-12-27",
            "2019-01-13", "2019-01-26",
            "2019-02-13", "2019-02-23",
            "2019-03-16",
            "2019-04-02", "2019-04-14",
        ],
    },
    "Matterhorn Zermatt": {
        "sector_id": 2223,
        "latitud": 45.977,
        "longitud": 7.659,
        "zona_horaria": "Europe/Zurich",
        "fechas": [
            "2018-12-11", "2018-12-24",
            "2019-01-04", "2019-01-22",
            "2019-02-08", "2019-02-18",
            "2019-03-01", "2019-03-20",
            "2019-04-14",
            "2019-12-03",
        ],
    },
    "St Moritz": {
        "sector_id": 6113,
        "latitud": 46.491,
        "longitud": 9.836,
        "zona_horaria": "Europe/Zurich",
        "fechas": [
            "2018-12-06", "2018-12-22",
            "2019-01-02", "2019-01-12",
            "2019-02-02", "2019-02-13",
            "2019-02-27",
            "2019-03-25",
            "2019-04-18",
            "2019-12-21",
        ],
    },
}


# ── Conversiones ─────────────────────────────────────────────────────────────

_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _grados_a_compass(grados: float | None) -> str | None:
    if grados is None:
        return None
    idx = round(grados / 22.5) % 16
    return _COMPASS[idx]


def _wind_chill(ta: float | None, vw_kmh: float | None) -> float | None:
    """Wind chill (JAG/TI) en °C. Aplica solo con TA <= 10°C y VW >= 10 km/h."""
    if ta is None or vw_kmh is None:
        return ta
    if ta > 10 or vw_kmh < 10:
        return round(ta, 1)
    wc = (13.12 + 0.6215 * ta
          - 11.37 * vw_kmh ** 0.16
          + 0.3965 * ta * vw_kmh ** 0.16)
    return round(wc, 1)


def _condicion_clima(ta: float | None, hn24: float | None, rh: float | None) -> str:
    """Deriva condicion_clima legible a partir de temperatura, nieve nueva y humedad."""
    if hn24 is not None and hn24 > 5:
        return "Heavy snow" if hn24 > 15 else "Snow"
    if hn24 is not None and hn24 > 0:
        return "Light snow"
    if ta is not None and ta <= 0 and (rh is None or rh > 80):
        return "Overcast"
    if ta is not None and ta <= 5:
        return "Partly cloudy"
    return "Clear"


# ── BigQuery helpers ──────────────────────────────────────────────────────────

def _consultar_imis(
    cliente: bigquery.Client,
    sector_id: int,
    fecha: str,
) -> dict | None:
    """Retorna la fila IMIS para (sector_id, datum=fecha) o None."""
    sql = f"""
        SELECT
            TA, TSS_mod, TSS_meas, RH, VW, DW,
            HN24, HS_meas, HS_mod, SWE,
            wind_trans24, hoar_size, Sclass2, pwl_100, base_pwl,
            dangerLevel, station_code, elevation_station, `set`
        FROM `{GCP_PROJECT}.{DATASET_VALIDACION}.{TABLA_ORIGEN}`
        WHERE sector_id = @sector_id
          AND datum = @fecha
        LIMIT 1
    """
    config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sector_id", "INTEGER", sector_id),
        bigquery.ScalarQueryParameter("fecha",     "DATE",    fecha),
    ])
    filas = list(cliente.query(sql, job_config=config).result())
    if not filas:
        return None
    return dict(filas[0])


def _existe(cliente: bigquery.Client, nombre_ubicacion: str, fecha: str) -> bool:
    """True si ya hay una fila IMIS para (ubicacion, fecha) en condiciones_actuales."""
    sql = f"""
        SELECT COUNT(*) AS n
        FROM `{GCP_PROJECT}.{DATASET_CLIMA}.{TABLA_DESTINO}`
        WHERE nombre_ubicacion = @ubicacion
          AND DATE(hora_actual) = @fecha
          AND JSON_VALUE(datos_json_crudo, '$.fuente') = 'IMIS_DEAPSnow_RF2'
    """
    config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("ubicacion", "STRING", nombre_ubicacion),
        bigquery.ScalarQueryParameter("fecha",     "DATE",   fecha),
    ])
    resultado = list(cliente.query(sql, job_config=config).result())
    return resultado[0]["n"] > 0


def _construir_fila(
    nombre_ubicacion: str,
    latitud: float,
    longitud: float,
    zona_horaria: str,
    fecha: str,
    imis: dict,
) -> dict:
    """Construye la fila para condiciones_actuales a partir de datos IMIS."""
    ta = imis.get("TA")
    vw_ms = imis.get("VW")
    vw_kmh = round(vw_ms * 3.6, 1) if vw_ms is not None else None
    rh = imis.get("RH")
    hn24 = imis.get("HN24")

    # HN24 cm → mm SWE (proxy: densidad nieve fresca ~100 kg/m³ → 10:1)
    precip_mm = round(hn24 / 10.0, 2) if (hn24 is not None and hn24 > 0) else 0.0

    condicion = _condicion_clima(ta, hn24, rh)

    return {
        "nombre_ubicacion":           nombre_ubicacion,
        "latitud":                    latitud,
        "longitud":                   longitud,
        "zona_horaria":               zona_horaria,
        "hora_actual":                f"{fecha}T18:00:00+00:00",
        "temperatura":                round(ta, 2) if ta is not None else None,
        "sensacion_termica":          _wind_chill(ta, vw_kmh),
        "punto_rocio":                None,
        "velocidad_viento":           vw_kmh,
        "direccion_viento":           round(imis.get("DW"), 1) if imis.get("DW") is not None else None,
        "precipitacion_acumulada":    precip_mm,
        "probabilidad_precipitacion": 90.0 if (hn24 is not None and hn24 > 0) else 5.0,
        "probabilidad_tormenta":      5.0,
        "humedad_relativa":           round(rh, 1) if rh is not None else None,
        "presion_aire":               None,
        "cobertura_nubes":            None,
        "condicion_clima":            condicion,
        "descripcion_clima":          condicion,
        "es_dia":                     False,
        "marca_tiempo_ingestion":     datetime.now(timezone.utc).isoformat(),
        "datos_json_crudo":           json.dumps({
            "fuente":          "IMIS_DEAPSnow_RF2",
            "sector_id":       imis.get("sector_id_meta"),  # None, no está en query
            "station_code":    imis.get("station_code"),
            "datum":           fecha,
            # Campos meteorológicos IMIS originales (unidades originales)
            "TA_c":            ta,
            "VW_ms":           vw_ms,
            "DW_deg":          imis.get("DW"),
            "DW_compass":      _grados_a_compass(imis.get("DW")),
            "RH_pct":          rh,
            "HN24_cm":         hn24,
            "HS_meas_cm":      imis.get("HS_meas"),
            "HS_mod_cm":       imis.get("HS_mod"),
            "SWE_kgm2":        imis.get("SWE"),
            "TSS_mod_c":       imis.get("TSS_mod"),
            "TSS_meas_c":      imis.get("TSS_meas"),
            # Campos de estado del manto nival — cruciales para EAWS real
            "Sclass2":         imis.get("Sclass2"),
            "pwl_100":         imis.get("pwl_100"),
            "base_pwl":        imis.get("base_pwl"),
            "wind_trans24":    imis.get("wind_trans24"),
            "hoar_size":       imis.get("hoar_size"),
            # Ground truth (para referencia, no usado por AndesAI)
            "dangerLevel_gt":  imis.get("dangerLevel"),
            "elevation_station_m": imis.get("elevation_station"),
            "split":           imis.get("set"),
        }, ensure_ascii=False, default=str),
    }


# ── Ejecución principal ───────────────────────────────────────────────────────

def ejecutar_backfill(
    dry_run: bool = False,
    estacion_filtro: str | None = None,
) -> None:
    cliente = bigquery.Client(project=GCP_PROJECT)
    tabla_destino = f"{GCP_PROJECT}.{DATASET_CLIMA}.{TABLA_DESTINO}"

    estaciones = (
        {k: v for k, v in ESTACIONES.items() if k == estacion_filtro}
        if estacion_filtro
        else ESTACIONES
    )

    total = sum(len(v["fechas"]) for v in estaciones.values())
    ok = skip = err = 0

    print(f"\n{'='*60}")
    print(f"BACKFILL IMIS → condiciones_actuales  ({total} inserciones)")
    print(f"Fuente : {GCP_PROJECT}.{DATASET_VALIDACION}.{TABLA_ORIGEN}")
    print(f"Destino: {tabla_destino}")
    print(f"Dry-run: {dry_run}")
    print(f"{'='*60}\n")

    for nombre, cfg in estaciones.items():
        sector_id = cfg["sector_id"]
        latitud   = cfg["latitud"]
        longitud  = cfg["longitud"]
        zona      = cfg["zona_horaria"]

        for fecha in cfg["fechas"]:
            etiqueta = f"{nombre[:15]:<15} {fecha}"

            # En dry-run se omite el check de existencia (solo muestra qué se insertaría)
            if not dry_run and _existe(cliente, nombre, fecha):
                logger.info(f"SKIP (ya existe) — {etiqueta}")
                skip += 1
                continue

            imis = _consultar_imis(cliente, sector_id, fecha)
            if imis is None:
                logger.warning(f"SIN DATOS IMIS — {etiqueta} (sector_id={sector_id})")
                err += 1
                continue

            fila = _construir_fila(nombre, latitud, longitud, zona, fecha, imis)
            nivel_gt = imis.get("dangerLevel", "?")
            ta_str = f"{imis.get('TA', '?'):.1f}°C" if imis.get('TA') is not None else "?"
            hn_str = f"HN24={imis.get('HN24', '?'):.1f}cm" if imis.get('HN24') is not None else ""
            sc_str = f"Sclass2={imis.get('Sclass2', '?'):.1f}" if imis.get('Sclass2') is not None else ""

            if dry_run:
                logger.info(
                    f"DRY-RUN — {etiqueta}  "
                    f"TA={ta_str} {hn_str} {sc_str}  GT_nivel={nivel_gt}"
                )
                ok += 1
                continue

            errores = cliente.insert_rows_json(tabla_destino, [fila])
            if errores:
                logger.error(f"ERROR BQ — {etiqueta}: {errores}")
                err += 1
            else:
                logger.info(
                    f"OK — {etiqueta}  "
                    f"TA={ta_str} {hn_str} {sc_str}  GT_nivel={nivel_gt}"
                )
                ok += 1

    print(f"\n{'='*60}")
    print(f"COMPLETADO")
    print(f"  OK:   {ok}")
    print(f"  Skip: {skip} (ya existían)")
    print(f"  Err:  {err}")
    print(f"{'='*60}")

    if not dry_run and ok > 0:
        print("\nPróximo paso — Paso 3: verificar precipitacion_72h con proxy HN24:")
        print("  python agentes/datos/backfill/cargar_imis_condiciones_actuales.py --verificar")
        print("\nLuego lanzar reproceso v14.0:")
        print("  python notebooks_validacion/reprocesar_retroactivo.py --solo-suiza")


def main():
    parser = argparse.ArgumentParser(description="Backfill IMIS DEAPSnow → condiciones_actuales")
    parser.add_argument("--dry-run",   action="store_true", help="Lista inserciones sin ejecutar")
    parser.add_argument("--estacion",  type=str, default=None,
                        help="Filtrar a una estación: 'Interlaken', 'Matterhorn Zermatt', 'St Moritz'")
    parser.add_argument("--verificar", action="store_true",
                        help="Verifica registros ya insertados (no inserta)")
    args = parser.parse_args()

    if args.verificar:
        _verificar_inserciones()
        return

    ejecutar_backfill(dry_run=args.dry_run, estacion_filtro=args.estacion)


def _verificar_inserciones() -> None:
    """Muestra resumen de registros IMIS ya presentes en condiciones_actuales."""
    cliente = bigquery.Client(project=GCP_PROJECT)
    sql = f"""
        SELECT
            nombre_ubicacion,
            COUNT(*) AS n,
            MIN(DATE(hora_actual)) AS fecha_min,
            MAX(DATE(hora_actual)) AS fecha_max,
            AVG(temperatura) AS ta_media,
            AVG(velocidad_viento) AS vw_media,
            AVG(precipitacion_acumulada) AS precip_media
        FROM `{GCP_PROJECT}.{DATASET_CLIMA}.{TABLA_DESTINO}`
        WHERE JSON_VALUE(datos_json_crudo, '$.fuente') = 'IMIS_DEAPSnow_RF2'
        GROUP BY nombre_ubicacion
        ORDER BY nombre_ubicacion
    """
    filas = list(cliente.query(sql).result())
    print("\nRegistros IMIS en condiciones_actuales:")
    print(f"{'Estación':<22} {'N':>4} {'Fecha min':>12} {'Fecha max':>12} "
          f"{'TA media':>10} {'VW media':>10} {'Precip media':>13}")
    print("-" * 90)
    for f in filas:
        print(
            f"{f['nombre_ubicacion']:<22} {f['n']:>4} "
            f"{str(f['fecha_min']):>12} {str(f['fecha_max']):>12} "
            f"{f['ta_media']:>9.1f}°C "
            f"{f['vw_media']:>8.1f}km/h "
            f"{f['precip_media']:>11.2f}mm"
        )


if __name__ == "__main__":
    main()
