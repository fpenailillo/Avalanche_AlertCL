# Ronda 7 — Resultados Validación AndesAI v7.5

**Fecha:** 2026-05-08  
**Versión sistema:** v7.5 (VERSION_GLOBAL=7.5)  
**Reproceso:** 120 runs — ok=120, err=0, skip=0 (49.723s / ~13.8h, 3 hangs TCP)  
**Branch:** `main`

---

## Fixes implementados en v7.5 (respecto a v7.0)

| Fix | Archivo(s) | Descripción |
|-----|-----------|-------------|
| **FIX-A (CR-6)** | `tool_clasificar_eaws.py`, `prompts.py` (S1 + S5) | EAWS Paso 1 ahora basado en datos: reemplaza `problema_avalancha_presente` (bool S1) con `condiciones_meteo_disponibles` (bool S5). Solo activa nivel 1 cuando S3 tuvo datos reales + factor neutro + ventanas=0. Sin datos → camino conservador. |
| **FIX-B (CURRENT_DATE)** | `consultor_bigquery.py` | `obtener_estado_manto` y `obtener_sar_baseline` usaban `CURRENT_DATE()` fijo, ignorando `_fecha_referencia_global`. Runs retroactivos obtenían datos satelitales/térmicos del 2026 en vez del período histórico. |

### Principio metodológico v7.5

> "Sin datos ≠ sin trigger. La ausencia de datos meteorológicos es incertidumbre, no evidencia de calma."

EAWS Paso 1 solo se activa cuando S3 confirma positivamente que no hubo trigger meteorológico (datos reales disponibles + factor neutro). Para runs retroactivos donde la tabla `condiciones_actuales` no tiene registros históricos, el sistema toma el camino conservador (continúa con la matriz EAWS).

---

## H1 y H3 — Validación Swiss SLF

**Script:** `notebooks_validacion/07_validacion_slf_suiza.py --version v7.5`  
**Ground truth:** `validacion_avalanchas.slf_danger_levels_qc`  
**Muestra:** n=24 pares (3 estaciones × 10 fechas, invierno 2023-2024)  
**Mapeo:** sector preciso (REQ-04)

### Métricas

| Métrica | v6.2 (R5) | v7.0 (R6) | v7.5 (R7) | Δ v6.2→v7.5 | Objetivo |
|---------|-----------|-----------|-----------|-------------|----------|
| QWK | −0.031 | 0.000 | **+0.103** | +0.134 | ≥ +0.10 ✅ |
| F1-macro | 0.244 | 0.056 | **0.176** | −0.068 | ≥ 0.75 ❌ |
| Accuracy exacta | 0.333 | 0.125 | **0.292** | −0.042 | — |
| Accuracy ±1 | 0.750 | 0.667 | **0.750** | 0.000 | — |
| Sesgo medio | −0.75 | −1.33 | **−0.71** | +0.04 | — |

**H3 ALCANZADA:** QWK = 0.103 ≥ 0.10 ✅  
**H1 NO ALCANZADA:** F1-macro = 0.176 (objetivo ≥ 0.75)

### Distribución de niveles (n=24)

| Nivel | SLF real | AndesAI v6.2 | AndesAI v7.0 | AndesAI v7.5 |
|-------|----------|--------------|--------------|--------------|
| 1 | 12.5% | 54.2% | 100.0% | **45.8%** |
| 2 | 54.2% | 33.3% | 0.0% | **45.8%** |
| 3 | 20.8% | 12.5% | 0.0% | **8.3%** |
| 4 | 12.5% | 0.0% | 0.0% | **0.0%** |
| 5 | 0.0% | 0.0% | 0.0% | **0.0%** |

---

## H4 — Validación Snowlab La Parva

**Script:** `notebooks_validacion/08_validacion_snowlab.py --version v7.5`  
**Ground truth:** `validacion_avalanchas.snowlab_boletines`  
**Muestra:** n=87 pares (3 sectores × 30 boletines)

### Métricas globales

| Métrica | v6.2 (R5) | v7.0 (R6) | v7.5 (R7) | Δ v6.2→v7.5 | Objetivo |
|---------|-----------|-----------|-----------|-------------|----------|
| QWK | −0.031 | 0.000 | **−0.139** | −0.108 | ≥ 0.40 ❌ |
| MAE | 1.230 | 0.506 | **1.448** | +0.218 | ≤ 1.00 ❌ |
| Sesgo (EAWS−Snowlab) | +0.885 | −0.506 | **+1.011** | +0.126 | ≤ +0.60 ❌ |
| F1-macro | 0.145 | 0.163 | **0.118** | −0.027 | — |
| % nivel 1-2 | 58% | 100% | **52%** | −6pp | ≥ 65% ❌ |
| MAE tormentas (Snowlab≥3) | N/D | 2.417 | **1.500** | — | ≤ 1.00 ❌ |

**H4 NO ALCANZADA** — regresión respecto a v6.2 en MAE (+0.218) y sesgo (+0.126)

### Distribución de niveles (n=87)

| Nivel | Snowlab | AndesAI v6.2 | AndesAI v7.0 | AndesAI v7.5 |
|-------|---------|--------------|--------------|--------------|
| 1 | 69% (60) | 15% (13) | 100% (87) | **14% (12)** |
| 2 | 17% (15) | 43% (37) | 0% (0) | **38% (33)** |
| 3 | 9% (8) | 32% (28) | 0% (0) | **36% (31)** |
| 4 | 3% (3) | 9% (8) | 0% (0) | **8% (7)** |
| 5 | 1% (1) | 1% (1) | 0% (0) | **5% (4)** |

### Matriz de confusión v7.5

```
              AndesAI
          1   2   3   4   5
Snowlab 1 [ 7  21  23   5   4]  (60 casos)
        2 [ 1   7   5   2   0]  (15 casos)
        3 [ 2   4   2   0   0]  ( 8 casos)
        4 [ 2   1   0   0   0]  ( 3 casos)
        5 [ 0   0   1   0   0]  ( 1 caso)
```

---

## Análisis de efectos por fix

| Fix | Efecto observado v7.5 | Veredicto |
|-----|----------------------|-----------|
| **FIX-A (CR-6)** | EAWS Paso 1 no activa en retroactivos → % nivel 1 baja de 100% a 14% H4 / 46% H1-H3 | ✅ Correcto |
| **FIX-B (CURRENT_DATE)** | Satelital/térmica ahora usa fechas 2024/2025 correctas → sistema ve más nieve activa → predice más alto | ⚠️ Corrige el bug, pero amplifica sobrepredicción H4 |
| **FIX-GEO** (v7.0, ahora medible) | Sin cap en Alpes → QWK H1/H3 sube de −0.031 a +0.103, objetivo cumplido | ✅ Efecto confirmado |
| **FIX-H** (v7.0, ahora medible) | Default 'poor' en Alpes → sesgo H1/H3 mejora de −1.33 a −0.71 | ✅ Efecto confirmado |

**Nueva causa raíz CR-7:** FIX-B reveló que el sistema sobreestima niveles H4 cuando recibe datos satelitales/térmicos históricos reales. En v6.2 los retroactivos usaban datos de 2026 (sin nieve de invierno andino = señal baja), lo que coincidentemente moderaba las predicciones. Con datos correctos de 2024/2025, el sistema ve cobertura nival real y escala los niveles al alza más de lo que corresponde.

---

## Progresión histórica completa

### H1/H3 — Swiss SLF

| Ronda | Versión | QWK | F1-macro | Acc exacta | Acc ±1 | Sesgo |
|-------|---------|-----|----------|------------|--------|-------|
| 1 | v3.0 | −0.056 | 0.197 | — | 0.708 | −0.79 |
| 2 | v3.2 (cantón) | +0.109 | 0.191 | 0.250 | 0.750 | −0.54 |
| 2b | v3.2 (sector) | +0.016 | 0.161 | 0.208 | 0.750 | −0.50 |
| 3 | v4.0 | +0.162 | 0.155 | 0.250 | 0.792 | −0.92 |
| 4 | v5.0 | +0.143 | 0.235 | 0.292 | 0.833 | −0.67 |
| 5 | v6.2 | −0.031 | 0.244 | 0.333 | 0.750 | −0.75 |
| 6 | v7.0 | 0.000 | 0.056 | 0.125 | 0.667 | −1.33 |
| **7** | **v7.5** | **+0.103** | **0.176** | **0.292** | **0.750** | **−0.71** |
| Ref. | Techel 2022 | 0.590 | 0.550 | 0.640 | 0.950 | — |

### H4 — Snowlab La Parva

| Ronda | Versión | QWK | MAE | Sesgo | F1-macro | % niv 1-2 |
|-------|---------|-----|-----|-------|----------|-----------|
| 2 | v3.2 | −0.016 | 2.103 | +1.989 | 0.104 | ~5% |
| 3 | v4.0 | −0.006 | 2.138 | +2.023 | 0.030 | ~0% |
| 4 | v5.0 | −0.000 | 1.724 | +1.609 | 0.084 | 21% |
| 5 | v6.2 | −0.031 | 1.230 | +0.885 | 0.145 | 58% |
| 6 | v7.0 | 0.000 | 0.506 | −0.506 | 0.163 | 100% |
| **7** | **v7.5** | **−0.139** | **1.448** | **+1.011** | **0.118** | **52%** |
| Objetivo | — | ≥ 0.40 | ≤ 1.00 | ≤ +0.60 | — | ≥ 65% |

---

## Causas raíz actualizadas post-v7.5

| ID | Descripción | Estado v7.5 |
|----|-------------|-------------|
| CR-1 | `tamano` topográfico Andes sobreestima nivel en días calmos | ✅ Resuelto (FIX-GEO aplica cap solo en Andes) |
| CR-4 | Sin ViT en invierno alpino → `estabilidad_satelital` subestima H1/H3 | ✅ Resuelto (FIX-H default 'poor' en Alpes) — efecto medido: sesgo H1/H3 mejora de −1.33 a −0.71 |
| CR-5 | Gap distribucional Snowlab: 69% nivel 1 vs AndesAI | ⚠️ Parcial — v7.5 predice 14% nivel 1 (vs 69% GT), sobrepredicción persistente |
| CR-6 | FIX-S1 activaba EAWS Paso 1 en 100% retroactivos | ✅ Resuelto (FIX-A: condición data-conditional) |
| **CR-7 nuevo** | **FIX-B reveló sobrepredicción H4 con datos históricos reales** — sistema escala demasiado alto al recibir cobertura nival 2024/2025 correcta | 🔴 Nueva causa raíz identificada en v7.5 |

---

---

## Diagnóstico CR-7 — Sobrepredicción H4 con datos históricos correctos

Con FIX-B, `obtener_estado_manto` y `obtener_sar_baseline` usan la fecha de referencia histórica real (2024/2025). Esto significa que S2 recibe datos satelitales/térmicos de invierno andino activo:

- **Antes (v6.2 retroactivo):** `CURRENT_DATE()` = mayo 2026 → sin datos de invierno → señal satelital baja → niveles moderados
- **Ahora (v7.5 retroactivo):** fecha correcta (ej. julio 2024) → datos de temporada nevada activa → cobertura nival alta → S5 sube niveles

El sistema interpreta correctamente que hay nieve activa, pero **calibra el riesgo por encima del nivel real** — el sesgo positivo (+1.011) sugiere que la relación entre cobertura nival y nivel EAWS está sobreajustada para el contexto andino.

**Hipótesis para v8.0:** recalibrar los umbrales de `_determinar_estabilidad_dominante` usando los pares (cobertura_nival, nivel_EAWS) del dataset Snowlab como referencia, o introducir un factor de atenuación regional para La Parva basado en la climatología histórica.

---

*Generado desde sesión Claude Code 2026-05-09.*  
*Reproceso: PID 51823, log `/tmp/reproceso_v75.log`. Duración: 49.723s (~13.8h).*  
*Datos fuente: BigQuery `climas-chileno.clima.boletines_riesgo` (STARTS_WITH version_prompts, 'v7.5').*
