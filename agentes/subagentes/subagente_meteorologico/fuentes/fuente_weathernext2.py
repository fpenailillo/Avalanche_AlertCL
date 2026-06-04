"""
FuenteWeatherNext2 — Fuente meteorológica opcional (ensemble 64 miembros).

WeatherNext 2 (DeepMind, GA noviembre 2025): ensemble de 64 miembros,
15 días de horizonte, 6.5% mejor CRPS. Disponible via:
  - BigQuery Analytics Hub (recomendado para producción)
  - Earth Engine (asset no disponible actualmente)

ESTADO: Requiere suscripción manual en Analytics Hub de GCP.
  1. Ir a: console.cloud.google.com/bigquery/analytics-hub
  2. Buscar "WeatherNext 2"
  3. Suscribir dataset al proyecto climas-chileno
  4. El dataset quedará en: `climas-chileno.weathernext_2`
  5. Activar con: USE_WEATHERNEXT2=true (variable de entorno)

CAVEATS CHILE-ESPECÍFICOS (documentados para tesis):
  - Resolución 0.25° (~28km): La Parva y Valle Nevado caen en misma celda
  - Sin snow depth, SWE ni nieve nueva — solo precipitación líquido-equivalente
  - Sesgo cálido sistemático en altitudes de ski (orografía suavizada)
  - Subestimación de precipitación orográfica en ladera windward chilena
  - Subrepresentación de ráfagas en cumbres (señal crítica para wind slab)
  Todo esto se registra con requires_local_correction=True

Mientras no haya acceso → disponible=False, retorna PronosticoMeteorologico con error.
"""

import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

from agentes.datos.constantes_zonas import COORDENADAS_ZONAS
from agentes.subagentes.subagente_meteorologico.fuentes.base import (
    FuenteMeteorologica,
    PronosticoMeteorologico,
)

logger = logging.getLogger(__name__)

def _use_weathernext2() -> bool:
    return os.environ.get("USE_WEATHERNEXT2", "false").lower() == "true"

# Dataset en BigQuery (después de suscripción en Analytics Hub)
_BQ_DATASET = "climas-chileno.weathernext_2"
_BQ_TABLE = f"{_BQ_DATASET}.weathernext_2_0_0"


class FuenteWeatherNext2(FuenteMeteorologica):
    """
    Fuente WeatherNext 2: ensemble 64 miembros via BigQuery Analytics Hub.

    NOTA: Requiere suscripción manual antes de activar.
    Mientras USE_WEATHERNEXT2=false (default), retorna disponible=False.
    """

    @property
    def nombre(self) -> str:
        return "weathernext_2"

    @property
    def disponible(self) -> bool:
        return _use_weathernext2() and self._verificar_acceso_bq()

    def _verificar_acceso_bq(self) -> bool:
        """Verifica que el dataset esté suscrito y accesible."""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project="climas-chileno")
            dataset = client.get_dataset("climas-chileno.weathernext_2")
            return dataset is not None
        except Exception:
            return False

    def obtener_pronostico(
        self,
        zona: str,
        lat: float,
        lon: float,
        horizonte_h: int = 72,
    ) -> PronosticoMeteorologico:
        """
        Obtiene pronóstico determinista de WeatherNext 2 (mediana del ensemble).

        Usa el miembro P50 del ensemble de 64 para el pronóstico principal.
        Para el ensemble completo, usar obtener_ensemble().
        """
        if not self.disponible:
            return PronosticoMeteorologico(
                fuente=self.nombre, zona=zona, horizonte_h=horizonte_h,
                lat=lat, lon=lon,
                fuente_disponible=False,
                error=(
                    "WeatherNext 2 no disponible. "
                    "Requiere suscripción en Analytics Hub y USE_WEATHERNEXT2=true. "
                    "Ver docstring de fuente_weathernext2.py para instrucciones."
                ),
            )

        try:
            ensemble = self._query_ensemble(zona, lat, lon, horizonte_h)
            if not ensemble:
                return PronosticoMeteorologico(
                    fuente=self.nombre, zona=zona, horizonte_h=horizonte_h,
                    lat=lat, lon=lon, fuente_disponible=False,
                    error="Sin datos WN2 para la zona/horizonte solicitado",
                )
            return self._calcular_percentiles(ensemble, zona, lat, lon, horizonte_h)

        except Exception as exc:
            logger.error(f"FuenteWeatherNext2: error para '{zona}' — {exc}")
            return PronosticoMeteorologico(
                fuente=self.nombre, zona=zona, horizonte_h=horizonte_h,
                lat=lat, lon=lon, fuente_disponible=False, error=str(exc),
            )

    def obtener_ensemble(
        self,
        zona: str,
        lat: float,
        lon: float,
        horizonte_h: int = 72,
    ) -> list[PronosticoMeteorologico]:
        """
        Obtiene los 64 miembros del ensemble de WeatherNext 2.

        Returns:
            Lista de PronosticoMeteorologico, uno por miembro del ensemble.
            Lista vacía si no disponible.
        """
        if not self.disponible:
            logger.warning("FuenteWeatherNext2.obtener_ensemble: fuente no disponible")
            return []

        try:
            return self._query_ensemble(zona, lat, lon, horizonte_h)
        except Exception as exc:
            logger.error(f"FuenteWeatherNext2.obtener_ensemble: {exc}")
            return []

    def obtener_ventanas_6h(
        self,
        zona: str,
        lat: float,
        lon: float,
        fecha_objetivo: Optional[str] = None,
        elevacion_m: Optional[int] = None,
    ) -> dict:
        """
        Obtiene pronóstico WeatherNext 2 en 4 ventanas de 6h + resumen diario.

        Usa SQL v7 con mejoras sobre v6:
        - NEW-1: config CTE con @elevacion_m para cálculo cota 0°C
        - FIX-1: mejor_corrida sin filtro eaws_horizon (incluye beyond_72h)
        - FIX-2: media circular sin/cos para dirección de viento (evita sesgo 0°/360°)
        - FIX-3: LAG con tiebreaker forecast_time (estabilidad numérica)
        - FIX-6: snow_type_member mutuamente exclusivo (dry/wet/storm_slab/melt_freeze/rain)
        - NEW-2: lapse_rate variable por MSLP; cota_0c_m dinámica

        Args:
            zona:         Nombre exacto de la ubicación (para logs)
            lat:          Latitud del punto de interés
            lon:          Longitud del punto de interés
            fecha_objetivo: Fecha ISO (YYYY-MM-DD). Default: hoy UTC.
            elevacion_m:  Elevación de referencia en metros para cota 0°C.
                          Si None, se usa promedio min/max de METADATA_ZONAS.

        Returns:
            dict con claves:
              'disponible': bool
              'zona': str
              'fecha_objetivo': str
              'ventanas': list[dict]  — 4 filas (madrugada/manana/tarde/noche)
              'diario': dict          — 1 fila de resumen
            o {'disponible': False, 'error': str} si falla.
        """
        if not self.disponible:
            return {"disponible": False, "error": "WeatherNext 2 no activado (USE_WEATHERNEXT2=false)"}

        if fecha_objetivo is None:
            fecha_objetivo = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if elevacion_m is None:
            from agentes.datos.constantes_zonas import METADATA_ZONAS
            meta = METADATA_ZONAS.get(zona, {})
            emin = meta.get("elevacion_min_m", 2500)
            emax = meta.get("elevacion_max_m", 3500)
            elevacion_m = (emin + emax) // 2

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project="climas-chileno")
            rows = self._query_ventanas_6h(client, lat, lon, fecha_objetivo, elevacion_m, zona=zona)
            return self._formatear_ventanas(rows, zona, fecha_objetivo)

        except Exception as exc:
            logger.error(f"FuenteWeatherNext2.obtener_ventanas_6h: '{zona}' — {exc}")
            return {"disponible": False, "error": str(exc)}

    # ─── Métodos privados ────────────────────────────────────────────────────

    def _query_ventanas_6h(
        self,
        client,
        lat: float,
        lon: float,
        fecha_objetivo: str,
        elevacion_m: int,
        zona: str = "",
    ) -> list:
        """
        Ejecuta SQL v7 parametrizada por lat/lon/fecha/elevacion.

        Mejoras sobre v6:
        - NEW-1: config CTE con @elevacion_m para cálculo cota 0°C
        - FIX-1: mejor_corrida sin filtro eaws_horizon (incluye beyond_72h)
        - FIX-2: media circular sin/cos para dirección de viento
        - FIX-3: LAG con tiebreaker forecast_time
        - FIX-6: snow_type_member mutuamente exclusivo
        - NEW-2: lapse_rate variable por MSLP; cota_0c_m_member dinámica
        """
        from google.cloud import bigquery

        # FIX-BUG017: timezone local según hemisferio.
        # Suiza: lon>0 → Europe/Zurich (UTC+1/+2). Chile: → America/Santiago (UTC-3/-4).
        _tz = "Europe/Zurich" if lon > 0 else "America/Santiago"

        sql = f"""
-- WeatherNext 2 → AndesAI S3 — SQL v7 parametrizado
WITH

-- NEW-1: elevación de referencia para cota 0°C dinámica
config AS (
  SELECT @elevacion_m AS elevacion_m
),

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
  FROM
    `{_BQ_TABLE}` AS t1,
    UNNEST(forecast) AS forecast,
    UNNEST(ensemble) AS ensemble
  WHERE
    ST_CONTAINS(t1.geography_polygon, ST_GEOGPOINT(@lon, @lat))
    AND t1.init_time BETWEEN @init_date_start AND @init_date_end
),

ensemble_members AS (
  SELECT
    r.init_time,
    r.forecast_time,
    r.forecast_lead_hours,
    r.member_id,
    r.temp_2m_c,
    r.precip_6hr_mm,
    r.mslp_hpa,
    ROUND(SQRT(POW(r.u10,  2) + POW(r.v10,  2)), 2)           AS wind_10m_ms,
    ROUND(SQRT(POW(r.u100, 2) + POW(r.v100, 2)), 2)           AS wind_100m_ms,
    -- FIX-2: componentes sin/cos para media circular de dirección de viento
    SIN(ATAN2(-r.u10,  -r.v10))                                AS wdir_10m_sin,
    COS(ATAN2(-r.u10,  -r.v10))                                AS wdir_10m_cos,
    SIN(ATAN2(-r.u100, -r.v100))                               AS wdir_100m_sin,
    COS(ATAN2(-r.u100, -r.v100))                               AS wdir_100m_cos,
    -- Dirección cardinal por miembro (para moda del ensemble)
    CASE
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 22.5
        OR ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) >= 337.5 THEN 'N'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 67.5 THEN 'NE'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 112.5 THEN 'E'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 157.5 THEN 'SE'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 202.5 THEN 'S'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 247.5 THEN 'SW'
      WHEN ROUND(
            (ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)
            - FLOOR((ATAN2(-r.u100,-r.v100)*180.0/ACOS(-1.0)+360.0)/360.0)*360.0
           , 0) < 292.5 THEN 'W'
      ELSE 'NW'
    END                                                         AS wdir_100m_cardinal_member,
    -- FIX-6: tipo de precipitación mutuamente exclusivo
    CASE
      WHEN r.precip_6hr_mm = 0 AND ABS(r.temp_2m_c) <= 2.0    THEN 'melt_freeze'
      WHEN r.precip_6hr_mm = 0                                   THEN 'no_precip'
      WHEN r.temp_2m_c > 2.0                                     THEN 'rain'
      WHEN r.temp_2m_c > 0.0                                     THEN 'wet_snow'
      WHEN SQRT(POW(r.u100,2)+POW(r.v100,2)) > 8.0              THEN 'storm_slab'
      ELSE                                                         'dry_snow'
    END                                                         AS snow_type_member,
    -- NEW-2: tasa de lapso variable por MSLP; cota isoterma 0°C dinámica
    ROUND(
      c.elevacion_m + r.temp_2m_c * (1000.0 / CASE
        WHEN r.mslp_hpa < 990  THEN 7.5   -- tormenta fuerte: gradiente empinado
        WHEN r.mslp_hpa < 1005 THEN 6.5   -- atmosfera moderada
        ELSE 5.5                           -- atmosfera estable: gradiente suave
      END)
    , 0)                                                        AS cota_0c_m_member,
    -- Flags para alertas (complementarios a snow_type_member)
    r.precip_6hr_mm > 5.0                                       AS is_heavy_precip_member,
    SQRT(POW(r.u100,2)+POW(r.v100,2)) > 12.0
      AND r.precip_6hr_mm = 0                                  AS is_wind_erosion_member,
    -- FIX-3: LAG con tiebreaker forecast_time para estabilidad numérica
    ABS(
      r.temp_2m_c - LAG(r.temp_2m_c) OVER (
        PARTITION BY r.init_time, r.member_id
        ORDER BY r.forecast_lead_hours, r.forecast_time
      )
    )                                                           AS temp_delta_abs,
    -- Slot de ventana horaria
    CASE EXTRACT(HOUR FROM r.forecast_time)
      WHEN 6  THEN 'manana'
      WHEN 12 THEN 'tarde'
      WHEN 18 THEN 'noche'
      WHEN 0  THEN 'madrugada'
    END                                                         AS ventana,
    CASE EXTRACT(HOUR FROM r.forecast_time)
      WHEN 6  THEN 1
      WHEN 12 THEN 2
      WHEN 18 THEN 3
      WHEN 0  THEN 4
    END                                                         AS ventana_orden,
    DATE(r.forecast_time, '{_tz}')                              AS fecha_local
  FROM ensemble_raw r
  CROSS JOIN config c
),

ventana_6h AS (
  SELECT
    init_time,
    fecha_local,
    ventana,
    ventana_orden,
    forecast_time,
    forecast_lead_hours,
    COUNT(member_id)                                            AS n_members,
    ROUND(AVG(temp_2m_c), 2)                                   AS temp_mean_c,
    ROUND(APPROX_QUANTILES(temp_2m_c, 20)[OFFSET(1)],  2)     AS temp_p05_c,
    ROUND(APPROX_QUANTILES(temp_2m_c, 20)[OFFSET(10)], 2)     AS temp_p50_c,
    ROUND(APPROX_QUANTILES(temp_2m_c, 20)[OFFSET(19)], 2)     AS temp_p95_c,
    ROUND(STDDEV(temp_2m_c), 2)                                AS temp_std_c,
    ROUND(AVG(temp_delta_abs), 2)                              AS temp_delta_mean_c,
    ROUND(AVG(precip_6hr_mm), 3)                               AS precip_mean_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm, 20)[OFFSET(1)],  3) AS precip_p05_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm, 20)[OFFSET(10)], 3) AS precip_p50_mm,
    ROUND(APPROX_QUANTILES(precip_6hr_mm, 20)[OFFSET(19)], 3) AS precip_p95_mm,
    ROUND(AVG(mslp_hpa), 1)                                    AS mslp_mean_hpa,
    ROUND(MIN(mslp_hpa), 1)                                    AS mslp_min_hpa,
    ROUND(AVG(wind_10m_ms), 2)                                 AS wind_10m_mean_ms,
    ROUND(MAX(wind_10m_ms), 2)                                 AS wind_10m_max_ms,
    ROUND(APPROX_QUANTILES(wind_10m_ms, 20)[OFFSET(19)], 2)   AS wind_10m_p95_ms,
    -- FIX-2: media circular para dirección viento 10m (evita sesgo 0°/360°)
    ROUND(
      (ATAN2(AVG(wdir_10m_sin), AVG(wdir_10m_cos)) * 180.0 / ACOS(-1.0) + 360.0)
      - FLOOR((ATAN2(AVG(wdir_10m_sin), AVG(wdir_10m_cos)) * 180.0 / ACOS(-1.0) + 360.0) / 360.0) * 360.0
    , 0)                                                        AS wdir_10m_mean_deg,
    ROUND(AVG(wind_100m_ms), 2)                                AS wind_100m_mean_ms,
    ROUND(MAX(wind_100m_ms), 2)                                AS wind_100m_max_ms,
    ROUND(APPROX_QUANTILES(wind_100m_ms, 20)[OFFSET(19)], 2)  AS wind_100m_p95_ms,
    -- FIX-2: media circular para dirección viento 100m
    ROUND(
      (ATAN2(AVG(wdir_100m_sin), AVG(wdir_100m_cos)) * 180.0 / ACOS(-1.0) + 360.0)
      - FLOOR((ATAN2(AVG(wdir_100m_sin), AVG(wdir_100m_cos)) * 180.0 / ACOS(-1.0) + 360.0) / 360.0) * 360.0
    , 0)                                                        AS wdir_100m_mean_deg,
    APPROX_TOP_COUNT(wdir_100m_cardinal_member, 1)[OFFSET(0)].value AS wdir_100m_cardinal,
    -- FIX-6: probabilidades por tipo de nieve (mutuamente excluyentes)
    ROUND(COUNTIF(snow_type_member = 'dry_snow')    / COUNT(member_id) * 100, 1) AS prob_dry_snow_pct,
    ROUND(COUNTIF(snow_type_member = 'wet_snow')    / COUNT(member_id) * 100, 1) AS prob_wet_snow_pct,
    ROUND(COUNTIF(snow_type_member = 'storm_slab')  / COUNT(member_id) * 100, 1) AS prob_storm_slab_pct,
    ROUND(COUNTIF(snow_type_member = 'melt_freeze') / COUNT(member_id) * 100, 1) AS prob_melt_freeze_pct,
    ROUND(COUNTIF(snow_type_member = 'rain')        / COUNT(member_id) * 100, 1) AS prob_rain_pct,
    -- prob_snow_pct: suma de todos los tipos de nieve (compatibilidad)
    ROUND(
      COUNTIF(snow_type_member IN ('dry_snow','wet_snow','storm_slab'))
      / COUNT(member_id) * 100
    , 1)                                                        AS prob_snow_pct,
    ROUND(COUNTIF(is_heavy_precip_member) / COUNT(member_id) * 100, 1) AS prob_heavy_precip_pct,
    ROUND(COUNTIF(is_wind_erosion_member) / COUNT(member_id) * 100, 1) AS prob_wind_erosion_pct,
    -- Tipo de nieve dominante
    APPROX_TOP_COUNT(snow_type_member, 1)[OFFSET(0)].value     AS snow_type_dominant,
    -- NEW-2: cota isoterma 0°C con incertidumbre ensemble
    ROUND(APPROX_QUANTILES(cota_0c_m_member, 20)[OFFSET(1)],  0) AS cota_0c_p05_m,
    ROUND(APPROX_QUANTILES(cota_0c_m_member, 20)[OFFSET(10)], 0) AS cota_0c_p50_m,
    ROUND(APPROX_QUANTILES(cota_0c_m_member, 20)[OFFSET(19)], 0) AS cota_0c_p95_m,
    ROUND(STDDEV(cota_0c_m_member), 0)                           AS cota_0c_std_m
  FROM ensemble_members
  GROUP BY
    init_time, fecha_local, ventana, ventana_orden,
    forecast_time, forecast_lead_hours
),

ventana_eaws AS (
  SELECT
    v.*,
    ROUND(
      CASE
        WHEN v.temp_mean_c > 0   THEN v.precip_p50_mm * 5.0
        WHEN v.temp_mean_c > -2  THEN v.precip_p50_mm * 6.7
        WHEN v.temp_mean_c > -5  THEN v.precip_p50_mm * 10.0
        ELSE                          v.precip_p50_mm * 14.0
      END, 1
    )                                                           AS est_nieve_6h_cm_p50_raw,
    ROUND(
      CASE
        WHEN v.temp_mean_c > 0   THEN v.precip_p50_mm * 5.0  * 0.1
        WHEN v.temp_mean_c > -2  THEN v.precip_p50_mm * 6.7  * 0.1
        WHEN v.temp_mean_c > -5  THEN v.precip_p50_mm * 10.0 * 0.1
        ELSE                          v.precip_p50_mm * 14.0 * 0.1
      END, 2
    )                                                           AS est_nieve_6h_cm_p50_corr,
    ROUND(
      CASE
        WHEN v.temp_mean_c > 0   THEN v.precip_p95_mm * 5.0  * 0.1
        WHEN v.temp_mean_c > -2  THEN v.precip_p95_mm * 6.7  * 0.1
        WHEN v.temp_mean_c > -5  THEN v.precip_p95_mm * 10.0 * 0.1
        ELSE                          v.precip_p95_mm * 14.0 * 0.1
      END, 2
    )                                                           AS est_nieve_6h_cm_p95_corr,
    CASE
      WHEN forecast_lead_hours <= 24 THEN 'H24'
      WHEN forecast_lead_hours <= 48 THEN 'H48'
      WHEN forecast_lead_hours <= 72 THEN 'H72'
      ELSE 'beyond_72h'
    END                                                         AS eaws_horizon,
    CASE
      WHEN v.wind_100m_mean_ms >= 20 THEN 'temporal'
      WHEN v.wind_100m_mean_ms >= 15 THEN 'fuerte'
      WHEN v.wind_100m_mean_ms >= 10 THEN 'moderado'
      WHEN v.wind_100m_mean_ms >= 5  THEN 'leve'
      ELSE                                'calma'
    END                                                         AS wind_class_es,
    -- FIX-6: problema EAWS usando tipos mutuamente excluyentes
    CASE
      WHEN v.prob_storm_slab_pct >= 50
        AND v.precip_p50_mm > 2                                THEN 'storm_slab'
      WHEN v.prob_storm_slab_pct >= 30
        AND v.precip_p50_mm < 2                                THEN 'wind_slab'
      WHEN (v.prob_dry_snow_pct + v.prob_storm_slab_pct) >= 50
        AND v.precip_p50_mm > 3                                THEN 'new_snow'
      WHEN v.prob_wet_snow_pct >= 40                           THEN 'wet_snow'
      WHEN (v.prob_dry_snow_pct + v.prob_storm_slab_pct) >= 30
        AND v.precip_p50_mm BETWEEN 0.5 AND 3                 THEN 'new_snow'
      WHEN v.temp_delta_mean_c > 3.0
        AND v.prob_melt_freeze_pct >= 20                       THEN 'persistent_weak_layer'
      ELSE 'low_load'
    END                                                         AS probable_avalanche_problem,
    ((v.prob_dry_snow_pct + v.prob_wet_snow_pct + v.prob_storm_slab_pct) >= 80
      AND v.precip_p95_mm >= 5.0)                              AS alert_heavy_snow,
    -- FIX-6: alert_storm_slab usa prob_storm_slab_pct (tipo exclusivo)
    (v.prob_storm_slab_pct >= 60)                              AS alert_storm_slab,
    (v.prob_wet_snow_pct >= 40 AND v.temp_mean_c > -1)        AS alert_wet_snow,
    (v.wind_100m_p95_ms >= 15)                                 AS alert_wind_strong,
    CASE
      WHEN v.temp_std_c < 1.0 THEN 'alta'
      WHEN v.temp_std_c < 2.0 THEN 'media'
      WHEN v.temp_std_c < 3.5 THEN 'baja'
      ELSE                         'muy_baja'
    END                                                         AS confianza_pronostico
  FROM ventana_6h v
),

-- FIX-1: sin filtro eaws_horizon — incluye ventanas beyond_72h
mejor_corrida AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY fecha_local, ventana
      ORDER BY init_time DESC
    ) AS rn
  FROM ventana_eaws
),

diario AS (
  SELECT
    fecha_local,
    ROUND(SUM(precip_p50_mm), 2)                               AS precip_24h_p50_mm,
    ROUND(SUM(precip_p95_mm), 2)                               AS precip_24h_p95_mm,
    ROUND(SUM(est_nieve_6h_cm_p50_corr), 1)                   AS nieve_24h_cm_p50_corr,
    ROUND(SUM(est_nieve_6h_cm_p95_corr), 1)                   AS nieve_24h_cm_p95_corr,
    ROUND(MIN(temp_p05_c), 1)                                  AS temp_min_dia_c,
    ROUND(MAX(temp_p95_c), 1)                                  AS temp_max_dia_c,
    APPROX_TOP_COUNT(probable_avalanche_problem, 1)[OFFSET(0)].value AS problema_dominante,
    -- NEW-2: cota 0°C diaria
    ROUND(MIN(cota_0c_p05_m), 0)                               AS cota_0c_min_dia_m,
    ROUND(AVG(cota_0c_p50_m), 0)                               AS cota_0c_media_dia_m,
    ROUND(MAX(cota_0c_p95_m), 0)                               AS cota_0c_max_dia_m,
    -- Tipo de nieve dominante del día
    APPROX_TOP_COUNT(snow_type_dominant, 1)[OFFSET(0)].value   AS snow_type_dia,
    MAX(CASE WHEN alert_heavy_snow  THEN 1 ELSE 0 END)         AS dia_alert_heavy_snow,
    MAX(CASE WHEN alert_storm_slab  THEN 1 ELSE 0 END)         AS dia_alert_storm_slab,
    MAX(CASE WHEN alert_wet_snow    THEN 1 ELSE 0 END)         AS dia_alert_wet_snow,
    MAX(CASE WHEN alert_wind_strong THEN 1 ELSE 0 END)         AS dia_alert_wind_strong,
    CASE MIN(CASE confianza_pronostico
      WHEN 'alta'     THEN 4
      WHEN 'media'    THEN 3
      WHEN 'baja'     THEN 2
      ELSE                 1 END)
      WHEN 4 THEN 'alta'
      WHEN 3 THEN 'media'
      WHEN 2 THEN 'baja'
      ELSE        'muy_baja'
    END                                                         AS confianza_dia
  FROM mejor_corrida
  WHERE rn = 1
  GROUP BY fecha_local
),

-- FIX-WN2-3D: acumulado 3 días (t-2, t-1, t) con mejor init por ventana
-- Captura tormentas que ocurrieron antes del día del boletín (placas de tormenta persistentes)
diario_3d AS (
  SELECT
    ROUND(SUM(est_nieve_6h_cm_p50_corr), 1) AS nieve_3d_cm_p50_corr,
    ROUND(SUM(est_nieve_6h_cm_p95_corr), 1) AS nieve_3d_cm_p95_corr
  FROM mejor_corrida
  WHERE rn = 1
    AND fecha_local BETWEEN DATE_SUB(@fecha_obj, INTERVAL 2 DAY) AND @fecha_obj
)

-- OUTPUT A: ventanas 6h
SELECT
  'ventana'                          AS nivel,
  fecha_local,
  ventana,
  ventana_orden,
  eaws_horizon,
  init_time,
  forecast_lead_hours,
  n_members,
  temp_mean_c,
  temp_p05_c,
  temp_p50_c,
  temp_p95_c,
  temp_std_c,
  temp_delta_mean_c,
  precip_p50_mm,
  precip_p95_mm,
  est_nieve_6h_cm_p50_raw,
  est_nieve_6h_cm_p50_corr,
  est_nieve_6h_cm_p95_corr,
  mslp_mean_hpa,
  wind_10m_mean_ms,
  wind_100m_mean_ms,
  wind_100m_max_ms,
  wind_100m_p95_ms,
  wdir_100m_mean_deg,
  wdir_100m_cardinal,
  wind_class_es,
  prob_snow_pct,
  prob_wet_snow_pct,
  prob_dry_snow_pct,
  prob_storm_slab_pct,
  prob_melt_freeze_pct,
  prob_rain_pct,
  snow_type_dominant,
  cota_0c_p05_m,
  cota_0c_p50_m,
  cota_0c_p95_m,
  cota_0c_std_m,
  probable_avalanche_problem,
  alert_heavy_snow,
  alert_storm_slab,
  alert_wet_snow,
  alert_wind_strong,
  confianza_pronostico,
  CAST(NULL AS FLOAT64)              AS nieve_24h_cm_p50_corr,
  CAST(NULL AS FLOAT64)              AS nieve_24h_cm_p95_corr,
  CAST(NULL AS STRING)               AS problema_dominante,
  CAST(NULL AS FLOAT64)              AS cota_0c_min_dia_m,
  CAST(NULL AS FLOAT64)              AS cota_0c_media_dia_m,
  CAST(NULL AS FLOAT64)              AS cota_0c_max_dia_m,
  CAST(NULL AS STRING)               AS snow_type_dia,
  CAST(NULL AS STRING)               AS confianza_dia,
  CAST(NULL AS FLOAT64)              AS nieve_3d_cm_p50_corr,
  CAST(NULL AS FLOAT64)              AS nieve_3d_cm_p95_corr

FROM mejor_corrida
WHERE rn = 1

UNION ALL

-- OUTPUT B: resumen diario
SELECT
  'diario'                           AS nivel,
  fecha_local,
  '--- TOTAL DÍA ---'                AS ventana,
  9                                  AS ventana_orden,
  CAST(NULL AS STRING)               AS eaws_horizon,
  CAST(NULL AS TIMESTAMP)            AS init_time,
  CAST(NULL AS INT64)                AS forecast_lead_hours,
  CAST(NULL AS INT64)                AS n_members,
  CAST(NULL AS FLOAT64)              AS temp_mean_c,
  temp_min_dia_c                     AS temp_p05_c,
  CAST(NULL AS FLOAT64)              AS temp_p50_c,
  temp_max_dia_c                     AS temp_p95_c,
  CAST(NULL AS FLOAT64)              AS temp_std_c,
  CAST(NULL AS FLOAT64)              AS temp_delta_mean_c,
  precip_24h_p50_mm                  AS precip_p50_mm,
  precip_24h_p95_mm                  AS precip_p95_mm,
  CAST(NULL AS FLOAT64)              AS est_nieve_6h_cm_p50_raw,
  nieve_24h_cm_p50_corr              AS est_nieve_6h_cm_p50_corr,
  nieve_24h_cm_p95_corr              AS est_nieve_6h_cm_p95_corr,
  CAST(NULL AS FLOAT64)              AS mslp_mean_hpa,
  CAST(NULL AS FLOAT64)              AS wind_10m_mean_ms,
  CAST(NULL AS FLOAT64)              AS wind_100m_mean_ms,
  CAST(NULL AS FLOAT64)              AS wind_100m_max_ms,
  CAST(NULL AS FLOAT64)              AS wind_100m_p95_ms,
  CAST(NULL AS FLOAT64)              AS wdir_100m_mean_deg,
  CAST(NULL AS STRING)               AS wdir_100m_cardinal,
  CAST(NULL AS STRING)               AS wind_class_es,
  CAST(NULL AS FLOAT64)              AS prob_snow_pct,
  CAST(NULL AS FLOAT64)              AS prob_wet_snow_pct,
  CAST(NULL AS FLOAT64)              AS prob_dry_snow_pct,
  CAST(NULL AS FLOAT64)              AS prob_storm_slab_pct,
  CAST(NULL AS FLOAT64)              AS prob_melt_freeze_pct,
  CAST(NULL AS FLOAT64)              AS prob_rain_pct,
  CAST(NULL AS STRING)               AS snow_type_dominant,
  CAST(NULL AS FLOAT64)              AS cota_0c_p05_m,
  CAST(NULL AS FLOAT64)              AS cota_0c_p50_m,
  CAST(NULL AS FLOAT64)              AS cota_0c_p95_m,
  CAST(NULL AS FLOAT64)              AS cota_0c_std_m,
  problema_dominante                 AS probable_avalanche_problem,
  CAST(dia_alert_heavy_snow AS BOOL) AS alert_heavy_snow,
  CAST(dia_alert_storm_slab AS BOOL) AS alert_storm_slab,
  CAST(dia_alert_wet_snow   AS BOOL) AS alert_wet_snow,
  CAST(dia_alert_wind_strong AS BOOL) AS alert_wind_strong,
  confianza_dia                      AS confianza_pronostico,
  nieve_24h_cm_p50_corr,
  nieve_24h_cm_p95_corr,
  problema_dominante,
  cota_0c_min_dia_m,
  cota_0c_media_dia_m,
  cota_0c_max_dia_m,
  snow_type_dia,
  confianza_dia,
  diario_3d.nieve_3d_cm_p50_corr,
  diario_3d.nieve_3d_cm_p95_corr

FROM diario CROSS JOIN diario_3d

ORDER BY fecha_local, ventana_orden
        """

        from datetime import datetime as _dt, timedelta as _td
        _fecha_dt = _dt.strptime(fecha_objetivo, "%Y-%m-%d")
        # FIX-WN2-3D: extender ventana de init 5 días atrás para capturar runs que
        # pronosticaron la tormenta 1-3 días antes del boletín (placas persistentes)
        init_date_start = f"{(_fecha_dt - _td(days=5)).strftime('%Y-%m-%d')} 00:00:00 UTC"
        init_date_end = f"{fecha_objetivo} 23:59:59 UTC"

        params = [
            bigquery.ScalarQueryParameter("lon",             "FLOAT64",   lon),
            bigquery.ScalarQueryParameter("lat",             "FLOAT64",   lat),
            bigquery.ScalarQueryParameter("elevacion_m",     "INT64",     elevacion_m),
            bigquery.ScalarQueryParameter("init_date_start", "TIMESTAMP", init_date_start),
            bigquery.ScalarQueryParameter("init_date_end",   "TIMESTAMP", init_date_end),
            bigquery.ScalarQueryParameter("fecha_obj",       "DATE",      fecha_objetivo),
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        return list(client.query(sql, job_config=job_config).result())

    def _formatear_ventanas(
        self,
        rows: list,
        zona: str,
        fecha_objetivo: str,
    ) -> dict:
        """Convierte las filas BQ (SQL v7) en el dict estructurado que expone la tool."""
        ventanas = []
        diario = {}
        _diario_fallback = {}   # FIX-WN2-DIARIO: primer día disponible si fecha_obj sin datos

        for row in rows:
            r = dict(row)
            if r["nivel"] == "ventana":
                ventanas.append({
                    "ventana": r["ventana"],
                    "fecha_local": str(r["fecha_local"]),
                    "eaws_horizon": r["eaws_horizon"],
                    # Temperatura
                    "temp_p05_c": r["temp_p05_c"],
                    "temp_p50_c": r["temp_p50_c"],
                    "temp_p95_c": r["temp_p95_c"],
                    "temp_std_c": r["temp_std_c"],
                    # Precipitación
                    "precip_p50_mm": r["precip_p50_mm"],
                    "precip_p95_mm": r["precip_p95_mm"],
                    "est_nieve_6h_cm_p50_corr": r["est_nieve_6h_cm_p50_corr"],
                    "est_nieve_6h_cm_p95_corr": r["est_nieve_6h_cm_p95_corr"],
                    # Viento
                    "wind_100m_mean_ms": r["wind_100m_mean_ms"],
                    "wind_100m_p95_ms": r["wind_100m_p95_ms"],
                    "wdir_100m_cardinal": r["wdir_100m_cardinal"],
                    "wind_class_es": r["wind_class_es"],
                    # FIX-6: probabilidades de tipo de nieve (mutuamente excluyentes)
                    "prob_snow_pct": r["prob_snow_pct"],       # suma todos los tipos de nieve
                    "prob_dry_snow_pct": r["prob_dry_snow_pct"],
                    "prob_wet_snow_pct": r["prob_wet_snow_pct"],
                    "prob_storm_slab_pct": r["prob_storm_slab_pct"],
                    "prob_melt_freeze_pct": r["prob_melt_freeze_pct"],
                    "prob_rain_pct": r["prob_rain_pct"],
                    "snow_type_dominant": r["snow_type_dominant"],
                    # NEW-2: cota isoterma 0°C con incertidumbre ensemble
                    "cota_0c_p05_m": r["cota_0c_p05_m"],
                    "cota_0c_p50_m": r["cota_0c_p50_m"],
                    "cota_0c_p95_m": r["cota_0c_p95_m"],
                    "cota_0c_std_m": r["cota_0c_std_m"],
                    # Problema EAWS y alertas
                    "probable_avalanche_problem": r["probable_avalanche_problem"],
                    "alerts": {
                        "heavy_snow": bool(r["alert_heavy_snow"]),
                        "storm_slab": bool(r["alert_storm_slab"]),
                        "wet_snow": bool(r["alert_wet_snow"]),
                        "wind_strong": bool(r["alert_wind_strong"]),
                    },
                    "confianza": r["confianza_pronostico"],
                })
            elif r["nivel"] == "diario":
                # FIX-WN2-DIARIO (v25.10): solo usar el resumen del día del boletín
                # (fecha_objetivo) como nieve_nueva_cm_wn2. El loop SQL llega en orden
                # fecha_local ASC; sin este filtro, el último día (p. ej. una tormenta
                # 8 días adelante) sobreescribía el dict y causaba nieve_wn2=100 cm
                # para días tranquilos, inflando el nivel EAWS a 4-5 (FP severo).
                _d = {
                    "fecha_local": str(r["fecha_local"]),
                    # Precipitación y nieve diaria
                    "precip_24h_p50_mm": r["precip_p50_mm"],
                    "precip_24h_p95_mm": r["precip_p95_mm"],
                    "nieve_24h_cm_p50_corr": r["nieve_24h_cm_p50_corr"],
                    "nieve_24h_cm_p95_corr": r["nieve_24h_cm_p95_corr"],
                    # Temperatura diaria
                    "temp_min_dia_c": r["temp_p05_c"],
                    "temp_max_dia_c": r["temp_p95_c"],
                    # NEW-2: cota 0°C diaria
                    "cota_0c_min_dia_m": r["cota_0c_min_dia_m"],
                    "cota_0c_media_dia_m": r["cota_0c_media_dia_m"],
                    "cota_0c_max_dia_m": r["cota_0c_max_dia_m"],
                    # Tipo de nieve y problema dominante
                    "snow_type_dia": r["snow_type_dia"],
                    "problema_dominante": r["problema_dominante"],
                    "confianza_dia": r["confianza_dia"],
                    "nieve_3d_cm_p95_corr": r.get("nieve_3d_cm_p95_corr"),
                    "nieve_3d_cm_p50_corr": r.get("nieve_3d_cm_p50_corr"),
                    "alerts_dia": {
                        "heavy_snow": bool(r["alert_heavy_snow"]),
                        "storm_slab": bool(r["alert_storm_slab"]),
                        "wet_snow": bool(r["alert_wet_snow"]),
                        "wind_strong": bool(r["alert_wind_strong"]),
                    },
                }
                if str(r["fecha_local"]) == fecha_objetivo:
                    diario = _d
                elif not _diario_fallback:
                    _diario_fallback = _d  # primer día disponible como respaldo

        # Si fecha_objetivo no tenía datos de pronóstico, usar el más próximo disponible
        if not diario and _diario_fallback:
            diario = _diario_fallback
            logger.warning(
                f"FuenteWeatherNext2._formatear_ventanas: '{zona}' — "
                f"sin datos diario para {fecha_objetivo}, usando fallback "
                f"fecha={diario.get('fecha_local')}"
            )

        if not ventanas and not diario:
            return {"disponible": False, "error": f"Sin datos WN2 para fecha={fecha_objetivo}"}

        logger.info(
            f"FuenteWeatherNext2.obtener_ventanas_6h: '{zona}' fecha={fecha_objetivo} "
            f"— {len(ventanas)} ventanas"
        )
        return {
            "disponible": True,
            "zona": zona,
            "fecha_objetivo": fecha_objetivo,
            "ventanas": ventanas,
            "diario": diario,
        }

    def _query_ensemble(
        self,
        zona: str,
        lat: float,
        lon: float,
        horizonte_h: int,
    ) -> list[PronosticoMeteorologico]:
        """
        Query BigQuery para obtener los 64 miembros del ensemble (schema anidado v2).

        Reescrito para el schema real de weathernext_2_0_0 (arrays anidados).
        Mantiene la API existente que usa obtener_pronostico() / obtener_ensemble().
        """
        from google.cloud import bigquery

        client = bigquery.Client(project="climas-chileno")

        sql = f"""
        SELECT
            ensemble.ensemble_member                              AS member,
            forecast.time                                         AS valid_time,
            ROUND(ensemble.`2m_temperature` - 273.15, 2)         AS temperatura_c,
            ROUND(GREATEST(ensemble.`total_precipitation_6hr` * 1000, 0), 3) AS precip_6h_mm,
            ROUND(SQRT(POW(ensemble.`10m_u_component_of_wind`, 2)
                + POW(ensemble.`10m_v_component_of_wind`, 2)) * 3.6, 2)  AS viento_kmh,
            ROUND(
              (ATAN2(-ensemble.`10m_u_component_of_wind`,
                     -ensemble.`10m_v_component_of_wind`) * 180.0 / ACOS(-1.0) + 360.0)
              - FLOOR((ATAN2(-ensemble.`10m_u_component_of_wind`,
                             -ensemble.`10m_v_component_of_wind`) * 180.0 / ACOS(-1.0)
                       + 360.0) / 360.0) * 360.0
            , 1)                                                  AS direccion_viento_deg
        FROM `{_BQ_TABLE}` AS t1,
             UNNEST(forecast)  AS forecast,
             UNNEST(ensemble)  AS ensemble
        WHERE ST_CONTAINS(t1.geography_polygon, ST_GEOGPOINT(@lon, @lat))
          AND t1.init_time = (
              SELECT MAX(init_time) FROM `{_BQ_TABLE}`
              WHERE ST_CONTAINS(geography_polygon, ST_GEOGPOINT(@lon, @lat))
          )
          AND forecast.hours <= @horizonte_h
        ORDER BY ensemble.ensemble_member, forecast.time
        """

        params = [
            bigquery.ScalarQueryParameter("lon", "FLOAT64", lon),
            bigquery.ScalarQueryParameter("lat", "FLOAT64", lat),
            bigquery.ScalarQueryParameter("horizonte_h", "INT64", horizonte_h),
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(client.query(sql, job_config=job_config).result())

        if not rows:
            return []

        miembros: dict[int, dict] = {}
        for row in rows:
            m = row["member"]
            if m not in miembros:
                miembros[m] = {"precip_total": 0.0, "temps": [], "vientos": []}
            miembros[m]["precip_total"] += row["precip_6h_mm"] or 0.0
            if row["temperatura_c"] is not None:
                miembros[m]["temps"].append(row["temperatura_c"])
            if row["viento_kmh"] is not None:
                miembros[m]["vientos"].append(row["viento_kmh"])

        pronosticos = []
        for m_id, datos in miembros.items():
            temp_media = sum(datos["temps"]) / len(datos["temps"]) if datos["temps"] else None
            viento_max = max(datos["vientos"]) if datos["vientos"] else None

            pronosticos.append(PronosticoMeteorologico(
                fuente=self.nombre,
                zona=zona,
                horizonte_h=horizonte_h,
                lat=lat,
                lon=lon,
                temperatura_2m_c=round(temp_media, 1) if temp_media is not None else None,
                precipitacion_mm=round(datos["precip_total"], 1),
                viento_10m_kmh=round(viento_max, 1) if viento_max is not None else None,
                ensemble_id=m_id,
                n_miembros_ensemble=len(miembros),
                fuente_disponible=True,
                requires_local_correction=True,
            ))

        logger.info(
            f"FuenteWeatherNext2: '{zona}' — {len(pronosticos)} miembros ensemble "
            f"lat={lat} lon={lon}"
        )
        return pronosticos

    def _calcular_percentiles(
        self,
        ensemble: list[PronosticoMeteorologico],
        zona: str,
        lat: float,
        lon: float,
        horizonte_h: int,
    ) -> PronosticoMeteorologico:
        """Calcula P10/P50/P90 del ensemble y retorna el pronóstico central."""
        precips = sorted([p.precipitacion_mm for p in ensemble if p.precipitacion_mm is not None])
        temps = sorted([p.temperatura_2m_c for p in ensemble if p.temperatura_2m_c is not None])

        n = len(precips)
        p10_p = precips[int(n * 0.1)] if precips else None
        p50_p = precips[int(n * 0.5)] if precips else None
        p90_p = precips[int(n * 0.9)] if precips else None

        n_t = len(temps)
        p10_t = temps[int(n_t * 0.1)] if temps else None
        p90_t = temps[int(n_t * 0.9)] if temps else None

        central = ensemble[len(ensemble) // 2]
        central.p10_precipitacion = p10_p
        central.p50_precipitacion = p50_p
        central.p90_precipitacion = p90_p
        central.p10_temperatura = p10_t
        central.p90_temperatura = p90_t
        central.n_miembros_ensemble = len(ensemble)
        return central
