-- Queries de validación post-ingesta: climas-chileno.clima.snow_depth_caro_2026
-- Ejecutar después de completar la ingesta del dataset Caro et al. 2026
-- Criterios de aceptación REQ-2026-09 §4 Tarea 1

-- ── Query 1: Conteo por estación y zona ──────────────────────────────────────
SELECT
  station_name,
  basin,
  andean_zone,
  elevation_m,
  COUNT(*)                                             AS total_obs,
  COUNT(snow_depth_cm)                                 AS valid_obs,
  MIN(observation_date)                                AS primera_obs,
  MAX(observation_date)                                AS ultima_obs,
  ROUND(AVG(snow_depth_cm), 2)                         AS promedio_sd_cm,
  ROUND(MAX(snow_depth_cm), 2)                         AS maximo_sd_cm
FROM `climas-chileno.clima.snow_depth_caro_2026`
WHERE qc_status = 'clean'
GROUP BY station_name, basin, andean_zone, elevation_m
ORDER BY basin, elevation_m;

-- ── Query 2: Gap entre raw y clean (% removido por QC) ───────────────────────
SELECT
  station_name,
  COUNT(CASE WHEN qc_status = 'raw'   THEN 1 END) AS obs_raw,
  COUNT(CASE WHEN qc_status = 'clean' THEN 1 END) AS obs_clean,
  ROUND(
    SAFE_DIVIDE(
      COUNTIF(qc_status = 'raw' AND snow_depth_cm IS NULL) * 100.0,
      COUNTIF(qc_status = 'raw')
    ), 2
  )                                                  AS pct_nulos_raw,
  ROUND(
    (1 - SAFE_DIVIDE(
      COUNTIF(qc_status = 'clean'),
      COUNTIF(qc_status = 'raw')
    )) * 100.0, 2
  )                                                  AS pct_removido_por_qc
FROM `climas-chileno.clima.snow_depth_caro_2026`
GROUP BY station_name
ORDER BY pct_removido_por_qc DESC;

-- ── Query 3: Verificación criterio >50k observaciones limpias ─────────────────
SELECT
  COUNT(*) AS total_obs_clean
FROM `climas-chileno.clima.snow_depth_caro_2026`
WHERE qc_status = 'clean';
-- Esperado: > 50,000

-- ── Query 4: Verificación de duplicados (clave lógica) ───────────────────────
SELECT
  station_id,
  observation_date,
  qc_status,
  COUNT(*) AS n_duplicados
FROM `climas-chileno.clima.snow_depth_caro_2026`
GROUP BY station_id, observation_date, qc_status
HAVING COUNT(*) > 1
ORDER BY n_duplicados DESC
LIMIT 20;
-- Esperado: 0 filas (sin duplicados)

-- ── Query 5: Distribución por cuenca y rango altitudinal ─────────────────────
SELECT
  basin,
  CASE
    WHEN elevation_m < 2500 THEN 'baja (<2500m)'
    WHEN elevation_m < 3000 THEN 'media-baja (2500-3000m)'
    WHEN elevation_m < 3500 THEN 'media-alta (3000-3500m)'
    WHEN elevation_m < 4000 THEN 'alta (3500-4000m)'
    ELSE 'muy_alta (>4000m)'
  END                                                 AS banda_altitudinal,
  COUNT(DISTINCT station_id)                          AS n_estaciones,
  ROUND(AVG(snow_depth_cm), 1)                        AS sd_promedio_cm,
  ROUND(MAX(snow_depth_cm), 1)                        AS sd_maximo_cm
FROM `climas-chileno.clima.snow_depth_caro_2026`
WHERE qc_status = 'clean'
GROUP BY basin, banda_altitudinal
ORDER BY basin, elevation_m;
