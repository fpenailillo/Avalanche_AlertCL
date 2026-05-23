# Mejoras capa de datos — auditoría 2026-05-23

Archivo de seguimiento generado tras la auditoría read-only de la capa de datos.
Registra los hallazgos, los fixes implementados y los pendientes priorizados.

---

## Estado general

| Fase | Estado |
|---|---|
| Auditoría diagnóstica (read-only) | ✅ Completada 2026-05-23 |
| Fix FIX-WIND-PRONOSTICO | ✅ Implementado |
| Fix FIX-VERSION-DEFAULT-07 | ✅ Implementado |
| Fix FIX-VERSION-DEFAULT-08 | ✅ Implementado |
| Validación H3 (SLF Suiza) con datos reales | ✅ Ejecutada |
| Validación H4 (Snowlab La Parva) con datos reales | ✅ Ejecutada |
| FIX-VIENTO-SQL (ingestor_wn2.py:139) | ✅ Implementado |
| FIX-ESTADO-MANTO-VIEW (CREATE VIEW estado_manto_gee) | ✅ Implementado |
| Aclarar cobertura imagenes/zonas (28 imag. / 39 zonas) | ✅ Aclarado |
| Confirmar USE_WEATHERNEXT2 en Cloud Run | ✅ Confirmado: `true` |
| Confirmar job ingestor-wn2 en Cloud Run | ✅ Confirmado: integrado en orquestador |

---

## Fixes implementados

### FIX-WIND-PRONOSTICO — `agentes/datos/consultor_bigquery.py:474-483`

**Problema:** `obtener_tendencia_meteorologica()` tomaba `velocidad_viento` de
`pronostico_horas` (almacenado en km/h por Google Weather API METRIC mode) y lo
usaba directamente como m/s. El umbral `> 15` disparaba `VIENTO_FUERTE` con apenas
15 km/h (~4 m/s = brisa suave). El valor retornado como `viento_max_ms` en el dict
de resultado era incorrecto y el display `f"{v} m/s ({v * 3.6} km/h)"` mostraba
unidades invertidas.

**Fix:** Se agrega variable intermedia `_viento_max_kmh` con el valor raw en km/h,
y se calcula `viento_max_ms = round(_viento_max_kmh / 3.6, 2)`. La comparación para
encontrar la hora del viento máximo usa `_viento_max_kmh`. El umbral de alerta (15 m/s
= 54 km/h = Beaufort 7) y el display ahora son correctos. Análogo a FIX-WIND-UNITS
ya aplicado en `condiciones_actuales:222`.

**Archivos:** `agentes/datos/consultor_bigquery.py` (líneas 474-483)
**Tests:** 502 passed, 0 regresiones

---

### FIX-VERSION-DEFAULT-07 — `notebooks_validacion/07_validacion_slf_suiza.py:418`

**Problema:** El argumento `--version` defaulteaba a `"v6"`. No existe ningún
boletín con `version_prompts LIKE 'v6%'` en la tabla `boletines_riesgo`. Los
boletines disponibles para las fechas de validación (dic 2023–abr 2024) son
versión `v13.0`. El notebook retornaba 0 pares y abortaba.

**Fix:** `default="v6"` → `default="v13"`. Con v13 se encuentran 30 boletines
(10 por estación) y 24 pares válidos con ground truth SLF.

**Archivos:** `notebooks_validacion/07_validacion_slf_suiza.py` (línea 418)

---

### FIX-VERSION-DEFAULT-08 — `notebooks_validacion/08_validacion_snowlab.py`

**Problema:** Mismo problema que FIX-VERSION-DEFAULT-07. El default `"v6"` retorna
0 boletines para La Parva. Los boletines disponibles en temporada Snowlab
(jun–sep 2024 y 2025) son mayoritariamente versión `v25.0` (87 boletines, 3 sectores,
ambas temporadas completas).

**Fix:** `default="v6"` → `default="v25"` tanto en `cargar_datos()` como en el
argumento CLI `--version`.

**Archivos:** `notebooks_validacion/08_validacion_snowlab.py` (líneas 119, 325)

---

---

### FIX-ESTADO-MANTO-VIEW — BigQuery VIEW `climas-chileno.clima.estado_manto_gee`

**Problema:** `obtener_estado_manto()` en `consultor_bigquery.py` consultaba la tabla
`climas-chileno.clima.estado_manto_gee`, que no existía como tabla física. El método
retornaba siempre `disponible=False` en silencio. El subagente S2 (Satelital) nunca
recibía datos de estado del manto (LST, ERA5, gradiente térmico).

**Fix:** Se creó una VIEW en BigQuery que mapea las columnas ERA5/LST de
`imagenes_satelitales` al esquema esperado por `obtener_estado_manto()`:

```sql
CREATE OR REPLACE VIEW `climas-chileno.clima.estado_manto_gee` AS
SELECT
    nombre_ubicacion,
    fecha_captura AS fecha,
    COALESCE(lst_dia_celsius, lst_min_celsius, era5_temp_2m_celsius) AS lst_celsius,
    era5_temp_2m_celsius AS temp_suelo_l1_celsius,
    CAST(NULL AS FLOAT64) AS temp_suelo_l2_celsius,
    CASE ... END AS gradiente_termico,
    pct_nubes AS cobertura_nubosa_pct,
    fuente_principal AS fuente_lst
FROM `climas-chileno.clima.imagenes_satelitales`
```

**Verificación:** `obtener_estado_manto("La Parva Sector Alto")` retorna:
`disponible=True, lst_celsius_medio_7d=-1.43, dias_lst_positivo=1,
gradiente_termico_medio=2.009, n_registros=14`

**Archivos:** Solo BigQuery (DDL), no requiere cambios en código.

---

### FIX-VIENTO-SQL — `agentes/datos/ingestores/ingestor_wn2.py:139`

**Problema:** `ST_GEOGPOINT({lon}, {lat})` usaba interpolación f-string para
coordenadas geográficas. Aunque `lat`/`lon` son floats (riesgo de inyección bajo),
rompe el patrón de queries completamente parametrizadas del resto del codebase y
crea una inconsistencia al mezclar f-strings con `@init_date_start`/`@init_date_end`
en la misma query.

**Fix:** `_sql_wn2(lat, lon)` → `_sql_wn2()` (sin argumentos). La línea 139 usa
ahora `ST_GEOGPOINT(@lon, @lat)`. En `_consultar_wn2()` se agregan dos nuevos
`ScalarQueryParameter("lat", "FLOAT64", lat)` y `ScalarQueryParameter("lon",
"FLOAT64", lon)`.

**Archivos:** `agentes/datos/ingestores/ingestor_wn2.py` (líneas 118-119, 139, 409-413)

---

## Resumen de consistencia de la capa de datos (2026-05-23)

| Componente | Estado | Notas |
|---|---|---|
| `condiciones_actuales` | ✅ Fresco | Ubicaciones operacionales OK; 22 legacy stale (esperado) |
| `pronostico_horas` / `pronostico_dias` | ✅ Fresco | — |
| `pronostico_wn2` | ✅ Activo | `USE_WEATHERNEXT2=true` en Cloud Run Job |
| `imagenes_satelitales` | ✅ Fresco | 25/28 ubicaciones con datos ≤48h; 3 suizas en pausa estacional |
| `estado_manto_gee` | ✅ VIEW creada | Antes siempre `disponible=False`; ahora funcional |
| `zonas_avalancha` | ✅ Fresco | 39 ubicaciones operacionales (no 39/70) |
| `boletines_riesgo` | ✅ OK | Versiones v13/v25 para validación H3/H4 |
| `slf_danger_levels_qc` | ✅ OK | Sectores 2223/4113/6113 presentes |
| `snowlab_boletines` | ✅ OK | Temporadas 2024/2025 completas |
| `snow_depth_caro_2026` | ✅ OK | Pre-QC'd en Zenodo; `qc_status="clean"` intencional |
| `earth_ai` (S2_VIA) | ✅ Activo | `S2_VIA=ambas_consolidar_vit` en Cloud Run Job |
| `ingestor_wn2` | ✅ Integrado | Parte del orquestador-avalanchas (no job separado) |

**Pendiente de modelo (no datos):** Sistema nunca predice EAWS ≥ 3 — revisar S5 Integrador.

---

## Resultados de validación

### H3 — Suiza (versión v13.0, n=24 pares)

```
Fechas:     10 fechas dic-2023 → abr-2024
Estaciones: Interlaken (4113), Matterhorn Zermatt (2223), St Moritz (6113)
Pares:      24/30 (6 fechas sin GT preciso para algunas estaciones)
Via sector: 16 preciso | 8 fallback_cantón

Accuracy exacta      : 0.125   (Techel 2022: 0.64)
Accuracy adyacente   : 0.708   (Techel 2022: 0.95)
F1-macro             : 0.078   (objetivo ≥ 0.75) ❌
QWK                  : -0.103  (objetivo ≥ 0.59) ❌
```

**Patrón dominante:** subestimación severa. AndesAI predice nivel 1 en 79% de
los casos; el ground truth SLF tiene niveles 2–4 en 87.5%. Sistema predice
condiciones de bajo riesgo cuando hay riesgo medio/alto.

**Distribución:**

| Nivel | SLF (GT) | AndesAI |
|---|---|---|
| 1 | 12.5% | 79.2% |
| 2 | 54.2% | 20.8% |
| 3 | 20.8% | 0.0% |
| 4 | 12.5% | 0.0% |
| 5 | 0.0% | 0.0% |

---

### H4 — La Parva Snowlab (versión v25.0, n=87 pares)

```
Temporadas: 2024 (14 boletines Snowlab), 2025 (16 boletines Snowlab)
Sectores:   Alto, Medio, Bajo
Pares:      87 pares de 3 sectores × 30 boletines Snowlab
Distancia media: 1.1 días

MAE                  : 0.586
Sesgo (EAWS−Snowlab) : -0.310
QWK                  : -0.080   (objetivo ≥ 0.60) ❌
Kappa lineal         : 0.050
F1-macro             : 0.210

Constraint v7.0 (MAE tormentas, Snowlab≥3):
  n=12, MAE=2.417  [objetivo ≤ 1.00] ❌
```

**Por sector:**

| Sector | n | MAE | Sesgo | QWK |
|---|---|---|---|---|
| Alto | 30 | 0.63 | -0.57 | 0.000 |
| Medio | 27 | 0.78 | -0.41 | -0.169 |
| Bajo | 30 | 0.37 | +0.03 | 0.098 |

**Patrón dominante:** igual que H3 — subestimación del riesgo en niveles ≥3.
Todos los pares con Snowlab≥3 fueron clasificados como 1 (MAE=2.417 en tormentas).

---

## Hallazgos pendientes (sin fix en esta sesión)

### HIGH — Subestimación sistemática de riesgo alto (hallazgo de validación)

Los resultados de H3 y H4 revelan que el sistema no predice niveles EAWS ≥ 3
en ningún caso. Esto no es un problema de datos — la capa de datos está consistente.
Es un problema del modelo (prompts de clasificación o calibración post-LLM).
La calibración FIX-CALIB-REG v21 tiene shift +0.70 en Alpes, pero el suelo de
las predicciones es nivel 1 incluso cuando SLF reporta 3–4.

**Próximo paso:** revisar el subagente S5 Integrador y el prompt de clasificación
EAWS para entender por qué el sistema no llega a niveles ≥ 3.

---

## Tests

```
pytest agentes/tests/ -q
502 passed, 8 skipped  ✅ (sin regresiones post-fixes)
```
