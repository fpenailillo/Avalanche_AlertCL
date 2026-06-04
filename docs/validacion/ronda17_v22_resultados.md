# Ronda 17 — v22.0: FIX-WIND-UNITS + FIX-CR10B-RECAL

**Fecha:** 2026-05-22  
**Branch:** feat/v7.0-fixes  
**Commits:** a0dfac4 (FIX-CA-WINDOW v13.0), incluye v21→v22 delta  
**Reproceso:** 120/120 runs completados (PID 71758 → PID 40436 por timeout)

---

## Cambios introducidos en v22.0

### FIX-WIND-UNITS (bug_021)
- **Causa raíz:** todas las rutas de ingesta almacenan `velocidad_viento` en km/h, pero todos los consumers (tool_condiciones_actuales, fuente_open_meteo, tool_clima_reciente, almacenador) asumían m/s → doble conversión ×3.6.
- **Fix:** `ConsultorBigQuery.obtener_condiciones_actuales` divide por 3.6 antes de entregar al LLM.
- **Impacto downstream:** consumers reciben m/s correctos; almacenador sigue haciendo ×3.6 para guardar km/h en BQ (ya correcto).

### FIX-CR10B-RECAL
- **Contexto:** umbral `_umbral_viento_redistribucion` Alpes = 7 m/s estaba basado en factor de subestimación ERA5 ×1.4 (crestas). Pero las estaciones IMIS de validación son de valle → ratio IMIS/ERA5 ≈ 1.0.
- **Análisis post-fix:** max ERA5 real en dataset = 5.22 m/s. Con umbral 7 m/s: 0/30 días activan señal de viento.
- **Nuevo umbral:** 3.0 m/s → activa 4/30 días, todos GT≥3 (100% precisión).

---

## Resultados H3 — Validación Suiza (DEAPSnow 2018-2020, n=30)

| Métrica | v21 | v22 | Δ |
|---|---|---|---|
| QWK | **0.353** ✅ | **-0.064** ❌ | -0.417 |
| Accuracy exacta | — | 0.433 | — |
| Accuracy ±1 | — | 0.867 | — |
| Sesgo medio | — | +0.03 | — |
| F1-macro | — | 0.231 | — |

**Distribución de niveles:**
| Nivel | GT (%) | AI v22 (%) |
|---|---|---|
| 1 | 20.0 | 0.0 |
| 2 | 40.0 | 76.7 |
| 3 | 36.7 | 20.0 |
| 4 | 3.3 | 3.3 |

**Distribución raw vs calibrado (calibración α=+0.70):**
| Raw | Calibrado | n | % |
|---|---|---|---|
| 1 | 2 | 23 | 76.7% |
| 2 | 3 | 6 | 20.0% |
| 3 | 4 | 1 | 3.3% |

---

## Resultados H4 — Validación La Parva Snowlab (n=87 pares)

| Métrica | v21 | v22 | Δ |
|---|---|---|---|
| QWK | **0.220** ✅ | **0.003** ❌ | -0.217 |
| MAE | — | 0.793 | — |
| Sesgo (AI−Snowlab) | +0.345 | +0.218 | -0.127 |
| F1-macro | — | 0.154 | — |
| MAE tormentas (SL≥3) | — | 1.667 | — |
| Constraint v7.0 (MAE≤1.00) | — | ❌ VIOLADO | — |

**Distribución de niveles:**
| Nivel | Snowlab | AI v22 |
|---|---|---|
| 1 | 60 | 30 |
| 2 | 15 | 51 |
| 3 | 8 | 6 |
| 4 | 3 | 0 |
| 5 | 1 | 0 |

---

## Análisis de la regresión

### Causa raíz identificada

El fix de unidades es **técnicamente correcto** pero removió una señal que accidentalmente beneficiaba las predicciones:

**Antes del fix (v21):**
- `velocidad_viento` almacenado en km/h (ej: 18.8 km/h = 5.22 m/s real)
- Consumers leían como m/s → "18.8 m/s" (3.6× inflado)
- Umbral Swiss VIENTO_REDISTRIBUCION = 7 m/s
- Effective real threshold: 7/3.6 = **1.94 m/s** → todos los 30 días suizos disparaban señal de viento
- Resultado: más ventanas críticas → raw level 2-3 → calibrado level 3-4 → mejor QWK

**Después del fix (v22):**
- Consumers reciben m/s correctos (max 5.22 m/s real)
- Umbral recalibrado = 3.0 m/s → solo 4/30 días activan señal de viento
- 23/30 runs: 0 ventanas de viento → EAWS matrix → raw level 1 → calibrado level 2
- Resultado: concentración en nivel 2, falla en capturar niveles 3-4

**Para La Parva:**
- Umbral viento `_umbral_viento_fuerte = 10.0 m/s` (= 36 km/h en km/h reales)
- Antes del fix: 36 km/h almacenado → leído como "36 m/s" >> 10 m/s → señal siempre activa
- Después del fix: 36 km/h / 3.6 = 10 m/s → borderline; días de tormenta moderada no disparan
- Resultado: días tormentosos (Snowlab≥3) quedan bajo-predichos → MAE tormentas 1.667

### La calibración (α=+0.70) fue entrenada sobre datos con bug
El shift de +0.70 para Alpes compensaba la subestimación del sistema **con viento inflado**. Con viento correcto, el sistema genera más raw level 1, por lo que la misma calibración ya no es suficiente para alcanzar GT levels 3-4.

---

## Deuda técnica identificada

1. **Recalibración umbrales v23:** ajustar `_umbral_viento_redistribucion` Swiss y `_umbral_viento_fuerte` La Parva considerando escala correcta m/s.
2. **Re-entrenamiento calibración:** los coeficientes α=+0.70 (Swiss) fueron optimizados sobre el sistema buggy. Requieren re-estimación sobre v22+ data.
3. **Señales alternativas:** el sistema depende excesivamente del viento. Explorar señales adicionales (HN24 mejorado, ERA5 precip gradiente orográfico) para sostener discriminación en días sin viento alto.

---

## Veredicto

| Hipótesis | v21 | v22 | Estado |
|---|---|---|---|
| H3 Suiza QWK ≥ 0.35 | 0.353 ✅ | -0.064 ❌ | Regresión por fix de unidades |
| H4 La Parva QWK ≥ 0.15 | 0.220 ✅ | 0.003 ❌ | Regresión por fix de unidades |
| Constraint MAE tormentas ≤ 1.00 | — | 1.667 ❌ | Violado |

**Nota para tesis:** v22 representa el sistema con la implementación correcta de unidades físicas. La degradación de QWK revela que v21 se beneficiaba de un bug que amplificaba artificialmente la señal de viento. El baseline honesto del sistema sin señal inflada es QWK≈-0.06 (Suiza) y QWK≈0.003 (La Parva). Se requiere v23 con recalibración de umbrales y re-entrenamiento de calibración para recuperar o superar el QWK de v21.
