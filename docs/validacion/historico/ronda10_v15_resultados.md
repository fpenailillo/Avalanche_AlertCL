# Ronda 10 — Validación v15.0 (WeatherNext 2 + acumulado v10.x/v13.x)

**Fecha reproceso:** 2026-05-15 → 2026-05-16  
**Fecha validación:** 2026-05-16  
**Versión:** v15.0  
**Alcance:** Solo La Parva (90 runs — 3 sectores × 30 fechas, 0 errores)  
**H1/H3 Suiza:** heredados de v9.0 (no reprocesados — fixes v10.x/v13.x son Alpes-específicos)

---

## Fixes acumulados desde v8.0 (última ronda con reproceso La Parva)

| Versión | Fix | Impacto real La Parva |
|---------|-----|-----------------------|
| v7.5 | S1: eliminados triggers meteo; S5 determina EAWS Paso 1 | **Alto** — S1 ya no modera con señales meteo → integrador recibe señal topográfica más agresiva |
| v10.1 | CR-10A+CR-10B: calibración ERA5 regional Alpes (precip 72h, viento 7m/s) | **Probable culpable** — umbrales del integrador ajustados; afecta La Parva aunque diseñados para Alpes |
| v13.0 | FIX-CA-WINDOW: ventana ±12h condiciones_actuales | Nulo — La Parva sin IMIS |
| v15.0 | WN2 tool (disponible=False para fechas 2024-2025) | Nulo para histórico |

---

## Resultados H4 — Snowlab La Parva

| Métrica | v8.0 R8 | **v15.0 R10** | Δ | Objetivo | Estado |
|---------|---------|---------------|---|---------|--------|
| QWK | +0.028 | **+0.022** | −0.006 | ≥ 0.05 | ❌ regresión leve |
| MAE | 0.828 | **1.138** | +0.310 | ≤ 1.00 | ❌ |
| Sesgo (EAWS−Snowlab) | +0.299 | **+0.770** | +0.471 | ≤ +0.60 | ❌ |
| % nivel 1-2 AndesAI | 85.1% | **65.5%** | −19.6 pp | ≥ 65% | ⚠️ límite |
| MAE tormentas (SL≥3) | 1.667 | **1.083** | −0.584 | ≤ 1.00 | ⚠️ mejora, aún fuera |
| F1-macro | — | **0.101** | — | — | — |
| Accuracy exacta | — | **17.2%** | — | — | — |
| Kappa lineal | — | **−0.044** | — | — | — |
| n pares válidos | ~87 | **87** | — | — | — |

### Distribución de niveles (n=87 pares)

| Nivel | Snowlab GT | AndesAI v8.0* | **AndesAI v15.0** |
|-------|------------|---------------|-------------------|
| 1 | 69.0% (60) | ~85%* | **12.6% (11)** |
| 2 | 17.2% (15) | — | **52.9% (46)** |
| 3 | 9.2% (8) | — | **29.9% (26)** |
| 4 | 3.5% (3) | — | **3.4% (3)** |
| 5 | 1.1% (1) | — | **1.1% (1)** |

*v8.0 distribución estimada: 85.1% nivel 1-2 según R8.

### Matriz de confusión v15.0

```
         AI=1  AI=2  AI=3  AI=4  AI=5
SL=1  →     8    33    15     3     1   (60 casos)
SL=2  →     3     5     7     0     0   (15 casos)
SL=3  →     0     6     2     0     0   ( 8 casos)
SL=4  →     0     1     2     0     0   ( 3 casos)
SL=5  →     0     1     0     0     0   ( 1 caso )
```

Diagonal (aciertos exactos): 8+5+2+0+0 = **15/87 = 17.2%**

### Desglose por sector

| Sector | QWK | MAE | Sesgo | n |
|--------|-----|-----|-------|---|
| La Parva Sector Alto | −0.143 | 1.33 | +0.73 | 30 |
| La Parva Sector Bajo | +0.043 | 1.03 | +0.97 | 30 |
| La Parva Sector Medio | +0.219 | 1.04 | +0.59 | 27 |

Sector Medio tiene el mejor QWK (+0.219) y sesgo dentro del objetivo (+0.59). Sector Alto es el más problemático (QWK negativo, MAE 1.33).

---

## Diagnóstico de la regresión

### Patrón dominante: sobreestimación sistemática (sesgo +0.770)

El sistema predice nivel 2-3 en casos donde Snowlab dice nivel 1. De 60 casos Snowlab=1:
- Solo 8 predichos correctamente como nivel 1 (13%)
- 33 predichos como nivel 2 (55%)
- 15 predichos como nivel 3 (25%)

La sobreestimación se concentra en períodos sin eventos de tormenta (julio–agosto 2024 y 2025):
- 2024-07-12, 07-26, 08-16: Snowlab=1,1,1 → AndesAI=3,3,3 (los tres sectores)
- 2025-07-04, 07-11, 07-18, 07-25, 08-08, 08-15: misma cadena

### Causa probable: CR-10A/B con efecto global no esperado

CR-10A/B ajustó los umbrales del integrador (v10.1) para calibrar ERA5 regional en Alpes. Sin embargo, el integrador no distingue región en sus umbrales internos: los mismos umbrales ajustados para Alpes (`precip_efectiva_72h`, `umbral_viento_7ms`) se aplican también a La Parva, donde ERA5 tiene sesgos húmedos distintos.

Evidencia: el sesgo pasó de +0.299 (v8.0) a +0.770 (v15.0), un aumento de +0.471 — consistente con un integrador que ahora "ve" más precipitación relevante en los mismos datos ERA5 de La Parva.

### Contribución de v7.5 (S1 sin triggers meteo)

Al eliminar los triggers meteo en S1, el subagente topográfico entrega señales de estabilidad `"poor"/"fair"` más frecuentes sin la moderación que antes introducía la ausencia de datos meteo. Esto alimenta al integrador con inputs de mayor riesgo.

---

## Plan de corrección — v16.0 (FIX-CR16)

| Fix | Descripción | Impacto esperado |
|-----|-------------|-----------------|
| **FIX-CR16A** | Regionalizar umbrales CR-10A/B en integrador: `if region == "alpes_suiza"` → umbrales actuales; `if region == "andes_chile"` → umbrales v8.0 originales | Reducir sesgo La Parva de +0.770 → ~+0.30 |
| **FIX-CR16B** | Revisar prompt S1 v7.5: reintroducir modulación de confianza cuando `condiciones_meteo_disponibles=False` para que el integrador reciba señal de incertidumbre | Reducir overestimación en períodos sin eventos |

Criterio de éxito v16.0:
- H4 QWK ≥ +0.028 (recuperar v8.0)
- H4 MAE ≤ 0.828 (recuperar v8.0)
- H4 Sesgo ≤ +0.45
- Sin regresión H3 (QWK ≥ +0.049)

---

## Punto positivo: MAE tormentas mejoró

A pesar de la regresión global, la métrica de eventos de tormenta (Snowlab ≥ 3, n=12) mejoró:
- v8.0: MAE tormentas = **1.667**
- v15.0: MAE tormentas = **1.083** (−0.584, mejora real)

El sistema detecta mejor los eventos de alto riesgo. El problema es la sobreestimación en condiciones normales.

---

## Resultados H1/H3 — Swiss SLF (heredados de v9.0)

| Métrica | v9.0 R9 | v15.0 (heredado) | Objetivo |
|---------|---------|-----------------|---------|
| QWK H3 | +0.049 | +0.049 | ≥ 0.59 ❌ |
| F1-macro H1 | 0.288 | 0.288 | ≥ 0.75 ❌ |

---

## Análisis WN2 shadow (producción)

WeatherNext 2 activo en producción desde 2026-05-15. Para fechas históricas (2024-2025) retornó `disponible=False` en todos los runs — sin impacto en métricas. El análisis de impacto real será con runs de producción:

```sql
SELECT DATE(fecha_emision), nombre_ubicacion, wn2_avalanche_problem, wn2_confianza, nivel_eaws_24h
FROM `climas-chileno.clima.boletines_riesgo`
WHERE STARTS_WITH(version_prompts, 'v15') AND wn2_avalanche_problem IS NOT NULL
ORDER BY fecha_emision DESC LIMIT 20
```

---

## Resumen consolidado

| Ronda | Versión | QWK H3 | QWK H4 | MAE H4 | Sesgo H4 |
|-------|---------|--------|--------|--------|----------|
| R3 | v4.0 | +0.162 | −0.006 | 2.138 | +2.023 |
| R4 | v5.0 | +0.143 | −0.000 | 1.724 | +1.609 |
| R5 | v6.2 | −0.031 | −0.031 | 1.230 | +0.885 |
| R7 | v7.5 | +0.103 | −0.139 | 1.448 | +1.011 |
| R8 | v8.0 | −0.073 | **+0.028** | **0.828** | **+0.299** |
| R9 | v9.0 | +0.049 | =(v8.0) | =(v8.0) | =(v8.0) |
| **R10** | **v15.0** | **(her. v9.0)** | **+0.022** | **1.138** | **+0.770** |

**v8.0 sigue siendo el mejor punto para La Parva.** La cadena v10.x introdujo regresión.  
**Próximo paso: FIX-CR16A (regionalizar umbrales integrador) → Ronda 11.**

---

## Ejecución

```
Reproceso : 2026-05-15 23:46 → 2026-05-16 17:19 UTC (521 min + latencia Databricks)
Runs      : 90/90 OK, 0 errores (40 skip + 50 nuevos)
Validación: 2026-05-16 — 08_validacion_snowlab.py --version v15 --verbose
```
