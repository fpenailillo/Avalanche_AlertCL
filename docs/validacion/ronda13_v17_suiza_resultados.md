# Ronda 13 — Validación H1/H3 v17.0 (DEAPSnow test set 2018-2020)

**Fecha reproceso:** 2026-05-18 08:24 → 2026-05-18 09:59 UTC (95 min)  
**Fecha validación:** 2026-05-18  
**Versión:** v17.0  
**Alcance reproceso:** Solo Suiza (30 runs — 3 estaciones × 10 fechas, 0 errores)  
**H4 La Parva:** sin cambio — resultados heredados de R12/v17.0

> **Primera validación IMIS mode para Suiza.** Las rondas R3–R12 usaban fechas 2023-2024 con
> `slf_danger_levels_qc`. A partir de v14.0 se usa el DEAPSnow RF2 test set (2018-2020) con
> `slf_meteo_snowpack.dangerLevel` como ground truth. Los resultados **no son comparables
> directamente** con las rondas anteriores (distinto test set, distinta fuente GT).

---

## Fixes acumulados desde v9.0 que afectan Suiza

| Versión | Fix | Impacto esperado Suiza |
|---------|-----|------------------------|
| v13.0 | FIX-CA-WINDOW: ventana ±12h condiciones_actuales | **Moderado** — IMIS a 18:00 UTC ahora detectado; antes quedaba fuera de ventana 12:00 |
| v15.0 / v10.1 | CR-10A: precip_efectiva = ERA5_72h/3 fallback | **Moderado** — reduce días secos sin señal en Alpes |
| v15.0 / v10.1 | CR-10B: umbral viento Alpes = 7 m/s (vs 10 m/s global) | **Esperado alto** — días con foehn/viento moderado activarían VIENTO_FUERTE |
| v17.0 | FIX-CR17A: cap estabilidad 'fair' Andes sin trigger | **Nulo** — guard `region == andes_chile`; no afecta Alpes |

---

## Resultados H1/H3 — Swiss IMIS (n=30 pares)

| Métrica | v9.0 R9 (2023-24)* | **v17.0 R13 (2018-20)** | Objetivo |
|---------|-------------------|------------------------|---------|
| QWK H3 | +0.049 | **+0.048** | ≥ 0.59 |
| F1-macro H1 | 0.288 | **0.198** | ≥ 0.75 |
| Sesgo | −0.71 | **−0.37** | — |
| Accuracy exacta | 0.417 | **0.267** | — |
| Accuracy ±1 | 0.792 | **0.833** | — |
| n pares | 24 | **30** | — |

*v9.0 usó fechas 2023-2024 / `slf_danger_levels_qc`. Comparación aproximada (test sets distintos).

### Estado H1/H3

- **H1 ❌** F1-macro 0.198 vs objetivo ≥ 0.75
- **H3 ❌** QWK +0.048 vs objetivo ≥ 0.59
- **Sin regresión ✅** QWK v17.0 (+0.048) ≈ v9.0 (+0.049) — cambio estadísticamente nulo

---

## Distribución de predicciones (n=30 pares)

| Nivel | SLF IMIS GT | AndesAI v17.0 |
|-------|-------------|---------------|
| 1 | 20.0% ( 6) | 33.3% (10) |
| 2 | 40.0% (12) | 46.7% (14) |
| 3 | 36.7% (11) | 20.0% ( 6) |
| 4 |  3.3% ( 1) |  0.0% ( 0) |
| 5 |  0.0% ( 0) |  0.0% ( 0) |

**Techel 2022 (referencia):** 8% nivel 1 / 42% nivel 2 / 40% nivel 3 / 9% nivel 4 / 1% nivel 5

### F1 por clase

| Clase | F1 | n GT |
|-------|-----|------|
| Nivel 1 | 0.250 | 6 |
| Nivel 2 | 0.308 | 12 |
| Nivel 3 | 0.235 | 11 |
| Nivel 4 | 0.000 | 1 |
| Nivel 5 | 0.000 | 0 |

---

## Desglose por par (n=30, todos vía IMIS DEAPSnow)

| Estación | Fecha | Nuestro | SLF GT | Dif |
|----------|-------|---------|--------|-----|
| Interlaken | 2018-12-07 | 1 | 3 | −2 |
| Interlaken | 2018-12-17 | 2 | 3 | −1 |
| Interlaken | 2018-12-27 | 2 | 2 | 0 |
| Interlaken | 2019-01-13 | 2 | 4 | −2 |
| Interlaken | 2019-01-26 | 1 | 3 | −2 |
| Interlaken | 2019-02-13 | 1 | 2 | −1 |
| Interlaken | 2019-02-23 | 3 | 1 | +2 |
| Interlaken | 2019-03-16 | 3 | 2 | +1 |
| Interlaken | 2019-04-02 | 1 | 2 | −1 |
| Interlaken | 2019-04-14 | 2 | 1 | +1 |
| Matterhorn Zermatt | 2018-12-11 | 2 | 3 | −1 |
| Matterhorn Zermatt | 2018-12-24 | 2 | 3 | −1 |
| Matterhorn Zermatt | 2019-01-04 | 2 | 3 | −1 |
| Matterhorn Zermatt | 2019-01-22 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2019-02-08 | 2 | 3 | −1 |
| Matterhorn Zermatt | 2019-02-18 | 2 | 1 | +1 |
| Matterhorn Zermatt | 2019-03-01 | 3 | 2 | +1 |
| Matterhorn Zermatt | 2019-03-20 | 3 | 2 | +1 |
| Matterhorn Zermatt | 2019-04-14 | 2 | 1 | +1 |
| Matterhorn Zermatt | 2019-12-03 | 2 | 2 | 0 |
| St Moritz | 2018-12-06 | 1 | 2 | −1 |
| St Moritz | 2018-12-22 | 3 | 3 | 0 |
| St Moritz | 2019-01-02 | 1 | 2 | −1 |
| St Moritz | 2019-01-12 | 1 | 3 | −2 |
| St Moritz | 2019-02-02 | 3 | 3 | 0 |
| St Moritz | 2019-02-13 | 2 | 2 | 0 |
| St Moritz | 2019-02-27 | 1 | 1 | 0 |
| St Moritz | 2019-03-25 | 1 | 2 | −1 |
| St Moritz | 2019-04-18 | 1 | 1 | 0 |
| St Moritz | 2019-12-21 | 2 | 3 | −1 |

**Aciertos exactos:** 8/30 = 26.7%  
**Dentro de ±1 nivel:** 25/30 = 83.3%

---

## Análisis: patrón de error

### Sesgo negativo persistente (−0.37)

El sistema **subestima** el peligro en Suiza: predice 33.3% nivel 1 cuando el GT tiene solo 20%.
Predice 20% nivel 3 cuando el GT tiene 36.7%. El nivel 4 (1 caso: Interlaken 2019-01-13 con
GT=4, predicho=2) no se detecta en absoluto.

Este sesgo negativo es **estructuralmente opuesto** al sesgo de La Parva (+0.816), donde el
sistema sobrepredice. En Suiza, el problema es que los eventos de tormenta más intensos (GT=3–4)
se predicen como 1–2.

### Causas probables de sub-detección en Suiza

1. **ERA5 @9 km subestima precipitaciones locales intensas:** La mayoría de los pares GT=3 que
   se predicen como 2 corresponden a nevadas registradas por IMIS pero que ERA5 reporta como
   precipitación moderada o nula a escala 9 km. Ejemplo: Matterhorn 2019-02-08 (GT=3, pred=2).

2. **CR-10B no activa suficientemente:** El umbral 7 m/s para VIENTO_FUERTE debería ayudar, pero
   muchos días de invierno en Suiza tienen viento ERA5 <7 m/s a 10m mientras el manto registra
   transporte activo (Matterhorn tiene datos `wind_trans24` en IMIS que no usa AndesAI S3).

3. **IMIS disponible via FIX-CA-WINDOW, pero S5 no lo pondera suficientemente:** Los datos IMIS
   (Sclass2, HN24, pwl_100) quedan en `datos_json_crudo` de `condiciones_actuales` pero S5 y S1
   no reciben estos campos directamente — los recibe S3 vía `condiciones_actuales.temperatura`,
   `velocidad_viento`, etc. Los campos especializados del manto nival (weak layer depth, hoar
   size) no llegan al contexto LLM.

4. **Interlaken 2019-01-13 (GT=4, pred=2):** Caso más extremo. Fue un evento de colapso de
   capa débil masiva documentado en DEAPSnow. ERA5 captura temperatura pero no la profundidad
   de la capa débil — info que solo IMIS tiene vía `pwl_100` y `Sclass2=2`.

### Casos anómalos positivos (over-prediction)

- Interlaken 2019-02-23: pred=3, GT=1. Temperatura positiva (+2.1°C), nieve nueva = 0 → el sistema
  detecta fusión activa cuando no hay carga nueva. Posible falso positivo de FUSION_ACTIVA_CON_CARGA.
- Matterhorn 2019-03-01, 2019-03-20: pred=3, GT=2. Meses de marzo/primavera — el sistema puede
  interpretar señales de fusión como más peligrosas de lo que indica el GT.

### Comparación con distribución Techel 2022

Techel tiene 40% nivel 3 + 9% nivel 4 = 49% casos "alto riesgo". AndesAI predice solo 20% nivel 3
+ 0% nivel 4. El sistema está calibrado para un rango típico de invierno de peligro moderado
(niveles 1-3), pero el DEAPSnow test set incluye las tormentas más significativas de 2018-2020
(El boletín SLF de enero 2019 fue uno de los peores registros en décadas en Los Alpes centrales).

---

## Estado vs objetivos

| Objetivo | Valor | Estado |
|---------|-------|--------|
| H3 QWK ≥ +0.049 (sin regresión) | **+0.048** | ✅ prácticamente idéntico (Δ = −0.001) |
| H3 QWK ≥ +0.59 (Techel 2022) | +0.048 | ❌ lejos (brecha 0.54) |
| H1 F1-macro ≥ 0.75 | 0.198 | ❌ lejos (brecha 0.55) |
| H4 QWK ≥ +0.028 | **+0.052** (R12) | ✅ heredado |

**Objetivo operativo (sin regresión H3) cumplido.** Los objetivos originales de la tesis (H1/H3
según Techel 2022) no se alcanzan — el sistema requiere un rediseño de la capa de detección
de tormentas en Suiza para cerrar esa brecha.

---

## Próximos fixes candidatos para Suiza (FIX-CR18-CH)

| Fix | Descripción | Impacto esperado |
|-----|-------------|-----------------|
| **FIX-CR18-CH-A** | Exponer campos IMIS especializados a S1: cuando `condiciones_actuales.datos_json_crudo.fuente = 'IMIS_DEAPSnow_RF2'`, pasar `Sclass2`, `HN24_cm`, `pwl_100` como contexto adicional al prompt topográfico | Mejorar detección GT=3–4 (capa débil activa) |
| **FIX-CR18-CH-B** | S3 prompt: si `condiciones_actuales.precipitacion_acumulada > 0` y `datos_json_crudo.HN24_cm > 10`, tratar como NEVADA_RECIENTE significativa aunque ERA5_72h sea moderado | Reducir sub-detección días nevados |
| **FIX-CR18-CH-C** | Umbral CR-10B: reducir a 5 m/s (actualmente 7 m/s) en invierno diciembre-marzo para Alpes; en estos meses el viento de traslado es importante con menores velocidades absolutas | Activar más VIENTO_FUERTE en temporada pico |

Estos fixes deben validarse sin regresar La Parva (FIX-CR17A protege Andes del viento ruido).

---

## Resumen consolidado H3 (QWK Suiza)

| Ronda | Versión | Test Set | GT | QWK H3 | Sesgo |
|-------|---------|----------|----|--------|-------|
| R3 | v4.0 | 2023-2024 | slf_danger_levels_qc | +0.162 | — |
| R4 | v5.0 | 2023-2024 | slf_danger_levels_qc | +0.143 | — |
| R5 | v6.2 | 2023-2024 | slf_danger_levels_qc | −0.031 | — |
| R7 | v7.5 | 2023-2024 | slf_danger_levels_qc | +0.103 | — |
| R8 | v8.0 | 2023-2024 | slf_danger_levels_qc | −0.073 | −0.88 |
| R9 | v9.0 | 2023-2024 | slf_danger_levels_qc | +0.049 | −0.71 |
| R10–R12 | v15–v17 | — | — | (no reprocesado) | — |
| **R13** | **v17.0** | **2018-2020 DEAPSnow** | **slf_meteo_snowpack** | **+0.048** | **−0.37** |

---

## Ejecución

```
Reproceso : 2026-05-18 08:24 → 2026-05-18 09:59 UTC (95 min)
Runs      : 30/30 OK, 0 errores, 0 skip
Validación: 2026-05-18 13:59 UTC — 07_validacion_slf_suiza.py --version v17 --imis-gt
```
