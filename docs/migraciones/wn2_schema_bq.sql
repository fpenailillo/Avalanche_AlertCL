-- ============================================================
-- Migración v15.0: WeatherNext 2 — 6 nuevos campos en boletines_riesgo
-- Ejecutar una sola vez en BigQuery Console o via bq CLI:
--   bq query --use_legacy_sql=false < wn2_schema_bq.sql
-- ============================================================
--
-- Todos los campos son NULLABLE para compatibilidad con boletines
-- previos a v15.0 donde WN2 no estaba activo.
-- Se poblarán con NULL cuando USE_WEATHERNEXT2=false.
--

ALTER TABLE `climas-chileno.clima.boletines_riesgo`
  ADD COLUMN IF NOT EXISTS wn2_alert_heavy_snow BOOL
    OPTIONS(description="WN2 v15.0: alerta nieve intensa (prob_snow>=80% AND precip_p95>=5mm)"),
  ADD COLUMN IF NOT EXISTS wn2_alert_storm_slab BOOL
    OPTIONS(description="WN2 v15.0: alerta placa de tormenta (prob_dry_snow>=89% AND precip_p50>=2mm AND viento100m>=8m/s)"),
  ADD COLUMN IF NOT EXISTS wn2_alert_wet_snow BOOL
    OPTIONS(description="WN2 v15.0: alerta nieve húmeda (prob_wet_snow>=40% AND temp_mean>-1°C)"),
  ADD COLUMN IF NOT EXISTS wn2_alert_wind_strong BOOL
    OPTIONS(description="WN2 v15.0: alerta viento fuerte (wind_100m_p95>=15m/s)"),
  ADD COLUMN IF NOT EXISTS wn2_avalanche_problem STRING
    OPTIONS(description="WN2 v15.0: problema dominante (storm_slab|wind_slab|new_snow|wet_snow|persistent_weak_layer|low_load)"),
  ADD COLUMN IF NOT EXISTS wn2_confianza STRING
    OPTIONS(description="WN2 v15.0: confianza pronóstico ensemble (alta|media|baja|muy_baja)");

-- Verificación post-migración:
-- SELECT column_name, data_type
-- FROM `climas-chileno.clima.INFORMATION_SCHEMA.COLUMNS`
-- WHERE table_name = 'boletines_riesgo'
--   AND column_name LIKE 'wn2_%';
