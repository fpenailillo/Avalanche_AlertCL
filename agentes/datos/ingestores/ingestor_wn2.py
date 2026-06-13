"""
Ingestor diario WeatherNext 2 → BigQuery + GCS

Guarda el pronóstico ensemble completo (ventanas 6h + resumen diario,
horizonte hasta 15 días) para todas las ubicaciones en COORDENADAS_ZONAS.

Tabla destino : climas-chileno.clima.pronostico_wn2
  Partición   : DATE(ingestion_timestamp)
  Clustering  : nombre_ubicacion, nivel, fecha_local

GCS destino   : gs://climas-chileno-datos-clima-bronce/pronostico_wn2/
                  {ubicacion}/{YYYY}/{MM}/{DD}/pronostico.json

Idempotente: borra la partición del día en curso antes de insertar,
  por lo que puede re-ejecutarse sin duplicar datos.

Uso:
    python agentes/datos/ingestores/ingestor_wn2.py
    python agentes/datos/ingestores/ingestor_wn2.py --backfill-days 7
    python agentes/datos/ingestores/ingestor_wn2.py --ubicaciones "La Parva Sector Alto"
    python agentes/datos/ingestores/ingestor_wn2.py --dry-run
"""

import argparse
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

from agentes.datos.constantes_zonas import COORDENADAS_ZONAS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

GCP_PROJECT  = os.environ.get("GCP_PROJECT", "climas-chileno")
DATASET      = "clima"
TABLA        = "pronostico_wn2"
BUCKET       = "climas-chileno-datos-clima-bronce"
WN2_TABLE    = "climas-chileno.weathernext_2.weathernext_2_0_0"
SCHEMA_PATH  = os.path.join(os.path.dirname(__file__), "schema_pronostico_wn2.json")

# Series diarias consolidadas para el frontend (bucket público con CORS,
# mismo bucket que boletin_activo.json — ver gcp_cors.json en la raíz)
BUCKET_SERIES_FRONTEND = os.environ.get("BUCKET_BOLETIN_ACTIVO", "avalanche-alertcl-boletines")
OBJETO_SERIES_FRONTEND = "series_wn2.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalizar(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s


def _cargar_schema() -> list:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return [
            bigquery.SchemaField(
                name=c["name"], field_type=c["type"],
                mode=c.get("mode", "NULLABLE"),
                description=c.get("description", ""),
            )
            for c in json.load(f)
        ]


def _asegurar_tabla(bq: bigquery.Client) -> None:
    tabla_ref = f"{GCP_PROJECT}.{DATASET}.{TABLA}"
    try:
        bq.get_table(tabla_ref)
    except NotFound:
        logger.info(f"Creando tabla {tabla_ref} ...")
        t = bigquery.Table(tabla_ref, schema=_cargar_schema())
        t.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="ingestion_timestamp",
        )
        t.clustering_fields = ["nombre_ubicacion", "nivel", "fecha_local"]
        bq.create_table(t)
        logger.info("Tabla creada.")


def _borrar_particion(bq: bigquery.Client, ingestion_date: str) -> None:
    """Elimina todas las filas del día actual para todas las ubicaciones."""
    sql = f"""
        DELETE FROM `{GCP_PROJECT}.{DATASET}.{TABLA}`
        WHERE DATE(ingestion_timestamp) = @fecha
    """
    try:
        bq.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("fecha", "DATE", ingestion_date),
            ]),
        ).result()
        logger.info(f"Partición {ingestion_date} limpiada.")
    except Exception as exc:
        if "streaming buffer" in str(exc).lower():
            logger.warning(
                f"Partición {ingestion_date} con filas en streaming buffer — "
                "se omite DELETE; reinserción tolerada (QUALIFY ROW_NUMBER downstream)"
            )
        else:
            raise


# ── SQL v6 con horizonte completo (beyond_72h incluido) ───────────────────────

def _sql_wn2() -> str:
    """SQL completamente parametrizado (@lat, @lon, @init_date_start, @init_date_end)."""
    return f"""
WITH
ensemble_raw AS (
  SELECT
    t1.init_time,
    forecast.time                                              AS forecast_time,
    forecast.hours                                             AS forecast_lead_hours,
    ensemble.ensemble_member                                   AS member_id,
    ROUND(ensemble.`2m_temperature` - 273.15, 2)              AS temp_2m_c,
    ROUND(GREATEST(ensemble.`total_precipitation_6hr` * 1000, 0), 3) AS precip_6hr_mm,
    ROUND(ensemble.`mean_sea_level_pressure` / 100, 1)        AS mslp_hpa,
    ensemble.`10m_u_component_of_wind`                        AS u10,
    ensemble.`10m_v_component_of_wind`                        AS v10,
    ensemble.`100m_u_component_of_wind`                       AS u100,
    ensemble.`100m_v_component_of_wind`                       AS v100
  FROM `{WN2_TABLE}` AS t1,
       UNNEST(forecast) AS forecast,
       UNNEST(ensemble) AS ensemble
  WHERE
    ST_CONTAINS(t1.geography_polygon, ST_GEOGPOINT(@lon, @lat))
    AND t1.init_time BETWEEN @init_date_start AND @init_date_end
),
ensemble_members AS (
  SELECT *,
    ROUND(SQRT(POW(u10,2)  + POW(v10,2)),  2)                 AS wind_10m_ms,
    ROUND(SQRT(POW(u100,2) + POW(v100,2)), 2)                 AS wind_100m_ms,
    ROUND((ATAN2(-u10,-v10)*180.0/ACOS(-1.0)+360.0)
      - FLOOR((ATAN2(-u10,-v10)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0, 1) AS wdir_10m_deg,
    ROUND((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)
      - FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0, 1) AS wdir_100m_deg,
    CASE
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 22.5
        OR (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 >= 337.5 THEN 'N'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 67.5  THEN 'NE'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 112.5 THEN 'E'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 157.5 THEN 'SE'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 202.5 THEN 'S'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 247.5 THEN 'SW'
      WHEN (ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)-FLOOR((ATAN2(-u100,-v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0 < 292.5 THEN 'W'
      ELSE 'NW'
    END                                                         AS wdir_100m_cardinal_member,
    temp_2m_c <= 2.0 AND precip_6hr_mm > 0                    AS is_snow_member,
    temp_2m_c > 2.0  AND precip_6hr_mm > 0                    AS is_rain_member,
    temp_2m_c BETWEEN 0.0 AND 2.0 AND precip_6hr_mm > 0       AS is_wet_snow_member,
    temp_2m_c < -2.0 AND precip_6hr_mm > 0                    AS is_dry_snow_member,
    precip_6hr_mm > 5.0                                         AS is_heavy_precip_member,
    SQRT(POW(u100,2)+POW(v100,2)) > 8.0  AND precip_6hr_mm > 0 AS is_wind_slab_member,
    SQRT(POW(u100,2)+POW(v100,2)) > 12.0 AND precip_6hr_mm = 0 AS is_wind_erosion_member,
    CASE EXTRACT(HOUR FROM forecast_time)
      WHEN 6 THEN 'manana' WHEN 12 THEN 'tarde'
      WHEN 18 THEN 'noche' WHEN 0 THEN 'madrugada'
    END                                                         AS ventana,
    CASE EXTRACT(HOUR FROM forecast_time)
      WHEN 6 THEN 1 WHEN 12 THEN 2 WHEN 18 THEN 3 WHEN 0 THEN 4
    END                                                         AS ventana_orden,
    DATE(TIMESTAMP_SUB(forecast_time, INTERVAL 3 HOUR))        AS fecha_local,
    ABS(temp_2m_c - LAG(temp_2m_c) OVER (
      PARTITION BY init_time, member_id ORDER BY forecast_lead_hours
    ))                                                          AS temp_delta_abs
  FROM ensemble_raw
),
ventana_6h AS (
  SELECT
    init_time, fecha_local, ventana, ventana_orden,
    forecast_time, forecast_lead_hours,
    COUNT(member_id)                                            AS n_members,
    ROUND(AVG(temp_2m_c),2)                                    AS temp_mean_c,
    ROUND(APPROX_QUANTILES(temp_2m_c,20)[OFFSET(1)],2)        AS temp_p05_c,
    ROUND(APPROX_QUANTILES(temp_2m_c,20)[OFFSET(10)],2)       AS temp_p50_c,
    ROUND(APPROX_QUANTILES(temp_2m_c,20)[OFFSET(19)],2)       AS temp_p95_c,
    ROUND(STDDEV(temp_2m_c),2)                                 AS temp_std_c,
    ROUND(AVG(temp_delta_abs),2)                               AS temp_delta_mean_c,
    ROUND(AVG(precip_6hr_mm),3)                                AS precip_mean_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm,20)[OFFSET(1)],3)    AS precip_p05_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm,20)[OFFSET(10)],3)   AS precip_p50_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm,20)[OFFSET(19)],3)   AS precip_p95_mm,
    ROUND(AVG(mslp_hpa),1)                                     AS mslp_mean_hpa,
    ROUND(MIN(mslp_hpa),1)                                     AS mslp_min_hpa,
    ROUND(AVG(wind_10m_ms),2)                                  AS wind_10m_mean_ms,
    ROUND(MAX(wind_10m_ms),2)                                  AS wind_10m_max_ms,
    ROUND(APPROX_QUANTILES(wind_10m_ms,20)[OFFSET(19)],2)     AS wind_10m_p95_ms,
    ROUND(AVG(wdir_10m_deg),0)                                 AS wdir_10m_mean_deg,
    ROUND(AVG(wind_100m_ms),2)                                 AS wind_100m_mean_ms,
    ROUND(MAX(wind_100m_ms),2)                                 AS wind_100m_max_ms,
    ROUND(APPROX_QUANTILES(wind_100m_ms,20)[OFFSET(19)],2)    AS wind_100m_p95_ms,
    ROUND(AVG(wdir_100m_deg),0)                                AS wdir_100m_mean_deg,
    APPROX_TOP_COUNT(wdir_100m_cardinal_member,1)[OFFSET(0)].value AS wdir_100m_cardinal,
    ROUND(COUNTIF(is_snow_member)        /COUNT(member_id)*100,1) AS prob_snow_pct,
    ROUND(COUNTIF(is_rain_member)        /COUNT(member_id)*100,1) AS prob_rain_pct,
    ROUND(COUNTIF(is_wet_snow_member)    /COUNT(member_id)*100,1) AS prob_wet_snow_pct,
    ROUND(COUNTIF(is_dry_snow_member)    /COUNT(member_id)*100,1) AS prob_dry_snow_pct,
    ROUND(COUNTIF(is_heavy_precip_member)/COUNT(member_id)*100,1) AS prob_heavy_precip_pct,
    ROUND(COUNTIF(is_wind_slab_member)   /COUNT(member_id)*100,1) AS prob_wind_slab_pct,
    ROUND(COUNTIF(is_wind_erosion_member)/COUNT(member_id)*100,1) AS prob_wind_erosion_pct
  FROM ensemble_members
  GROUP BY init_time, fecha_local, ventana, ventana_orden, forecast_time, forecast_lead_hours
),
ventana_eaws AS (
  SELECT v.*,
    ROUND(CASE WHEN v.temp_mean_c>0 THEN v.precip_p50_mm*5.0*0.1
               WHEN v.temp_mean_c>-2 THEN v.precip_p50_mm*6.7*0.1
               WHEN v.temp_mean_c>-5 THEN v.precip_p50_mm*10.0*0.1
               ELSE v.precip_p50_mm*14.0*0.1 END, 2)   AS est_nieve_6h_cm_p50_corr,
    ROUND(CASE WHEN v.temp_mean_c>0 THEN v.precip_p95_mm*5.0*0.1
               WHEN v.temp_mean_c>-2 THEN v.precip_p95_mm*6.7*0.1
               WHEN v.temp_mean_c>-5 THEN v.precip_p95_mm*10.0*0.1
               ELSE v.precip_p95_mm*14.0*0.1 END, 2)   AS est_nieve_6h_cm_p95_corr,
    CASE WHEN forecast_lead_hours<=24 THEN 'H24'
         WHEN forecast_lead_hours<=48 THEN 'H48'
         WHEN forecast_lead_hours<=72 THEN 'H72'
         ELSE 'beyond_72h' END                          AS eaws_horizon,
    CASE WHEN v.wind_100m_mean_ms>=20 THEN 'temporal'
         WHEN v.wind_100m_mean_ms>=15 THEN 'fuerte'
         WHEN v.wind_100m_mean_ms>=10 THEN 'moderado'
         WHEN v.wind_100m_mean_ms>=5  THEN 'leve'
         ELSE 'calma' END                               AS wind_class_es,
    CASE
      WHEN v.prob_dry_snow_pct>=50 AND v.precip_p50_mm>3 AND v.wind_100m_mean_ms>=8 THEN 'storm_slab'
      WHEN v.prob_dry_snow_pct>=30 AND v.wind_100m_mean_ms>=8 AND v.precip_p50_mm<3 THEN 'wind_slab'
      WHEN v.prob_dry_snow_pct>=50 AND v.precip_p50_mm>3                            THEN 'new_snow'
      WHEN v.prob_wet_snow_pct>=40                                                  THEN 'wet_snow'
      WHEN v.prob_snow_pct>=30 AND v.precip_p50_mm BETWEEN 0.5 AND 3               THEN 'new_snow'
      WHEN v.temp_delta_mean_c>3.0 AND v.prob_snow_pct<20                          THEN 'persistent_weak_layer'
      ELSE 'low_load'
    END                                                  AS probable_avalanche_problem,
    (v.prob_snow_pct>=80 AND v.precip_p95_mm>=5.0)     AS alert_heavy_snow,
    (v.prob_dry_snow_pct>=89 AND v.precip_p50_mm>=2.0 AND v.wind_100m_mean_ms>=8) AS alert_storm_slab,
    (v.prob_wet_snow_pct>=40 AND v.temp_mean_c>-1)     AS alert_wet_snow,
    (v.wind_100m_p95_ms>=15)                            AS alert_wind_strong,
    CASE WHEN v.temp_std_c<1.0 THEN 'alta'
         WHEN v.temp_std_c<2.0 THEN 'media'
         WHEN v.temp_std_c<3.5 THEN 'baja'
         ELSE 'muy_baja' END                            AS confianza_pronostico
  FROM ventana_6h v
),
mejor_corrida AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY fecha_local, ventana ORDER BY init_time DESC
  ) AS rn
  FROM ventana_eaws
),
diario AS (
  SELECT fecha_local,
    ROUND(SUM(precip_p50_mm),2)               AS precip_24h_p50_mm,
    ROUND(SUM(precip_p95_mm),2)               AS precip_24h_p95_mm,
    ROUND(SUM(est_nieve_6h_cm_p50_corr),1)    AS nieve_24h_cm_p50_corr,
    ROUND(SUM(est_nieve_6h_cm_p95_corr),1)    AS nieve_24h_cm_p95_corr,
    ROUND(MIN(temp_p05_c),1)                  AS temp_min_dia_c,
    ROUND(MAX(temp_p95_c),1)                  AS temp_max_dia_c,
    APPROX_TOP_COUNT(probable_avalanche_problem,1)[OFFSET(0)].value AS problema_dominante,
    MAX(CASE WHEN alert_heavy_snow  THEN 1 ELSE 0 END) AS dia_alert_heavy_snow,
    MAX(CASE WHEN alert_storm_slab  THEN 1 ELSE 0 END) AS dia_alert_storm_slab,
    MAX(CASE WHEN alert_wet_snow    THEN 1 ELSE 0 END) AS dia_alert_wet_snow,
    MAX(CASE WHEN alert_wind_strong THEN 1 ELSE 0 END) AS dia_alert_wind_strong,
    CASE MIN(CASE confianza_pronostico
      WHEN 'alta' THEN 4 WHEN 'media' THEN 3 WHEN 'baja' THEN 2 ELSE 1 END)
      WHEN 4 THEN 'alta' WHEN 3 THEN 'media' WHEN 2 THEN 'baja' ELSE 'muy_baja'
    END                                       AS confianza_dia
  FROM mejor_corrida WHERE rn=1 GROUP BY fecha_local
)
SELECT 'ventana' AS nivel, fecha_local, ventana, ventana_orden, eaws_horizon, init_time,
  forecast_lead_hours, n_members, temp_mean_c, temp_p05_c, temp_p50_c, temp_p95_c,
  temp_std_c, temp_delta_mean_c, precip_p50_mm, precip_p95_mm,
  est_nieve_6h_cm_p50_corr, est_nieve_6h_cm_p95_corr, mslp_mean_hpa,
  wind_10m_mean_ms, wind_100m_mean_ms, wind_100m_max_ms, wind_100m_p95_ms,
  wdir_100m_mean_deg, wdir_100m_cardinal, wind_class_es,
  prob_snow_pct, prob_wet_snow_pct, prob_dry_snow_pct, prob_wind_slab_pct,
  probable_avalanche_problem, alert_heavy_snow, alert_storm_slab, alert_wet_snow,
  alert_wind_strong, confianza_pronostico,
  CAST(NULL AS FLOAT64) AS nieve_24h_cm_p50_corr,
  CAST(NULL AS FLOAT64) AS nieve_24h_cm_p95_corr,
  CAST(NULL AS STRING)  AS problema_dominante,
  CAST(NULL AS STRING)  AS confianza_dia
FROM mejor_corrida WHERE rn=1

UNION ALL

SELECT 'diario' AS nivel, fecha_local, '--- TOTAL DÍA ---' AS ventana,
  9 AS ventana_orden, CAST(NULL AS STRING) AS eaws_horizon,
  CAST(NULL AS TIMESTAMP) AS init_time, CAST(NULL AS INT64) AS forecast_lead_hours,
  CAST(NULL AS INT64) AS n_members, CAST(NULL AS FLOAT64) AS temp_mean_c,
  temp_min_dia_c AS temp_p05_c, CAST(NULL AS FLOAT64) AS temp_p50_c,
  temp_max_dia_c AS temp_p95_c, CAST(NULL AS FLOAT64) AS temp_std_c,
  CAST(NULL AS FLOAT64) AS temp_delta_mean_c,
  precip_24h_p50_mm AS precip_p50_mm, precip_24h_p95_mm AS precip_p95_mm,
  CAST(NULL AS FLOAT64) AS est_nieve_6h_cm_p50_corr,
  CAST(NULL AS FLOAT64) AS est_nieve_6h_cm_p95_corr,
  CAST(NULL AS FLOAT64) AS mslp_mean_hpa,
  CAST(NULL AS FLOAT64) AS wind_10m_mean_ms, CAST(NULL AS FLOAT64) AS wind_100m_mean_ms,
  CAST(NULL AS FLOAT64) AS wind_100m_max_ms, CAST(NULL AS FLOAT64) AS wind_100m_p95_ms,
  CAST(NULL AS FLOAT64) AS wdir_100m_mean_deg, CAST(NULL AS STRING) AS wdir_100m_cardinal,
  CAST(NULL AS STRING) AS wind_class_es,
  CAST(NULL AS FLOAT64) AS prob_snow_pct, CAST(NULL AS FLOAT64) AS prob_wet_snow_pct,
  CAST(NULL AS FLOAT64) AS prob_dry_snow_pct, CAST(NULL AS FLOAT64) AS prob_wind_slab_pct,
  problema_dominante AS probable_avalanche_problem,
  CAST(dia_alert_heavy_snow AS BOOL) AS alert_heavy_snow,
  CAST(dia_alert_storm_slab AS BOOL) AS alert_storm_slab,
  CAST(dia_alert_wet_snow   AS BOOL) AS alert_wet_snow,
  CAST(dia_alert_wind_strong AS BOOL) AS alert_wind_strong,
  confianza_dia AS confianza_pronostico,
  nieve_24h_cm_p50_corr, nieve_24h_cm_p95_corr, problema_dominante, confianza_dia
FROM diario

ORDER BY fecha_local, ventana_orden
"""


# ── Ingestor ────────────────────────────────────────────────────────────────────

class IngestorWN2:
    """Ingesta diaria WN2 → BQ + GCS para todas las ubicaciones."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.bq  = bigquery.Client(project=GCP_PROJECT)
        self.gcs = storage.Client(project=GCP_PROJECT)

    def ejecutar(
        self,
        ubicaciones: list[str],
        fecha_inicio: str,
        fecha_fin: str,
        limpiar_particion: bool = True,
    ) -> dict:
        """
        Ingesta WN2 para todas las ubicaciones en el rango de init_times.

        Args:
            ubicaciones:       Lista de nombres exactos (deben estar en COORDENADAS_ZONAS)
            fecha_inicio:      Inicio del rango init_time (YYYY-MM-DD)
            fecha_fin:         Fin del rango init_time (YYYY-MM-DD)
            limpiar_particion: Si True, borra la partición de hoy antes de insertar.
        """
        now_utc = datetime.now(timezone.utc)
        ingestion_ts = now_utc.isoformat()
        ingestion_date = now_utc.strftime("%Y-%m-%d")

        logger.info(f"\n{'='*60}")
        logger.info(f"INGESTOR WN2 — {len(ubicaciones)} ubicaciones")
        logger.info(f"Rango init_time: {fecha_inicio} → {fecha_fin}")
        logger.info(f"Dry-run: {self.dry_run}")
        logger.info(f"{'='*60}\n")

        if not self.dry_run:
            _asegurar_tabla(self.bq)
            if limpiar_particion:
                _borrar_particion(self.bq, ingestion_date)

        stats = {"ok": 0, "sin_datos": 0, "error": 0}
        series_frontend: dict[str, list] = {}

        for nombre in ubicaciones:
            coords = COORDENADAS_ZONAS.get(nombre)
            if coords is None:
                logger.warning(f"[{nombre}] — no encontrada en COORDENADAS_ZONAS, omitiendo")
                stats["error"] += 1
                continue

            lat, lon = coords
            try:
                filas = self._consultar_wn2(lat, lon, fecha_inicio, fecha_fin)
                if not filas:
                    logger.warning(f"[{nombre}] — sin datos WN2 para el rango")
                    stats["sin_datos"] += 1
                    continue

                n_ventanas = sum(1 for r in filas if r.get("nivel") == "ventana")
                n_diario   = sum(1 for r in filas if r.get("nivel") == "diario")
                logger.info(f"[{nombre}] — {n_ventanas} ventanas + {n_diario} días")

                if self.dry_run:
                    stats["ok"] += 1
                    continue

                self._insertar_bq(nombre, ingestion_ts, filas)
                self._guardar_gcs(nombre, ingestion_date, filas)
                series_frontend[nombre] = [
                    r for r in filas if r.get("nivel") == "diario"
                ]
                stats["ok"] += 1

            except Exception as exc:
                logger.error(f"[{nombre}] — ERROR: {exc}")
                stats["error"] += 1

        if not self.dry_run:
            self._exportar_series_frontend(series_frontend, ingestion_ts)

        logger.info(f"\n{'='*60}")
        logger.info(f"COMPLETADO: ok={stats['ok']} sin_datos={stats['sin_datos']} error={stats['error']}")
        logger.info(f"{'='*60}")
        return stats

    @staticmethod
    def construir_contenido_series(series_por_zona: dict, generado: str) -> Optional[dict]:
        """
        Arma el dict de series diarias WN2 para el frontend (zonas chilenas
        base, sin sectores). Retorna None si no hay zonas con datos.
        """
        from agentes.datos.constantes_zonas import ZONAS_ANDES_CHILE

        series = []
        for nombre, diarios in sorted(series_por_zona.items()):
            # Solo zonas base chilenas: los sectores tienen su serie en BQ/bronce
            if nombre not in ZONAS_ANDES_CHILE or " Sector " in nombre:
                continue
            if not diarios:
                continue

            dias = []
            for fila in sorted(diarios, key=lambda r: str(r.get("fecha_local"))):
                viento_ms = fila.get("wind_100m_mean_ms")
                dias.append({
                    "fecha": str(fila.get("fecha_local")),
                    "tmin": round(fila["temp_p05_c"]) if fila.get("temp_p05_c") is not None else None,
                    "tmax": round(fila["temp_p95_c"]) if fila.get("temp_p95_c") is not None else None,
                    "nieve_cm": round(fila["nieve_24h_cm_p50_corr"], 1) if fila.get("nieve_24h_cm_p50_corr") is not None else None,
                    "nieve_cm_p95": round(fila["nieve_24h_cm_p95_corr"], 1) if fila.get("nieve_24h_cm_p95_corr") is not None else None,
                    "viento_kmh": round(viento_ms * 3.6, 1) if viento_ms is not None else None,
                    "viento_dir": fila.get("wdir_100m_cardinal"),
                    "prob_nieve_pct": fila.get("prob_snow_pct"),
                    "problema": fila.get("problema_dominante"),
                    "confianza": fila.get("confianza_dia"),
                })
            series.append({"zona": nombre, "dias": dias})

        if not series:
            return None
        return {"generado": generado, "fuente": "ingestor-wn2", "series": series}

    def subir_series_frontend(self, contenido: dict, rutas: list[str]) -> None:
        """Sube el contenido de series a las rutas indicadas del bucket público."""
        cuerpo = json.dumps(contenido, ensure_ascii=False, default=str, indent=2)
        bucket = self.gcs.bucket(BUCKET_SERIES_FRONTEND)
        for ruta in rutas:
            blob = bucket.blob(ruta)
            blob.cache_control = "public, max-age=300"
            blob.upload_from_string(cuerpo, content_type="application/json", timeout=60)
        logger.info(
            f"Series WN2 frontend: gs://{BUCKET_SERIES_FRONTEND}/{{{', '.join(rutas)}}} "
            f"({len(contenido['series'])} zonas)"
        )

    def _exportar_series_frontend(self, series_por_zona: dict, ingestion_ts: str) -> None:
        """
        Publica las series diarias WN2 en el bucket público del frontend:
        última versión + copia datada (permite ver el pronóstico vigente al
        consultar boletines históricos). Nunca aborta la ingesta.
        """
        try:
            contenido = self.construir_contenido_series(series_por_zona, ingestion_ts)
            if contenido is None:
                logger.warning("Series frontend: sin zonas chilenas con datos — no se exporta")
                return
            self.subir_series_frontend(contenido, [
                OBJETO_SERIES_FRONTEND,
                f"series_wn2/series_{ingestion_ts[:10]}.json",
            ])
        except Exception as exc:
            logger.error(f"Error exportando series frontend (no bloquea la ingesta): {exc}")

    def _consultar_wn2(
        self, lat: float, lon: float, fecha_inicio: str, fecha_fin: str
    ) -> list[dict]:
        sql = _sql_wn2()
        params = [
            bigquery.ScalarQueryParameter("lat",            "FLOAT64",    lat),
            bigquery.ScalarQueryParameter("lon",            "FLOAT64",    lon),
            bigquery.ScalarQueryParameter("init_date_start", "TIMESTAMP", f"{fecha_inicio} 00:00:00 UTC"),
            bigquery.ScalarQueryParameter("init_date_end",   "TIMESTAMP", f"{fecha_fin} 23:59:59 UTC"),
        ]
        rows = list(self.bq.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        ).result())
        return [dict(r) for r in rows]

    def _insertar_bq(self, nombre: str, ingestion_ts: str, filas: list[dict]) -> None:
        tabla_ref = f"{GCP_PROJECT}.{DATASET}.{TABLA}"
        rows_bq = []
        for r in filas:
            row = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()}
            row["nombre_ubicacion"]   = nombre
            row["ingestion_timestamp"] = ingestion_ts
            rows_bq.append(row)

        errores = self.bq.insert_rows_json(tabla_ref, rows_bq)
        if errores:
            raise RuntimeError(f"BQ insert errors: {errores[:3]}")
        logger.info(f"  BQ: {len(rows_bq)} filas insertadas en {tabla_ref}")

    def _guardar_gcs(self, nombre: str, fecha: str, filas: list[dict]) -> None:
        bucket = self.gcs.bucket(BUCKET)
        yyyy, mm, dd = fecha.split("-")
        ruta = f"pronostico_wn2/{_normalizar(nombre)}/{yyyy}/{mm}/{dd}/pronostico.json"

        # Separar ventanas y diario para JSON estructurado
        ventanas = [r for r in filas if r.get("nivel") == "ventana"]
        diarios  = [r for r in filas if r.get("nivel") == "diario"]

        contenido = {
            "nombre_ubicacion": nombre,
            "ingestion_date": fecha,
            "n_ventanas": len(ventanas),
            "n_dias": len(diarios),
            "ventanas": ventanas,
            "diario": diarios,
        }
        blob = bucket.blob(ruta)
        blob.upload_from_string(
            json.dumps(contenido, ensure_ascii=False, default=str, indent=2),
            content_type="application/json",
            timeout=120,
        )
        logger.info(f"  GCS: gs://{BUCKET}/{ruta}")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingestor diario WeatherNext 2 → BQ + GCS"
    )
    parser.add_argument(
        "--backfill-days", type=int, default=0,
        help="Número de días hacia atrás para backfill (0 = solo hoy)",
    )
    parser.add_argument(
        "--fecha-inicio", type=str,
        help="Fecha inicio explícita YYYY-MM-DD (sobreescribe --backfill-days)",
    )
    parser.add_argument(
        "--fecha-fin", type=str,
        help="Fecha fin explícita YYYY-MM-DD (sobreescribe --backfill-days)",
    )
    parser.add_argument(
        "--ubicaciones", nargs="+",
        help="Subset de ubicaciones (default: todas en COORDENADAS_ZONAS)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo consulta y muestra estadísticas sin insertar",
    )
    parser.add_argument(
        "--no-limpiar", action="store_true",
        help="No borrar la partición del día antes de insertar",
    )
    args = parser.parse_args()

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.fecha_inicio and args.fecha_fin:
        fecha_inicio = args.fecha_inicio
        fecha_fin    = args.fecha_fin
    elif args.backfill_days > 0:
        desde = (datetime.now(timezone.utc) - timedelta(days=args.backfill_days))
        fecha_inicio = desde.strftime("%Y-%m-%d")
        fecha_fin    = hoy
    else:
        fecha_inicio = hoy
        fecha_fin    = hoy

    ubicaciones = args.ubicaciones or list(COORDENADAS_ZONAS.keys())

    ingestor = IngestorWN2(dry_run=args.dry_run)
    ingestor.ejecutar(
        ubicaciones=ubicaciones,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        limpiar_particion=not args.no_limpiar,
    )


if __name__ == "__main__":
    main()
