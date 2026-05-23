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
| FIX-VIENTO-SQL (ingestor_wn2.py:139) | ⏳ Pendiente |
| Aclarar cobertura imagenes/zonas (25/70 y 39/70) | ⏳ Pendiente |
| Confirmar job ingestor-wn2 en Cloud Run | ⏳ Pendiente |

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

### HIGH — Subestimación sistemática de riesgo alto (nuevo hallazgo de validación)

Los resultados de H3 y H4 revelan que el sistema no predice niveles EAWS ≥ 3
en ningún caso. Esto no es un problema de datos, es un problema del modelo (prompts
de clasificación o calibración post-LLM). La calibración FIX-CALIB-REG v21 tiene
shift +0.70 en Alpes, pero el suelo de las predicciones es nivel 1 incluso cuando
SLF reporta 3–4.

**Próximo paso:** revisar el subagente S5 Integrador y el prompt de clasificación
EAWS para entender por qué el sistema no llega a niveles ≥ 3.

### MEDIUM — Cobertura incompleta en imagenes_satelitales y zonas_avalancha

- `imagenes_satelitales`: 25/70 ubicaciones con datos en las últimas 24h
- `zonas_avalancha`: 39/70 ubicaciones

Causa probable: cobertura de cielo despejado para satélite y selección de zonas
relevantes. Confirmar si el subset de 25/39 es el definido operacionalmente.

### MEDIUM — ingestor-wn2 no encontrado como Cloud Run Job

`gcloud run jobs describe ingestor-wn2` retorna error. El job puede llamarse
diferente o estar en otra región. El dataset `weathernext_2` existe y tiene datos
(stale 10.9h, comportamiento esperado), pero no se pudo auditar el proceso de ingesta.
Confirmar nombre real del job con `gcloud run jobs list --region=us-central1`.

### LOW — f-string SQL en ingestor_wn2.py:139

`ST_GEOGPOINT({lon}, {lat})` por f-string. Bajo riesgo práctico (float), pero
rompe el patrón de queries parametrizadas del resto del codebase.
Fix: usar `@lat`, `@lon` como `ScalarQueryParameter`.

---

## Tests

```
pytest agentes/tests/ -q
502 passed, 8 skipped  ✅ (sin regresiones post-fixes)
```
