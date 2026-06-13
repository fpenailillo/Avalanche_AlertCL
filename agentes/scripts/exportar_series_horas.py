"""
Exporta a GCS las series horarias de `clima.pronostico_horas` para que el
frontend (widget "Evolución del riesgo") muestre íconos y temperatura reales
por hora durante las próximas ~72 h.

Genera un único objeto público `series_horas.json` con las 6 zonas chilenas
del PoC. La condición de Google Weather se mapea a los íconos del componente
WeatherIcon del frontend (sun/moon/cloud/cloud-sun/cloud-moon/cloud-rain/
cloud-snow/snowflake/wind).

Uso:
    python agentes/scripts/exportar_series_horas.py
    python agentes/scripts/exportar_series_horas.py --horas 72 --dry-run
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from google.cloud import bigquery, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("exportar_series_horas")

GCP_PROJECT = "climas-chileno"
BUCKET = "avalanche-alertcl-boletines"
OBJETO = "series_horas.json"

# (zona de salida → nombre tal cual en BigQuery). La Parva se representa con su
# Sector Bajo, igual que el boletín consolida los sectores a "La Parva".
ZONAS = [
    ("La Parva", "La Parva Sector Bajo"),
    ("Valle Nevado", "Valle Nevado"),
    ("Portillo", "Portillo"),
    ("Ski Arpa", "Ski Arpa"),
    ("Lagunillas", "Lagunillas"),
    ("Chapa Verde", "Chapa Verde"),
]


def mapear_icono(condicion: str, es_dia, tipo_precip: str) -> str:
    """Traduce condicion_clima de Google Weather a un ícono del frontend."""
    c = (condicion or "").upper()
    dia = bool(es_dia)

    nieve_fuerte = {"SNOW", "HEAVY_SNOW", "SNOWSTORM", "BLIZZARD", "HEAVY_SNOW_SHOWERS"}
    nieve_ligera = {
        "LIGHT_SNOW", "SNOW_SHOWERS", "FLURRIES", "LIGHT_SNOW_SHOWERS",
        "CHANCE_OF_SNOW_SHOWERS", "SCATTERED_SNOW_SHOWERS",
        "RAIN_AND_SNOW", "SLEET", "WINTRY_MIX", "FREEZING_RAIN",
    }
    lluvia = {
        "RAIN", "LIGHT_RAIN", "HEAVY_RAIN", "RAIN_SHOWERS", "LIGHT_RAIN_SHOWERS",
        "HEAVY_RAIN_SHOWERS", "CHANCE_OF_SHOWERS", "SCATTERED_SHOWERS", "DRIZZLE",
        "THUNDERSTORM", "THUNDERSHOWER", "HAIL", "CHANCE_OF_TSTORM",
    }

    if c in nieve_fuerte:
        return "snowflake"
    if c in nieve_ligera:
        return "cloud-snow"
    if c in lluvia:
        return "cloud-rain"
    if c in {"CLOUDY", "MOSTLY_CLOUDY", "OVERCAST"}:
        return "cloud"
    if c == "PARTLY_CLOUDY":
        return "cloud-sun" if dia else "cloud-moon"
    if c in {"CLEAR", "MOSTLY_CLEAR", "SUNNY", "HOT"}:
        return "sun" if dia else "moon"
    if c in {"WINDY", "WIND", "BREEZY"}:
        return "wind"
    if c in {"FOG", "HAZE", "MIST", "SMOKE"}:
        return "cloud"

    # Fallback por tipo de precipitación si la condición es desconocida.
    tp = (tipo_precip or "").upper()
    if tp in {"SNOW", "RAIN_AND_SNOW"}:
        return "cloud-snow"
    if tp == "RAIN":
        return "cloud-rain"
    return "cloud"


def consultar_horas(cliente: bigquery.Client, nombre_bq: str, horas: int, fecha: str = None) -> list:
    """Trae `horas` horas desde el ancla (la última extracción por hora).

    Sin `fecha`: desde CURRENT_TIMESTAMP() (boletín vigente).
    Con `fecha` (YYYY-MM-DD): desde las 00:00 hora Chile de ese día (histórico).
    """
    desde_sql = (
        "TIMESTAMP(@fecha || ' 00:00:00', 'America/Santiago')"
        if fecha
        else "CURRENT_TIMESTAMP()"
    )
    sql = f"""
        SELECT
          hora_inicio,
          temperatura,
          condicion_clima,
          es_dia,
          tipo_precipitacion
        FROM `{GCP_PROJECT}.clima.pronostico_horas`
        WHERE nombre_ubicacion = @ubicacion
          AND hora_inicio >= {desde_sql}
          AND hora_inicio < TIMESTAMP_ADD({desde_sql}, INTERVAL @horas HOUR)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY hora_inicio ORDER BY marca_tiempo_ingestion DESC
        ) = 1
        ORDER BY hora_inicio
    """
    parametros = [
        bigquery.ScalarQueryParameter("ubicacion", "STRING", nombre_bq),
        bigquery.ScalarQueryParameter("horas", "INT64", horas),
    ]
    if fecha:
        parametros.append(bigquery.ScalarQueryParameter("fecha", "STRING", fecha))
    cfg = bigquery.QueryJobConfig(query_parameters=parametros)
    filas = list(cliente.query(sql, job_config=cfg).result())
    return [
        {
            "t": f.hora_inicio.astimezone(timezone.utc).isoformat(),
            "temp": round(f.temperatura) if f.temperatura is not None else None,
            "icono": mapear_icono(f.condicion_clima, f.es_dia, f.tipo_precipitacion),
        }
        for f in filas
        if f.temperatura is not None
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta series horarias a GCS")
    parser.add_argument("--horas", type=int, default=72, help="Horizonte en horas (default 72)")
    parser.add_argument(
        "--fecha",
        help="YYYY-MM-DD: genera series_horas/series_<fecha>.json para un boletín histórico",
    )
    parser.add_argument("--dry-run", action="store_true", help="No sube a GCS")
    args = parser.parse_args()

    cliente_bq = bigquery.Client(project=GCP_PROJECT)
    series = []
    for zona_salida, nombre_bq in ZONAS:
        horas = consultar_horas(cliente_bq, nombre_bq, args.horas, args.fecha)
        logger.info(f"{zona_salida:14s} ({nombre_bq}): {len(horas)} horas")
        if horas:
            series.append({"zona": zona_salida, "horas": horas})

    if not series:
        logger.error("Sin datos horarios — no se exporta")
        return 1

    contenido = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "fuente": "google-weather-hours",
        "series": series,
    }
    if args.fecha:
        contenido["fecha"] = args.fecha

    destino = f"series_horas/series_{args.fecha}.json" if args.fecha else OBJETO

    if args.dry_run:
        print(json.dumps(contenido, ensure_ascii=False, indent=2)[:1200])
        logger.info(f"[dry-run] no se subió a GCS (destino sería {destino})")
        return 0

    bucket = storage.Client(project=GCP_PROJECT).bucket(BUCKET)
    blob = bucket.blob(destino)
    blob.cache_control = "public, max-age=300"
    blob.upload_from_string(
        json.dumps(contenido, ensure_ascii=False, indent=2),
        content_type="application/json",
        timeout=60,
    )
    logger.info(f"Subido gs://{BUCKET}/{destino} ({len(series)} zonas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
