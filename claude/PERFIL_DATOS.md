# Perfil de datos — Sistema AndesAI
## Proyecto: Tesis doctoral avalanchas, GCP `climas-chileno`
### Generado: 2026-05-23 — rama `feat/v7.0-fixes`

---

## 1. Infraestructura de almacenamiento

### BigQuery — Datasets

| Dataset | Propósito | Acceso |
|---|---|---|
| `climas-chileno.clima` | Datos operacionales + boletines + ground truth offline | Interno |
| `climas-chileno.validacion_avalanchas` | Ground truth validación tesis (SLF, Snowlab, EAWS) | Interno |
| `climas-chileno.weathernext_2` | Pronóstico ensemble WeatherNext 2 (Google DeepMind) | Analytics Hub (suscripción activa) |

### Cloud Storage

| Bucket | Propósito | Estructura |
|---|---|---|
| `gs://climas-chileno-datos-clima-bronce/` | Datos bronce (raw JSON, GeoTIFFs, previews) | `<ubicacion>/{boletines,clima,pronostico_dias,pronostico_horas,satelital}/` |
| `gs://climas-chileno_cloudbuild/` | Artefactos de build Cloud Run | — |

**Cobertura bucket bronce:** 96 carpetas de ubicaciones. Las ubicaciones de estudio (La Parva Sector Alto/Medio/Bajo, Interlaken, Matterhorn Zermatt, St Moritz) tienen sub-carpetas completas.

---

## 2. Dataset `climas-chileno.clima` — Tablas operacionales

### 2.1 `boletines_riesgo`
**Propósito:** Output principal del sistema. Un registro por (ubicación, fecha_emisión).  
**Filas:** 606 | **Ubicaciones:** 41 | **Cobertura:** 2018-12-06 → 2026-05-22

| Columna | Tipo | Descripción |
|---|---|---|
| `nombre_ubicacion` | STRING | Nombre del área de pronóstico |
| `fecha_emision` | TIMESTAMP | Momento de generación del boletín |
| `nivel_eaws_24h` | INTEGER | Nivel EAWS (1-5) a 24h (con calibración FIX-CALIB-REG v21) |
| `nivel_eaws_24h_raw` | INTEGER | Nivel EAWS antes de calibración post-LLM |
| `nivel_eaws_48h` | INTEGER | Nivel EAWS a 48h |
| `nivel_eaws_72h` | INTEGER | Nivel EAWS a 72h |
| `version_prompts` | STRING | Versión del sistema (v13.0, v15.0, v22.0, v25.0...) |
| `boletin_texto` | STRING | Texto completo del boletín generado por LLM |
| `modelo` | STRING | Modelo LLM utilizado (Qwen3-80B, etc.) |
| `wn2_alert_*` | BOOLEAN | Alertas WeatherNext 2 (heavy_snow, storm_slab, wet_snow, wind_strong) |
| `tipo_problema_eaws` | STRING | Tipo de problema de avalancha EAWS |
| `ventanas_criticas` | INTEGER | Ventanas meteorológicas críticas detectadas |
| `datos_satelitales_disponibles` | BOOLEAN | Estado de S2 en el boletín |
| `estado_vit`, `score_anomalia_vit` | STRING/FLOAT | Output Earth AI ViT |
| `factor_seguridad_pinn` | FLOAT | Factor de seguridad del modelo PINN |

**Distribución de versiones por ubicación de tesis:**
- Interlaken: v3.1, v3.2, v13.x, v15.x, v25.x (69 boletines, desde 2018)
- Matterhorn Zermatt: v3.1, v3.2, v13.x, v15.x, v25.x (69 boletines, desde 2018)
- St Moritz: v3.1, v3.2, v13.x, v15.x, v25.x (68 boletines, desde 2018)
- La Parva Sector Alto: v3.1, v3.2, v15.x, v22.x, v25.x (98 boletines, desde 2023)
- La Parva Sector Medio: v3.1, v3.2, v15.x, v25.x (97 boletines, desde 2023)
- La Parva Sector Bajo: v3.1, v3.2, v15.x, v22.x, v25.x (97 boletines, desde 2023)

---

### 2.2 `condiciones_actuales`
**Propósito:** Condiciones meteorológicas en tiempo real (AWS + Google Weather API).  
**Filas:** 81.990 | **Ubicaciones:** 92 | **Cobertura:** 2018-12-06 → actual

| Columna | Tipo | Descripción |
|---|---|---|
| `nombre_ubicacion` | STRING | Nombre del área |
| `hora_actual` | TIMESTAMP | Timestamp de la observación |
| `temperatura` | FLOAT | °C |
| `velocidad_viento` | FLOAT | **km/h** (dividir por 3.6 para m/s — FIX-WIND-UNITS) |
| `precipitacion_acumulada` | FLOAT | mm/h |
| `humedad_relativa` | FLOAT | % |
| `presion_aire` | FLOAT | hPa |
| `punto_rocio` | FLOAT | °C |
| `probabilidad_precipitacion` | FLOAT | 0-100% |
| `probabilidad_tormenta` | FLOAT | 0-100% |
| `cobertura_nubes` | FLOAT | % |
| `indice_uv` | FLOAT | — |
| `es_dia` | BOOLEAN | — |

> **Nota FIX-WIND-UNITS:** `velocidad_viento` está almacenado en km/h (METRIC mode de Google Weather API). El consultor divide por 3.6 al leer (`consultor_bigquery.py:222`).

---

### 2.3 `pronostico_horas`
**Propósito:** Pronóstico horario (~72h horizonte), OpenMeteo/AROME.  
**Filas:** 309.083 | **Cobertura:** 2026-03-18 → +72h rolling

| Columna | Tipo | Descripción |
|---|---|---|
| `nombre_ubicacion` | STRING | — |
| `hora_inicio` / `hora_fin` | TIMESTAMP | Ventana horaria |
| `temperatura` | FLOAT | °C |
| `velocidad_viento` | FLOAT | **km/h** (FIX-WIND-PRONOSTICO: dividir/3.6 en consultor) |
| `cantidad_precipitacion` | FLOAT | mm |
| `tipo_precipitacion` | STRING | rain/snow/sleet/etc. |
| `temperatura_bulbo_humedo` | FLOAT | °C (wet bulb) |
| `rafaga_viento` | FLOAT | km/h |
| `espesor_hielo` | FLOAT | mm |

> **Nota FIX-WIND-PRONOSTICO:** `velocidad_viento` también en km/h. Corregido en `consultor_bigquery.py:474-483`.

---

### 2.4 `pronostico_dias`
**Propósito:** Pronóstico diario (~7 días), estructura día/noche.  
Columnas clave: `temp_max_dia`, `temp_min_dia`, `diurno_velocidad_viento` (km/h), `diurno_prob_precipitacion`, `nocturno_*` (duplicación day/night).

---

### 2.5 `imagenes_satelitales`
**Propósito:** Análisis multisensor (Sentinel-2, SAR, ERA5, LST) por ubicación y fecha.  
**Filas:** 5.057 | **Ubicaciones:** 28 | **Cobertura:** 2023-12-01 → actual

| Columna | Tipo | Descripción |
|---|---|---|
| `nombre_ubicacion` | STRING | — |
| `fecha_captura` | DATE | Fecha de la imagen |
| `ndsi_medio` / `ndsi_max` | FLOAT | Índice diferencial de nieve (−1 a +1) |
| `pct_cobertura_nieve` | FLOAT | % cobertura 0-100 |
| `snowline_elevacion_m` | FLOAT | Línea de nieve (m s.n.m.) |
| `lst_dia_celsius` / `lst_noche_celsius` | FLOAT | Temperatura superficie LST (°C) |
| `era5_snow_depth_m` | FLOAT | Profundidad de nieve ERA5 (m) |
| `era5_swe_m` | FLOAT | SWE ERA5 (m) |
| `era5_temp_2m_celsius` | FLOAT | Temperatura 2m ERA5 (°C) |
| `sar_pct_nieve_humeda` | FLOAT | % nieve húmeda SAR |
| `transporte_eolico_activo` | BOOLEAN | Transporte eólico activo |
| `viento_altura_vel_ms` | FLOAT | Velocidad viento en altura (m/s) |
| `sentinel2_disponible` | BOOLEAN | Disponibilidad Sentinel-2 |
| `uri_geotiff_*` / `uri_preview_*` | STRING | URIs GCS de artefactos |

---

### 2.6 `estado_manto_gee` (VIEW)
**Propósito:** Vista sobre `imagenes_satelitales` con columnas ERA5/LST en esquema esperado por `obtener_estado_manto()`.  
**Columnas:** `nombre_ubicacion`, `fecha` (= `fecha_captura`), `lst_celsius`, `temp_suelo_l1_celsius`, `gradiente_termico`, `cobertura_nubosa_pct`, `fuente_lst`.

> Creada 2026-05-23. Antes de la VIEW, `obtener_estado_manto()` siempre retornaba `disponible=False`.

---

### 2.7 `zonas_avalancha`
**Propósito:** Análisis topográfico de zonas de avalancha (S1 Topográfico).  
**Filas:** 2.412 | **Ubicaciones:** 39

Columnas clave: `zona_inicio_ha`, `zona_transito_ha`, `zona_deposito_ha`, `pendiente_media_inicio`, `pendiente_p90_inicio`, `aspecto_predominante_inicio`, `indice_riesgo_topografico`, `clasificacion_riesgo`, `tamano_estimado_eaws`, `peligro_eaws_base`.

---

### 2.8 `snow_depth_caro_2026`
**Propósito:** Profundidad de nieve en Andes centrales chilenos (validación offline tesis).  
**Filas:** 106.360 | **Estaciones:** 20 | **Cobertura:** 2010-06-11 → 2024-12-31  
**Fuente:** Dataset Caro 2026 — DOI: 10.5281/zenodo.20089265

| Columna | Tipo | Descripción |
|---|---|---|
| `station_id` / `station_name` | STRING | ID y nombre estación DGA/CEAZA |
| `basin` | STRING | Cuenca (`Río Elqui`, `Río Maipo`) |
| `andean_zone` | STRING | `Mediterranean` |
| `country` | STRING | `CL` |
| `elevation_m` | FLOAT | 2020–4425 m s.n.m. |
| `observation_date` | DATE | Fecha diaria |
| `snow_depth_cm` | FLOAT | Profundidad nieve (cm) |
| `qc_status` | STRING | Siempre `"clean"` — QC aplicado en Zenodo v4.2 |
| `data_source` | STRING | Fuente original |
| `paper_reference` | STRING | Referencia publicación |

**Distribución por cuenca:**
- Río Maipo: 13 estaciones, 2020–4425 m s.n.m.
- Río Elqui: 7 estaciones, 3209–4306 m s.n.m.
- Total: 15 años de datos, 2 cuencas hidrológicas

---

### 2.9 `relatos_montanistas`
**Propósito:** Relatos de montañistas scrapeados, procesados por LLM para contexto histórico avalanchas.  
**Filas:** 3.138 (snapshot 2025-07-20) | Columnas LLM: `llm_tipo_actividad`, `llm_nivel_riesgo`, `llm_factores_riesgo`, `llm_tipos_terreno`, `llm_puntuacion_riesgo`.

---

### 2.10 `pendientes_detalladas` / `zonas_objetivo`
- `pendientes_detalladas`: análisis DEM por ubicación — histograma de pendientes, % inicio posible, índice riesgo topográfico.
- `zonas_objetivo`: polígonos GEOGRAPHY de las zonas operacionales con metadatos EAWS.

---

## 3. Dataset `climas-chileno.validacion_avalanchas` — Ground truth

### 3.1 `slf_danger_levels_qc`
**Propósito:** Niveles de peligro SLF Suiza (H1/H3) — ground truth principal Alpes.  
**Filas:** 45.049 | **Sectores:** 146 | **Cobertura:** 2001-12-01 → 2024-05-18

| Columna | Tipo | Descripción |
|---|---|---|
| `date` | DATE | Fecha del boletín SLF |
| `sector_id` | INTEGER | ID del sector EAWS (2223=Matterhorn, 4113=Interlaken, 6113=St Moritz) |
| `danger_level_qc` | INTEGER | Nivel EAWS 1-5 QC'd |
| `elevation_m` | FLOAT | Elevación de referencia |
| `north/east/south/west` | FLOAT | Exposición (0-1) |
| `dry_wet` | STRING | Tipo de avalancha |

**Sectores de tesis:** 2223 (Matterhorn Zermatt), 4113 (Bernese Oberland / Interlaken), 6113 (Engadin / St Moritz).

---

### 3.2 `snowlab_boletines`
**Propósito:** Boletines Snowlab La Parva (H4) — ground truth principal Andes.  
**Filas:** 30 | **Cobertura:** 2024-06-15 → 2025-09-19

| Columna | Tipo | Descripción |
|---|---|---|
| `id_boletin` | STRING | Identificador único |
| `temporada` | INTEGER | 2024 o 2025 |
| `fecha_inicio_validez` / `fecha_fin_validez` | DATE | Ventana de validez |
| `nivel_alta` / `nivel_media` / `nivel_baja` | INTEGER | Nivel por banda de elevación |
| `nivel_max` | INTEGER | Nivel máximo del día |
| `problema_principal` | STRING | Tipo de problema EAWS |

**Nota:** 14 boletines temporada 2024 + 16 boletines temporada 2025 = 30 total. Genera 87 pares con 3 sectores AndesAI × boletines.

---

### 3.3 `slf_actividad_diaria_davos`
**Propósito:** Serie histórica de actividad de avalanchas Davos (AAI).  
**Filas:** 3.533 | **Cobertura:** 1998 → 2019

Columnas: `AAI_all`, `AAI_all_wet`, `AAI_all_dry`, `max_danger_corr`, `SIZE_234`.

---

### 3.4 `slf_avalanchas_davos`
**Propósito:** Catálogo individual de avalanchas Davos con características físicas.  
**Filas:** 13.918 | **Cobertura:** 1998 → 2019

Columnas: `snow_type`, `trigger_type`, `area_m2`, `aval_size_class`, `aspect_degrees`, `weight_AAI`.

---

### 3.5 `slf_meteo_snowpack`
**Propósito:** Variables meteorológicas y del manto nivoso (SNOWPACK model) estaciones SLF.  
**Filas:** ~500K+ | Variables SNOWPACK: `HS_mod`, `HS_meas`, `SWE`, `HN24`, `wind_trans24`, `pwl_100`, `ssi_pwl`, `Sclass2`.

---

### 3.6 `eaws_matrix_operacional`
**Filas:** 0 (tabla vacía — preparada para datos EAWS operacionales europeos).

---

## 4. Dataset `climas-chileno.weathernext_2` — WeatherNext 2 (Google DeepMind)

**Tabla:** `weathernext_2_0_0`  
**Acceso:** Analytics Hub, suscripción activa desde ≤2026-05-05  
**Estado en producción:** `USE_WEATHERNEXT2=true` en Cloud Run Job `orquestador-avalanchas`

| Columna | Tipo | Descripción |
|---|---|---|
| `init_time` | TIMESTAMP | Tiempo de inicialización del modelo |
| `geography` | GEOGRAPHY | Punto central |
| `geography_polygon` | GEOGRAPHY | Polígono del tile |
| `forecast` | ARRAY<STRUCT> | Array de horizontes temporales |
| `forecast[].time` | TIMESTAMP | Tiempo de pronóstico |
| `forecast[].hours` | INT64 | Lead time (horas) |
| `forecast[].ensemble` | ARRAY<STRUCT> | 50 miembros ensemble |
| `ensemble[].ensemble_member` | STRING | ID miembro |
| `ensemble[].2m_temperature` | FLOAT64 | K (restar 273.15 para °C) |
| `ensemble[].total_precipitation_6hr` | FLOAT64 | m (×1000 para mm) |
| `ensemble[].mean_sea_level_pressure` | FLOAT64 | Pa (÷100 para hPa) |
| `ensemble[].10m_u/v_component_of_wind` | FLOAT64 | m/s (componentes) |
| `ensemble[].100m_u/v_component_of_wind` | FLOAT64 | m/s a 100m |

**Variables derivadas (calculadas en ingesta):** `wind_10m_ms`, `wind_100m_ms`, `wdir_10m_deg`, `wdir_100m_deg`.

---

## 5. Resumen EDA — estadísticas clave

| Tabla | Filas | Ubicaciones únicas | Cobertura temporal |
|---|---|---|---|
| `condiciones_actuales` | 81.990 | 92 | 2018 → actual |
| `pronostico_horas` | 309.083 | — | 2026-03-18 → +72h rolling |
| `boletines_riesgo` | 606 | 41 | 2018 → actual |
| `imagenes_satelitales` | 5.057 | 28 | 2023-12 → actual |
| `zonas_avalancha` | 2.412 | 39 | 2026-03 → actual |
| `snow_depth_caro_2026` | 106.360 | 20 estaciones | 2010 → 2024 |
| `relatos_montanistas` | 3.138 | — | snapshot 2025-07 |
| `slf_danger_levels_qc` | 45.049 | 146 sectores | 2001 → 2024 |
| `slf_avalanchas_davos` | 13.918 | Davos | 1998 → 2019 |
| `slf_actividad_diaria_davos` | 3.533 | Davos | 1998 → 2019 |
| `snowlab_boletines` | 30 | La Parva | 2024 → 2025 |

---

## 6. Notas de ingeniería de datos críticas

### Unidades de velocidad de viento — convención unificada

Todas las tablas BQ almacenan `velocidad_viento` en **km/h**. El consultor convierte a **m/s** al leer. El patrón es consistente tras los siguientes fixes:

| Tabla | Columna | Almacenado | Convertido en |
|---|---|---|---|
| `condiciones_actuales` | `velocidad_viento` | km/h | `consultor_bigquery.py:222` (÷3.6) |
| `pronostico_horas` | `velocidad_viento` | km/h | `consultor_bigquery.py:477` (÷3.6) |
| `pronostico_dias` | `diurno/nocturno_velocidad_viento` | km/h | `consultor_bigquery.py:662` (÷3.6 → `viento_max_ms`) |
| `imagenes_satelitales` | `viento_altura_vel_ms` | m/s | ya en m/s (GEE/ERA5) |
| `weathernext_2` | `10m_u/v_component_of_wind` | m/s | ya en m/s (nativo WN2) |

**Fixes aplicados (todos en `feat/v7.0-fixes`):**
- `FIX-WIND-UNITS` (v21): `condiciones_actuales` — línea 222
- `FIX-WIND-PRONOSTICO` (2026-05-23): `pronostico_horas` — líneas 474-483
- `FIX-WIND-PRONOSTICO-DIAS` (2026-05-23): `pronostico_dias` — línea 658-662 + `tool_pronostico_dias.py:73,105`

**Bug corregido:** `tool_pronostico_dias.py` usaba `diurno_velocidad_viento` (km/h) directamente como m/s, disparando alertas `VIENTO_FUERTE_PRONOSTICADO` a partir de 20 km/h (~5 m/s). Ahora usa `viento_max_ms` (ya convertido en consultor).

### FIX-TENDENCIA-REGISTROS (2026-05-23)
`tool_clima_reciente.py` tenía código muerto en el bloque de tendencia 72h — buscaba `tendencia.get("registros")` y `tendencia.get("total_registros")` que `obtener_tendencia_meteorologica()` nunca retorna. Como resultado, los valores de temperatura min/max, viento y precipitación eran siempre el punto puntual de `condiciones_actuales` en lugar del resumen de 72h.

**Fix:** el bloque ahora usa directamente las claves `temp_min_72h`, `temp_max_72h`, `viento_max_ms` y `precip_total_acumulada_mm` del dict de tendencia.

### QC del dataset Caro 2026
- `qc_status = "clean"` en todas las filas es **intencional** — el QC fue aplicado previamente en Zenodo v4.2 (Caro et al. 2026, DOI: 10.5281/zenodo.20089265).

### VIEW `estado_manto_gee`
- No existe como tabla física. Es una VIEW sobre `imagenes_satelitales`.
- Creada 2026-05-23 (`FIX-ESTADO-MANTO-VIEW`) — antes `obtener_estado_manto()` siempre retornaba `disponible=False`.

### Particionamiento y QUALIFY en boletines
- `boletines_riesgo` usa `QUALIFY ROW_NUMBER() OVER (PARTITION BY nombre_ubicacion, DATE(fecha_emision) ORDER BY fecha_emision DESC) = 1` para deduplicar.
- Los notebooks de validación filtran por `STARTS_WITH(version_prompts, @version)`.
- Versiones para validación: H3 → `"v13"` (dic 2023–abr 2024), H4 → `"v25"` (jun 2024–sep 2025).

---

## 7. Estado de salud de la capa (auditoría 2026-05-23)

| Componente | Estado | Stale (h) |
|---|---|---|
| `condiciones_actuales` (ubicaciones operacionales) | ✅ Verde | < 4h |
| `pronostico_horas` / `pronostico_dias` | ✅ Verde | < 26h |
| `imagenes_satelitales` (28 ubicaciones) | ✅ Verde | < 48h (3 Suiza en pausa estacional) |
| `estado_manto_gee` (VIEW) | ✅ Funcional | — |
| `zonas_avalancha` | ✅ Verde | < 26h |
| `boletines_riesgo` | ✅ Verde | < 26h |
| `pronostico_wn2` | ✅ Activo | — |
| Ground truth SLF, Snowlab, Caro 2026 | ✅ Estático | Dataset fijo |

**Referencia completa:** ver `MEJORAS_CAPA_DATOS.md` para historial de fixes.
