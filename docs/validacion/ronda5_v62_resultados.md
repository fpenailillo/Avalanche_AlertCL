# Ronda 5 — Resultados Validación AndesAI v6.2

**Fecha:** 2026-05-03  
**Versión sistema:** v6.2 (VERSION_GLOBAL=6.2)  
**Reproceso:** 120 runs — ok=30, skip=90, err=0  
**Duración reproceso:** ~100 min (2 TCP hangs resueltos por reintentos automáticos)

---

## Fixes implementados en v6.2 (respecto a v5.0)

| Fix | Archivo | Descripción |
|-----|---------|-------------|
| FIX-T | `tool_clasificar_eaws.py` | Cap `tamano≤3` cuando `estado_pinn=ESTABLE` y `ventanas_criticas<2`; fix bug integer/string en `_determinar_tamano()` |
| FIX-V | `tool_ventanas_criticas.py` | Excluir `DIA_ALTO_RIESGO_PRONOSTICADO` del contador de ventanas para bump frecuencia EAWS |
| FIX-D | `prompts.py` (S5 integrador) | Instrucción explícita de pasar SIEMPRE `dias_consecutivos_nivel_bajo` aunque sea 0 |
| FIX-S3 | `prompts.py` (S3 meteorológico) + `orquestador/prompts.py` | Template salida: `FUSION_ACTIVA` legacy → `FUSION_ACTIVA_CON_CARGA\|CICLO_DIURNO_NORMAL` |
| FIX-HIST | `consultor_bigquery.py` | Bug: `QueryJobConfig` object pasado como `list` a `_ejecutar_query()` → historial siempre 0 → REQ-01 nunca activaba |
| FIX-STORE | `almacenador.py` | Retorno temprano ante streaming buffer BQ sin campo `guardado_bigquery` → reproceso reportaba ERROR |
| FIX-TIMEOUT | `cliente_llm.py` | `httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0))` explícito; antes TCP podía colgarse 30+ min |

---

## H1 y H3 — Validación Swiss SLF

**Script:** `notebooks_validacion/07_validacion_slf_suiza.py --version v6.2`  
**Ground truth:** `validacion_avalanchas.slf_danger_levels_qc`  
**Muestra:** n=24 pares (3 estaciones × 10 fechas, invierno 2023-2024)  
**Mapeo:** sector preciso (REQ-04): 16/24 vía sector_id exacto, 8/24 vía fallback cantón

### Métricas

| Métrica | v5.0 (R4) | v6.2 (R5) | Δ | Objetivo |
|---------|-----------|-----------|---|----------|
| QWK | +0.143 | **−0.031** | −0.174 | ≥ 0.59 |
| F1-macro | 0.235 | **0.244** | +0.009 | ≥ 0.75 |
| Accuracy exacta | 0.292 | **0.333** | +0.041 | — |
| Accuracy ±1 | 0.833 | **0.750** | −0.083 | — |
| Sesgo medio | −0.67 | **−0.75** | −0.08 | — |

**H1 NO ALCANZADA** (F1=0.244, objetivo ≥ 0.75)  
**H3 NO ALCANZADA** (QWK=−0.031, objetivo ≥ 0.59)

### Distribución de niveles (n=24)

| Nivel | SLF real | AndesAI v6.2 | AndesAI v5.0 |
|-------|----------|--------------|--------------|
| 1 | 12.5% | **54.2%** | 41.7% |
| 2 | 54.2% | **33.3%** | 45.8% |
| 3 | 20.8% | **12.5%** | 8.3% |
| 4 | 12.5% | **0.0%** | 4.2% |
| 5 | 0.0% | 0.0% | 0.0% |

### Tabla de predicciones vs SLF

| Estación | Fecha | AndesAI | SLF | Dif | Vía |
|----------|-------|---------|-----|-----|-----|
| Interlaken | 2023-12-01 | 1 | 4 | −3 | preciso |
| Interlaken | 2023-12-15 | 1 | 3 | −2 | preciso |
| Interlaken | 2024-01-01 | 2 | 3 | −1 | preciso |
| Interlaken | 2024-01-15 | 2 | 2 | 0 | preciso |
| Interlaken | 2024-02-01 | 2 | 2 | 0 | fallback_canton |
| Interlaken | 2024-02-15 | 2 | 2 | 0 | fallback_canton |
| Interlaken | 2024-03-01 | 3 | 3 | 0 | preciso |
| Interlaken | 2024-03-15 | 2 | 2 | 0 | fallback_canton |
| Interlaken | 2024-04-01 | 2 | 3 | −1 | preciso |
| Interlaken | 2024-04-15 | 1 | 1 | 0 | fallback_canton |
| Matterhorn Zermatt | 2023-12-01 | 1 | 3 | −2 | preciso |
| Matterhorn Zermatt | 2024-01-01 | 1 | 2 | −1 | fallback_canton |
| Matterhorn Zermatt | 2024-02-01 | 1 | 2 | −1 | fallback_canton |
| Matterhorn Zermatt | 2024-02-15 | 3 | 2 | +1 | preciso |
| Matterhorn Zermatt | 2024-03-01 | 2 | 2 | 0 | fallback_canton |
| Matterhorn Zermatt | 2024-03-15 | 1 | 2 | −1 | preciso |
| Matterhorn Zermatt | 2024-04-01 | 2 | 4 | −2 | preciso |
| St Moritz | 2024-01-01 | 1 | 2 | −1 | preciso |
| St Moritz | 2024-01-15 | 1 | 2 | −1 | preciso |
| St Moritz | 2024-02-01 | 3 | 1 | +2 | preciso |
| St Moritz | 2024-02-15 | 1 | 2 | −1 | preciso |
| St Moritz | 2024-03-15 | 1 | 2 | −1 | fallback_canton |
| St Moritz | 2024-04-01 | 1 | 4 | −3 | preciso |
| St Moritz | 2024-04-15 | 1 | 1 | 0 | preciso |

### Interpretación

La regresión en QWK (−0.174) se debe al efecto colateral de FIX-T: al captar `tamano≤3` cuando `estado_pinn=ESTABLE`, el sistema predice niveles más bajos. En La Parva esto es correcto (topografía extrema justificaba el cap), pero en los Alpes suizos el terreno es menos extremo y el cap produce subestimación adicional. La distribución resultante (54.2% nivel 1) se aleja aún más del ground truth SLF (12.5% nivel 1).

Causa raíz: **CR-4 — gap de dominio Andes→Alpes** no resuelto. FIX-H (pendiente) aborda parcialmente este gap.

---

## H4 — Validación Snowlab La Parva

**Script:** `notebooks_validacion/08_validacion_snowlab.py --version v6.2`  
**Ground truth:** `validacion_avalanchas.snowlab_boletines`  
**Muestra:** n=87 pares (3 sectores × 30 boletines, todos a ≤3 días)  
**Sectores:** La Parva Sector Alto, Bajo, Medio

### Métricas globales

| Métrica | v5.0 (R4) | v6.2 (R5) | Δ | Objetivo |
|---------|-----------|-----------|---|----------|
| QWK | −0.000 | **−0.031** | −0.031 | ≥ 0.40 |
| MAE | 1.724 | **1.230** | −0.494 (−29%) | — |
| Sesgo (EAWS−Snowlab) | +1.609 | **+0.885** | −0.724 (−45%) | ≤ +0.80 |
| F1-macro | 0.084 | **0.145** | +0.061 | — |
| % nivel 1-2 | 21% | **58%** | +37pp | ≥ 30% ✓ |

**H4 NO ALCANZADA** (QWK=−0.031, sesgo=+0.885)  
*% nivel 1-2 cumplido (58% > objetivo 30%)*

### Métricas por sector

| Sector | n | MAE | Sesgo | QWK |
|--------|---|-----|-------|-----|
| La Parva Sector Alto | 30 | 1.27 | +0.80 | −0.067 |
| La Parva Sector Bajo | 30 | 1.00 | +0.87 | −0.040 |
| La Parva Sector Medio | 27 | 1.44 | +1.00 | −0.065 |

### Distribución de niveles (n=87)

| Nivel | Snowlab | AndesAI v6.2 | AndesAI v5.0 |
|-------|---------|--------------|--------------|
| 1 | 69% (60) | **15% (13)** | 0% (0) |
| 2 | 17% (15) | **43% (37)** | 21% (19) |
| 3 | 9% (8) | **32% (28)** | 62% (54) |
| 4 | 3% (3) | **9% (8)** | 17% (15) |
| 5 | 1% (1) | **1% (1)** | 0% (0) |

### Matriz de confusión v6.2

```
                AndesAI
          1    2    3    4    5
Snowlab 1 [10   24   17    8    1]  (60 casos, 69%)
        2 [ 3    6    6    0    0]  (15 casos, 17%)
        3 [ 0    4    4    0    0]  ( 8 casos,  9%)
        4 [ 0    2    1    0    0]  ( 3 casos,  3%)
        5 [ 0    1    0    0    0]  ( 1 caso,   1%)
```

### Interpretación

**FIX-T fue el cambio más impactante:** el piso matemático de nivel 3 fue eliminado. AndesAI ahora emite nivel 1 en 15% de los boletines (vs 0% en v5.0). La distribución nivel 1-2 pasó de 21% a 58%, superando el objetivo del 30%.

**Gap distribucional persistente:** Snowlab clasifica el 69% de los días como nivel 1. AndesAI solo alcanza el 15%. Este gap impide que el QWK sea positivo independientemente de los demás fixes. Causas posibles:
- Metodología EAWS local de Snowlab más conservadora en invierno andino
- Topografía de La Parva (desnivel ≈1000m, zona inicio ≈510ha) fuerza niveles 2-3 incluso en condiciones calmas
- FIX-T cap `tamano≤3` no suficiente — en muchos días `ventanas_criticas≥1` sigue produciendo nivel 2-3

---

## Progresión histórica completa

### H1/H3 — Swiss SLF

| Ronda | Versión | QWK | F1-macro | Acc exacta | Acc ±1 | Sesgo |
|-------|---------|-----|----------|------------|--------|-------|
| 1 | v3.0 (sin satélite) | −0.056 | 0.197 | — | 0.708 | −0.79 |
| 2 | v3.2 (mapeo cantón) | +0.109 | 0.191 | 0.250 | 0.750 | −0.54 |
| 2b | v3.2 (sector preciso) | +0.016 | 0.161 | 0.208 | 0.750 | −0.50 |
| 3 | v4.0 | +0.162 | 0.155 | 0.250 | 0.792 | −0.92 |
| 4 | v5.0 | +0.143 | 0.235 | 0.292 | 0.833 | −0.67 |
| **5** | **v6.2** | **−0.031** | **0.244** | **0.333** | **0.750** | **−0.75** |
| Ref. | Techel 2022 | 0.590 | 0.550 | 0.640 | 0.950 | — |

### H4 — Snowlab La Parva

| Ronda | Versión | QWK | MAE | Sesgo | F1-macro | % niv 1-2 |
|-------|---------|-----|-----|-------|----------|-----------|
| 2 | v3.2 | −0.016 | 2.103 | +1.989 | 0.104 | ~5% |
| 3 | v4.0 | −0.006 | 2.138 | +2.023 | 0.030 | ~0% |
| 4 | v5.0 | −0.000 | 1.724 | +1.609 | 0.084 | 21% |
| **5** | **v6.2** | **−0.031** | **1.230** | **+0.885** | **0.145** | **58%** |
| Objetivo | — | ≥ 0.40 | — | ≤ +0.80 | — | ≥ 30% |

---

## Causas raíz residuales

| ID | Descripción | Estado |
|----|-------------|--------|
| CR-1 residual | `tamano` de La Parva sigue siendo alto (FIX-T capó a 3 pero ventanas≥1 produce nivel 2-3) | Parcialmente resuelto |
| CR-4 | Sin ViT en invierno alpino → `estabilidad_satelital=fair` → subestimación H1/H3 | Pendiente FIX-H |
| CR-5 nuevo | Distribución Snowlab: 69% nivel 1 (metodología conservadora o sesgo de temporada) | Requiere investigación |

---

## Próximos pasos — v7.0

1. **FIX-H** — `estabilidad_satelital='poor'` por defecto cuando ViT retorna `sin_datos` en coordenadas europeas; mejorará H1/H3 sin afectar H4
2. **Ajuste tamano regional** — factor geográfico Andes/Alpes para `tamano_eaws`; diferencia estructural entre dominios
3. **Investigar distribución Snowlab** — ¿metodología EAWS local más conservadora? ¿sesgo de temporada 2024-2025?
4. **Reprocesar Ronda 6** con v7.0

---

*Generado automáticamente desde sesión Claude Code 2026-05-03. Datos fuente en BigQuery `climas-chileno.clima.boletines_riesgo` (version_prompts STARTS_WITH 'v6.2').*
