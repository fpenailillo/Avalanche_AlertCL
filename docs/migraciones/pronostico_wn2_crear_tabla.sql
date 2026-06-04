-- Crea la tabla climas-chileno.clima.pronostico_wn2
-- Particionada por DATE(ingestion_timestamp), clustered por nombre_ubicacion + nivel + fecha_local
-- Compatible con boletines_riesgo pre-v15 (todos los campos NULLABLE excepto los 3 REQUIRED).
--
-- Ejecutar UNA VEZ en BigQuery Console o con bq CLI:
--   bq query --use_legacy_sql=false < docs/migraciones/pronostico_wn2_crear_tabla.sql

CREATE TABLE IF NOT EXISTS `climas-chileno.clima.pronostico_wn2`
(
  nombre_ubicacion         STRING    NOT NULL  OPTIONS(description="Nombre exacto de la zona (COORDENADAS_ZONAS)"),
  ingestion_timestamp      TIMESTAMP NOT NULL  OPTIONS(description="Momento en que se ejecutó la ingesta (UTC)"),
  nivel                    STRING    NOT NULL  OPTIONS(description="ventana | diario"),

  fecha_local              DATE               OPTIONS(description="Fecha local del pronóstico (UTC-3)"),
  ventana                  STRING             OPTIONS(description="manana | tarde | noche | madrugada | --- TOTAL DÍA ---"),
  ventana_orden            INT64              OPTIONS(description="1-4 para ventanas, 9 para diario"),
  eaws_horizon             STRING             OPTIONS(description="H24 | H48 | H72 | beyond_72h"),
  init_time                TIMESTAMP          OPTIONS(description="Hora de inicialización del run WN2 usado"),
  forecast_lead_hours      INT64              OPTIONS(description="Horas de lead del pronóstico"),
  n_members                INT64              OPTIONS(description="Miembros ensemble usados (max 64)"),

  temp_mean_c              FLOAT64,
  temp_p05_c               FLOAT64,
  temp_p50_c               FLOAT64,
  temp_p95_c               FLOAT64,
  temp_std_c               FLOAT64,
  temp_delta_mean_c        FLOAT64,

  precip_p50_mm            FLOAT64,
  precip_p95_mm            FLOAT64,

  est_nieve_6h_cm_p50_corr FLOAT64,
  est_nieve_6h_cm_p95_corr FLOAT64,

  mslp_mean_hpa            FLOAT64,

  wind_10m_mean_ms         FLOAT64,
  wind_100m_mean_ms        FLOAT64,
  wind_100m_max_ms         FLOAT64,
  wind_100m_p95_ms         FLOAT64,
  wdir_100m_mean_deg       FLOAT64,
  wdir_100m_cardinal       STRING,
  wind_class_es            STRING             OPTIONS(description="calma | leve | moderado | fuerte | temporal"),

  prob_snow_pct            FLOAT64,
  prob_wet_snow_pct        FLOAT64,
  prob_dry_snow_pct        FLOAT64,
  prob_wind_slab_pct       FLOAT64,

  probable_avalanche_problem STRING           OPTIONS(description="storm_slab|wind_slab|new_snow|wet_snow|persistent_weak_layer|low_load"),
  alert_heavy_snow         BOOL,
  alert_storm_slab         BOOL,
  alert_wet_snow           BOOL,
  alert_wind_strong        BOOL,
  confianza_pronostico     STRING             OPTIONS(description="alta|media|baja|muy_baja"),

  nieve_24h_cm_p50_corr    FLOAT64            OPTIONS(description="Solo nivel=diario"),
  nieve_24h_cm_p95_corr    FLOAT64            OPTIONS(description="Solo nivel=diario"),
  problema_dominante       STRING             OPTIONS(description="Solo nivel=diario"),
  confianza_dia            STRING             OPTIONS(description="Solo nivel=diario")
)
PARTITION BY DATE(ingestion_timestamp)
CLUSTER BY nombre_ubicacion, nivel, fecha_local
OPTIONS(
  description="Pronóstico WeatherNext 2 diario — horizonte 15 días, ventanas 6h + resumen diario. v15.0+."
);
