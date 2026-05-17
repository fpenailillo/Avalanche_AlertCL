# Ronda 11 — Validación v16.0 (FIX-CR16A: fallback precip_efectiva solo Alpes)

**Fecha reproceso:** 2026-05-16 17:14 → 2026-05-17 09:09 UTC (952 min)
**Fecha validación:** 2026-05-17
**Versión:** v16.0
**Alcance:** Solo La Parva (90 runs — 3 sectores × 30 fechas, 0 errores)

---

## Fix aplicado en v16.0 (FIX-CR16A)

En v15.0 (R10) se detectó sesgo +0.770 atribuido a CR-10A: el fallback
`precip_efectiva = precipitacion_72h/3` cuando `precipitacion_actual=0` se aplicaba
globalmente, generando `FUSION_ACTIVA_CON_CARGA` falsos en La Parva.

**Fix:** restringir el fallback a `_es_alpes=True`. En Andes Chile:
`precip_efectiva = precipitacion_actual_mm` (sin fallback, como pre-CR-10A v8.0).

---

## Resultados H4 — Snowlab La Parva

| Métrica | v8.0 R8 | v15.0 R10 | **v16.0 R11** | Δ vs R10 | Objetivo | Estado |
|---------|---------|-----------|---------------|----------|---------|--------|
| QWK | +0.028 | +0.022 | **−0.065** | −0.087 | ≥ 0.05 | ❌ regresión severa |
| MAE | 0.828 | 1.138 | **1.391** | +0.253 | ≤ 1.00 | ❌ |
| Sesgo (EAWS−Snowlab) | +0.299 | +0.770 | **+1.023** | +0.253 | ≤ +0.60 | ❌ |
| MAE tormentas (SL≥3) | 1.667 | 1.083 | **1.250** | +0.167 | ≤ 1.00 | ❌ retroceso |
| F1-macro | — | 0.101 | **0.088** | −0.013 | — | — |
| n pares válidos | ~87 | 87 | **87** | — | — | — |

### Distribución de niveles (n=87 pares)

| Nivel | Snowlab GT | AndesAI v15.0 | **AndesAI v16.0** | Δ |
|-------|------------|---------------|-------------------|---|
| 1 | 69.0% (60) | 12.6% (11) | **8.0% (7)** | −4.6 pp |
| 2 | 17.2% (15) | 52.9% (46) | **46.0% (40)** | −6.9 pp |
| 3 | 9.2% (8) | 29.9% (26) | **33.3% (29)** | +3.4 pp |
| 4 | 3.5% (3) | 3.4% (3) | **10.3% (9)** | +6.9 pp |
| 5 | 1.1% (1) | 1.1% (1) | **2.3% (2)** | +1.2 pp |

Las predicciones se desplazaron hacia niveles MÁS altos respecto a v15.0.

### Matriz de confusión v16.0

```
         AI=1  AI=2  AI=3  AI=4  AI=5
SL=1  →     5    26    21     6     2   (60 casos)
SL=2  →     2     5     6     2     0   (15 casos)
SL=3  →     0     5     2     1     0   ( 8 casos)
SL=4  →     0     3     0     0     0   ( 3 casos)
SL=5  →     0     1     0     0     0   ( 1 caso )
```

Diagonal (aciertos exactos): 5+5+2+0+0 = **12/87 = 13.8%** (vs 17.2% en v15.0)

### Desglose por sector

| Sector | QWK | MAE | Sesgo | n |
|--------|-----|-----|-------|---|
| La Parva Sector Alto | −0.178 | 1.37 | +0.77 | 30 |
| La Parva Sector Bajo | +0.022 | 1.20 | +1.13 | 30 |
| La Parva Sector Medio | −0.081 | 1.63 | +1.19 | 27 |

Sector Bajo tiene el mejor QWK pero el sesgo más alto (+1.13). Todos los sectores
empeoraron respecto a v15.0.

---

## Diagnóstico: FIX-CR16A produjo el efecto contrario al esperado

### Hipótesis original (incorrecta)

CR-10A fallback (`precip_efectiva = 72h/3`) → FUSION_ACTIVA_CON_CARGA → S5 asigna
nivel 2-3. Fix: `precip_efectiva = 0` en Andes → CICLO_DIURNO_NORMAL → S5 asigna
nivel 1-2.

### Efecto real observado

Con `precip_efectiva = 0`, S3 entrega señal meteorológica neutral (CICLO_DIURNO_NORMAL
o ESTABLE). S5 (integrador) recibe señal S3 débil y se apoya MÁS en S1 (topográfico),
que en La Parva siempre reporta factores de alto riesgo (PENDIENTE_CRITICA, DESNIVEL_
EXTENSO, etc.). El resultado es que S5 asigna niveles más altos cuando S3 es neutral.

**Paradoja:** la señal meteorológica moderada que antes moderaba (CICLO_DIURNO_NORMAL
vs ESTABLE) era suficiente para que S5 mantuviera niveles en 2. Al eliminarla,
S5 quedó más expuesto a la señal topográfica, que es inherentemente alta en La Parva.

### Implicación

CR-10A no es la causa de la regresión v8.0→v15.0. La causa real es probable que sea:

1. **v7.5 (causa principal):** S1 eliminó triggers meteo → S1 entrega estabilidad
   `"poor"/"fair"` con más frecuencia (sin moderación por ausencia de datos meteo).
   S5 recibe señal topográfica más agresiva → niveles más altos.

2. **Interacción S1-S5:** el prompt de S5 v10.1.0 no tiene lógica explícita para
   bajar el nivel cuando S3=ESTABLE y el historial (S4) indica temporada normal.

---

## Decisión: revertir FIX-CR16A → v15.5 (volver a baseline v15.0)

FIX-CR16A empeora todas las métricas. La solución correcta requiere:

| Fix | Descripción | Apunta a |
|-----|-------------|---------|
| **FIX-CR17A** | Revertir FIX-CR16A: restaurar fallback CR-10A global | Volver a v15.0 |
| **FIX-CR17B** | Reintroducir en S1 (v7.5): `if condiciones_meteo_disponibles=False → confianza_estabilidad "baja"` para que S5 descuente la señal topográfica | Abordar causa real |
| **FIX-CR17C** | En S5 prompt: cuando `factor_meteorologico = CICLO_DIURNO_NORMAL` + `precipitacion_72h < 5mm` + `no ventanas criticas activas` → anclar nivel ≤ 2 en Andes (excepto si S1 es "very_poor" y S4 confirma historial reciente) | Corregir integración |

Criterio de éxito v17.0:
- H4 QWK ≥ +0.028 (recuperar v8.0)
- H4 MAE ≤ 0.828
- H4 Sesgo ≤ +0.45
- H3 QWK ≥ +0.049 (sin regresión Suiza)

---

## Resumen consolidado

| Ronda | Versión | QWK H4 | MAE H4 | Sesgo H4 |
|-------|---------|--------|--------|----------|
| R8 | v8.0 | **+0.028** | **0.828** | **+0.299** |
| R9 | v9.0 | =(v8.0) | =(v8.0) | =(v8.0) |
| R10 | v15.0 | +0.022 | 1.138 | +0.770 |
| **R11** | **v16.0** | **−0.065** | **1.391** | **+1.023** |

**v8.0 sigue siendo el mejor punto para La Parva.**
**FIX-CR16A empeoró todas las métricas → revertir a v15.0 como base para v17.0.**

---

## Ejecución

```
Reproceso : 2026-05-16 17:14 → 2026-05-17 09:09 UTC (952 min)
Runs      : 90/90 OK, 0 errores, 0 skip
Validación: 2026-05-17 — 08_validacion_snowlab.py --version v16 --verbose
```
