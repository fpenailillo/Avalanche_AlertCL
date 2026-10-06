# Ronda 8 — Resultados v8.0 (FIX-CR7A + FIX-CR7B + FIX-CR7C)

**Fecha:** 2026-05-11  
**Versión prompts:** v8.0  
**Reproceso:** 120 runs (64 skip ya v8.0 + 56 nuevos) — 0 errores  
**Duración reproceso:** ~13.8h (2 cuelgues TCP en runs 94+95; resto ~90s/run)

---

## Resumen ejecutivo

Los tres fixes CR-7 mejoraron significativamente H4 (La Parva / Snowlab):
- **MAE H4: 1.448 → 0.828** ✅ objetivo ≤ 1.00 alcanzado
- **Sesgo H4: +1.011 → +0.299** ✅ objetivo ≤ +0.60 alcanzado
- **% nivel 1-2 H4: 52% → 85.1%** ✅ objetivo ≥ 65% alcanzado
- **QWK H4: -0.139 → +0.028** — mejora sustancial pero NO alcanzó objetivo ≥ 0.05

Sin embargo se detectó **regresión en H1/H3** (estaciones suizas):
- **QWK H3: +0.103 → -0.073** ❌ retrocedió por debajo del umbral de mantenimiento ≥ +0.10

---

## Resultados H1 — F1-macro clasificación EAWS (Suiza)

| Métrica | v7.5 (R7) | v8.0 (R8) | Objetivo | Estado |
|---------|-----------|-----------|----------|--------|
| F1-macro | — | 0.1556 | ≥ 0.75 | ❌ |
| Accuracy exacta | — | 0.250 | — | — |
| Accuracy ±1 | — | 0.708 | — | — |
| Sesgo medio | — | −0.88 | — | subestima |
| n | 24 | 24 | — | — |

Distribución de niveles (n=24):

| Nivel | SLF (%) | AndesAI v8.0 (%) |
|-------|---------|------------------|
| 1 | 12.5 | 62.5 |
| 2 | 54.2 | 29.2 |
| 3 | 20.8 | 8.3 |
| 4 | 12.5 | 0.0 |

**Diagnóstico:** AndesAI subestima sistemáticamente para estaciones suizas — 62.5% de predicciones en nivel 1 versus 12.5% en ground truth SLF. El sistema no captura los triggers meteorológicos alpinos europeos (acumulación persistente, capas débiles de facetas) que SLF detecta en niveles 3-4.

---

## Resultados H3 — Comparación con Techel et al. (2022)

| Métrica | Techel 2022 | AndesAI v7.5 | AndesAI v8.0 | Objetivo | Estado |
|---------|-------------|--------------|--------------|----------|--------|
| Accuracy exacta | 0.640 | — | 0.250 | — | — |
| Accuracy ±1 | 0.950 | — | 0.708 | — | — |
| F1-macro | 0.550 | — | 0.156 | — | — |
| **QWK** | **0.590** | **+0.103** | **−0.073** | ≥ 0.590 | **❌ regresión** |

**Diagnóstico de la regresión:** FIX-CR7A endureció `condiciones_meteo_disponibles=False` para inputs ERA5 retroactivos, pero las estaciones suizas (Interlaken, Matterhorn, St Moritz) también usan ERA5 como fuente. En v7.5, S5 pasaba `condiciones_meteo_disponibles=True` con datos ERA5 → la matrix EAWS (no EAWS Paso 1) daba niveles 2-3 en ciertos casos. Con v8.0, el mismo cambio que corrige H4 fuerza niveles más bajos para Suiza también.

---

## Resultados H4 — Validación Snowlab La Parva

| Métrica | v7.5 (R7) | v8.0 (R8) | Objetivo | Estado |
|---------|-----------|-----------|----------|--------|
| **QWK** | −0.139 | **+0.028** | ≥ 0.05 | ❌ (near-miss) |
| **MAE** | 1.448 | **0.828** | ≤ 1.00 | **✅** |
| **Sesgo** | +1.011 | **+0.299** | ≤ +0.60 | **✅** |
| **% nivel 1-2** | 52% | **85.1%** | ≥ 65% | **✅** |
| MAE tormentas | 1.500 | 1.667 | ≤ 1.00 | ❌ regresión |
| n | 90 | 87 | — | — |

Distribución de niveles H4 (n=87):

| Nivel | Snowlab (%) | AndesAI v7.5 (%) | AndesAI v8.0 (%) |
|-------|-------------|------------------|------------------|
| 1 | 69.0 | ~48 | 34.5 |
| 2 | 17.2 | ~38 | 50.6 |
| 3 | 9.2 | ~11 | 14.9 |
| 4 | 3.4 | ~3 | 0.0 |

Resultados por sector v8.0:

| Sector | n | MAE | Sesgo | QWK |
|--------|---|-----|-------|-----|
| La Parva Sector Alto | 30 | 1.00 | +0.00 | −0.147 |
| La Parva Sector Bajo | 30 | 0.70 | +0.63 | +0.056 |
| La Parva Sector Medio | 27 | 0.78 | +0.26 | +0.246 |

**Diagnóstico:** FIX-CR7A/B/C redujo el sesgo de +1.011 a +0.299 y el MAE de 1.448 a 0.828 — mejora clara en calibración. Pero el QWK de +0.028 no alcanzó el umbral ≥ 0.05. La distribución pasó de sobre-estimar (v7.5: sesgo +1.0) a una distribución más equilibrada. El sector Alto sigue negativo (−0.147) mientras Medio mejoró a +0.246.

**MAE tormentas:** Los 12 eventos con Snowlab ≥ 3 tienen MAE = 1.667 (todos subpredichos con sesgo −1.667), sugiriendo que el sistema sigue siendo incapaz de capturar tormentas de alta intensidad.

---

## Comparativa de versiones (H4 Snowlab)

| Versión | QWK | MAE | Sesgo | % niv1-2 |
|---------|-----|-----|-------|----------|
| v5.0 | −0.000 | ~1.6 | +1.609 | — |
| v6.2 | — | — | — | — |
| v7.5 | −0.139 | 1.448 | +1.011 | 52% |
| **v8.0** | **+0.028** | **0.828** | **+0.299** | **85%** |

---

## Balance objetivos v8.0

| Hipótesis | Métrica | Objetivo | v8.0 | Estado |
|-----------|---------|----------|------|--------|
| H1 | F1-macro (Suiza) | ≥ 0.75 | 0.156 | ❌ |
| H3 | QWK (Suiza) | ≥ 0.59 | −0.073 | ❌ regresión |
| H4 | QWK (Snowlab) | ≥ 0.05 | +0.028 | ❌ near-miss |
| H4 | MAE (Snowlab) | ≤ 1.00 | 0.828 | ✅ |
| H4 | Sesgo (Snowlab) | ≤ +0.60 | +0.299 | ✅ |
| H4 | % nivel 1-2 | ≥ 65% | 85.1% | ✅ |
| H4 | MAE tormentas | ≤ 1.00 | 1.667 | ❌ |
| H3 mant. | QWK no regresión | ≥ +0.10 | −0.073 | ❌ |

---

## Diagnóstico para v9.0

### Problema principal: trade-off H3/H4 por FIX-CR7A

FIX-CR7A mejoró H4 (corrigió sobrepredicción en La Parva) pero causó regresión H3 (subestimación en Suiza). El cambio `condiciones_meteo_disponibles` afecta tanto runs retroactivos de La Parva (sin mediciones reales) como runs suizos (con ERA5 disponible pero no "mediciones del momento").

**Opciones para v9.0:**
1. **Diferenciar por región:** `condiciones_meteo_disponibles=True` para estaciones con datos ERA5 de alta resolución (Suiza), `False` para La Parva retroactivo sin datos de estación.
2. **Usar tabla `condiciones_actuales` explícitamente:** Verificar en S3 si la tabla tiene registros reales para la fecha/ubicación — no depender de la interpretación de S5.
3. **Calibración separada:** Calibrar los umbrales EAWS Paso 1 por región (Alpes vs Andes).

### Problema secundario: MAE tormentas H4 = 1.667

Los 12 eventos Snowlab ≥ 3 tienen sesgo −1.667 (todos subpredichos). El sistema no detecta correctamente condiciones de tormenta intensa retroactivas en La Parva. Posible causa: ERA5 retroactivo subestima precipitación de nieve en eventos convectivos de verano austral.

---

## Archivos de resultados

- `/tmp/validacion_slf_suiza.json` — detalle H1/H3 pares individuales
- `/tmp/validacion_snowlab_v80.log` — output completo H4
- `/tmp/reproceso_v80_r2.log` — log del reproceso (120 runs)
