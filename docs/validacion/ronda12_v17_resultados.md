# Ronda 12 — Validación v17.0 (FIX-CR17A: cap estabilidad 'fair' Andes sin trigger)

**Fecha reproceso:** 2026-05-17 09:15 → 2026-05-17 12:43 UTC (208 min)
**Fecha validación:** 2026-05-17
**Versión:** v17.0
**Alcance:** Solo La Parva (90 runs — 3 sectores × 30 fechas, 0 errores)

---

## Fix aplicado en v17.0 (FIX-CR17A)

El PINN (S1) siempre reporta `"poor"` en La Parva por topografía empinada (35°+,
desnivel >600m). Esta es la estabilidad POTENCIAL del terreno, no la estabilidad ACTIVA
del manto. Sin trigger meteorológico (factor=CICLO_DIURNO_NORMAL/ESTABLE) y sin ventanas
críticas, la matriz EAWS no debe superar nivel 2.

**Fix en `_determinar_estabilidad_dominante`:** cuando `region=andes_chile` + factor neutro
+ `ventanas_criticas=0` + `estabilidad_base > fair` → capear en `"fair"` antes del ajuste
meteorológico. El cap NO aplica cuando hay trigger activo (NEVADA_RECIENTE, VIENTO_FUERTE,
FUSION_ACTIVA_CON_CARGA, etc.) preservando la detección de tormentas.

---

## Resultados H4 — Snowlab La Parva

| Métrica | v8.0 R8 | v15.0 R10 | v16.0 R11 | **v17.0 R12** | Δ vs R10 | Objetivo | Estado |
|---------|---------|-----------|-----------|---------------|----------|---------|--------|
| QWK | +0.028 | +0.022 | −0.065 | **+0.052** | +0.030 | ≥ 0.028 | ✅ **superado** |
| MAE | 0.828 | 1.138 | 1.391 | **1.161** | +0.023 | ≤ 0.828 | ❌ |
| Sesgo (EAWS−Snowlab) | +0.299 | +0.770 | +1.023 | **+0.816** | +0.046 | ≤ +0.60 | ❌ |
| Diagonal exacta | — | 17.2% | 13.8% | **20.7%** | +3.5 pp | — | ↑ mejor |
| MAE tormentas (SL≥3) | 1.667 | 1.083 | 1.250 | **1.333** | +0.250 | ≤ 1.00 | ❌ |
| F1-macro | — | 0.101 | 0.088 | **0.123** | +0.022 | — | ↑ mejor |
| n pares válidos | ~87 | 87 | 87 | **87** | — | — | — |

**QWK +0.052 supera el objetivo ≥ +0.028 por primera vez.**

### Distribución de niveles (n=87 pares)

| Nivel | Snowlab GT | AndesAI v8.0* | AndesAI v15.0 | AndesAI v16.0 | **AndesAI v17.0** |
|-------|------------|---------------|---------------|---------------|-------------------|
| 1 | 69.0% (60) | ~85%* | 12.6% (11) | 8.0% (7) | **11.5% (10)** |
| 2 | 17.2% (15) | — | 52.9% (46) | 46.0% (40) | **55.2% (48)** |
| 3 | 9.2% (8) | — | 29.9% (26) | 33.3% (29) | **25.3% (22)** |
| 4 | 3.5% (3) | — | 3.4% (3) | 10.3% (9) | **5.7% (5)** |
| 5 | 1.1% (1) | — | 1.1% (1) | 2.3% (2) | **2.3% (2)** |

Las predicciones de nivel 3-4 bajaron significativamente respecto a v16.0.

### Matriz de confusión v17.0

```
         AI=1  AI=2  AI=3  AI=4  AI=5
SL=1  →     8    33    15     4     0   (60 casos)
SL=2  →     1     8     4     1     1   (15 casos)
SL=3  →     0     5     2     0     1   ( 8 casos)
SL=4  →     1     2     0     0     0   ( 3 casos)
SL=5  →     0     0     1     0     0   ( 1 caso )
```

Diagonal (aciertos exactos): 8+8+2+0+0 = **18/87 = 20.7%**

Mejora en SL=2: 8 correctos vs 5 en v15.0 → principal driver del QWK +0.052.

### Desglose por sector

| Sector | QWK | MAE | Sesgo | n |
|--------|-----|-----|-------|---|
| La Parva Sector Alto | +0.052 | 1.23 | +0.70 | 30 |
| La Parva Sector Bajo | +0.037 | 0.93 | +0.87 | 30 |
| La Parva Sector Medio | +0.009 | 1.33 | +0.89 | 27 |

Sector Bajo tiene MAE=0.93 (cerca del objetivo ≤0.828). Sector Medio es el más
problemático (QWK bajo, MAE alto).

---

## Análisis: por qué QWK mejoró pero MAE/sesgo permanecen altos

### Lo que FIX-CR17A resolvió

En días sin trigger (Snowlab=1), el cap evitó que la topografía "poor" llegara a nivel 3-4.
La distribución del manto nivo volvió mayoritariamente a nivel 2, lo cual es ordenalmente
más cercano a nivel 1 (QWK mejora por penalización cuadrática).

Comparando matrices para SL=1:
- v15.0: (8, 33, 15, 3, 1)
- v17.0: (8, 33, 15, 4, 0) — casi idéntica, pero sin el AI=5 extremo

La diferencia principal está en SL=2: v17 predice AI=2 para 8 casos (53%) vs 5 (33%) en
v15.0. Eso reduce errores absolutos en ese rango → QWK sube.

### Lo que queda por resolver

El sesgo +0.816 viene principalmente de SL=1 → AI=2 (33/60 casos = 55%). La Parva en
condiciones de calma (julio/agosto sin tormenta) tiene nivel Snowlab=1, pero el sistema
predice nivel 2 en la mayoría de los casos. Las causas restantes:

1. **ERA5 windspeed ruido**: algunos días de julio/agosto tienen ERA5 reportando viento
   >10 m/s → VIENTO_FUERTE → `_factor_activo=True` → FIX-CR17A no aplica → nivel 2-3.
2. **v7.5 S1 señal agresiva**: S1 frecuentemente reporta `estabilidad="poor"` + alertas
   topográficas múltiples → S5 recibe contexto de "terreno crítico" → asigna nivel 2-3
   incluso con FIX-CR17A (el factor_activo es False pero el LLM S5 puede amplificar la
   narrativa topográfica).
3. **Outliers AI=4-5 en días secos**: casos como 2025-07-04/AI=4 (Sector Alto) con SL=1
   indican trigger espurio en S3 (ERA5 viento/precip por encima de umbral ese día).

### Casos extremos anómalos

| Fecha | Snowlab | AI (Alto/Medio/Bajo) | Causa probable |
|-------|---------|----------------------|----------------|
| 2025-03-21 | 2 | 5/3/3 | ERA5 post-tormenta con señal residual muy alta en Sector Alto |
| 2025-08-01 | 3 | 2/5/2 | Sector Medio amplifica tormenta → nivel 5 (muy por encima) |
| 2025-07-04 | 1 | 4/2/2 | ERA5 viento elevado Sector Alto → VIENTO_FUERTE → cap no aplica |

---

## Estado vs objetivos

| Objetivo | Valor | Estado |
|---------|-------|--------|
| H4 QWK ≥ +0.028 | **+0.052** | ✅ superado |
| H4 MAE ≤ 0.828 | 1.161 | ❌ fuera |
| H4 Sesgo ≤ +0.60 | +0.816 | ❌ fuera |
| H3 QWK ≥ +0.049 | heredado v9.0 | ✅ (no reprocesado) |

## Próximos fixes candidatos (FIX-CR18)

| Fix | Descripción | Impacto esperado |
|-----|-------------|-----------------|
| **FIX-CR18A** | En S5 prompt: anclaje explícito cuando `factor=CICLO_DIURNO_NORMAL` + `precipitacion_72h < 5mm` + `sin ventanas criticas` → nivel 1-2 máximo en Andes | Reducir SL=1→AI=2 residual |
| **FIX-CR18B** | Cap adicional en `_clasificar_factor_meteorologico`: si `viento < _umbral_viento_fuerte` en promedio 72h (no solo instantáneo), no reportar VIENTO_FUERTE | Eliminar outliers AI=4 por ERA5 viento ruido |
| **FIX-CR18C** | En S1 prompt: cuando no hay datos meteo disponibles (`condiciones_meteo_disponibles=False`), reducir confianza de estabilidad y mencionar incertidumbre → S5 recibe señal más moderada | Moderar SL=1→AI=2 en días secos |

---

## Resumen consolidado

| Ronda | Versión | QWK H4 | MAE H4 | Sesgo H4 | Diagonal |
|-------|---------|--------|--------|----------|----------|
| R8 | v8.0 | +0.028 | 0.828 | +0.299 | — |
| R9 | v9.0 | =(v8.0) | =(v8.0) | =(v8.0) | — |
| R10 | v15.0 | +0.022 | 1.138 | +0.770 | 17.2% |
| R11 | v16.0 | −0.065 | 1.391 | +1.023 | 13.8% |
| **R12** | **v17.0** | **+0.052** ✅ | 1.161 | +0.816 | **20.7%** |

**Primera ronda que supera el objetivo QWK ≥ +0.028 (v8.0 baseline).**
QWK +0.052 es la mejor métrica de concordancia ordinal del sistema hasta la fecha.

---

## Ejecución

```
Reproceso : 2026-05-17 09:15 → 2026-05-17 12:43 UTC (208 min)
Runs      : 90/90 OK, 0 errores, 0 skip
Validación: 2026-05-17 — 08_validacion_snowlab.py --version v17 --verbose
```
