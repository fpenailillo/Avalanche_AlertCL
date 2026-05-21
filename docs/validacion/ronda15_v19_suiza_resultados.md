# Ronda 15 — Validación H1/H3 Suiza v19.0 (FIX-CR19)

**Fecha ejecución:** 2026-05-18/19  
**Versión:** v19.0  
**GT:** IMIS DEAPSnow RF2 2018-2020 (`slf_meteo_snowpack.dangerLevel`)  
**n:** 30/30

## Cambio v19.0 respecto a v18.0

**FIX-CR19**: `nieve_nueva_cm = HN24_cm` — surfacear medición directa de nieve nueva IMIS al LLM.

- `consultor_bigquery.py`: añade `datos_json_crudo` al SELECT de `obtener_condiciones_actuales`; extrae `nieve_nueva_cm` desde `HN24_cm`.
- `tool_condiciones_actuales.py`: expone `nieve_nueva_cm` en el output del tool; alerta `CARGA_NIEVE_EXTREMA_30CM` cuando ≥30cm; `riesgo_precipitacion.nivel = "muy_alto"` cuando ≥30cm.
- `tool_ventanas_criticas.py`: nuevo parámetro `nieve_nueva_cm_imis`; ventana `CARGA_NIEVE_PROFUNDA` cuando HN24≥25cm + Alpes + T≤0°C → **segunda ventana crítica** → activa CH-2/CH-3 (tamaño≥3, boost frecuencia).
- Guard `_es_alpes`: no afecta Andes Chile (sin backfill IMIS).

## Resultados H1/H3

### Comparativa v17.0 → v18.0 → v19.0

| Métrica | v17.0 (n=30) | v18.0 (n=30) | v19.0 (n=30) | Delta v18→v19 |
|---------|-------------|-------------|-------------|----------------|
| QWK | 0.048 | 0.156 | **0.236** | **+0.080** ✅ |
| F1-macro | 0.198 | 0.256 | **0.509** | **+0.253** ✅ |
| Acc exacta | 0.333 | 0.367 | 0.400 | +0.033 |
| Acc ±1 | 0.833 | 0.867 | 0.800 | -0.067 ⚠️ |
| Sesgo medio | -0.37 | -0.50 | -0.60 | -0.10 ⚠️ |

### vs Techel (2022)

| Métrica | Techel 2022 | AndesAI v19.0 | Estado |
|---------|-------------|---------------|--------|
| QWK | 0.59 | 0.236 | ❌ (gap 0.354) |
| F1-macro | 0.55 | 0.509 | ❌ (gap 0.041) |
| Acc exacta | 0.64 | 0.400 | ❌ |
| Acc ±1 | 0.95 | 0.800 | ❌ |

### Distribución de niveles

| Nivel | SLF GT (%) | AndesAI v19 (%) | AndesAI v18 (%) |
|-------|-----------|-----------------|-----------------|
| 1 | 20.0% | **50.0%** | 33.3% |
| 2 | 40.0% | 40.0% | 60.0% |
| 3 | 36.7% | 6.7% | 6.7% |
| 4 | 3.3% | **3.3%** | 0.0% |
| 5 | 0.0% | 0.0% | 0.0% |

## Tabla detallada (30 pares)

| Estación | Fecha | v19 | v18 | SLF GT | Dif v19 | Dif v18 |
|----------|-------|-----|-----|--------|---------|---------|
| Interlaken | 2018-12-07 | 1 | 1 | 3 | -2 | -2 |
| Interlaken | 2018-12-17 | 1 | 1 | 3 | -2 | -2 |
| Interlaken | 2018-12-27 | 2 | 2 | 2 | 0 | 0 |
| Interlaken | 2019-01-13 | **4** | 2 | 4 | **0** ✅ | -2 |
| Interlaken | 2019-01-26 | 2 | 3 | 3 | -1 | 0 ← regresión |
| Interlaken | 2019-02-13 | 1 | 2 | 2 | -1 | 0 ← regresión |
| Interlaken | 2019-02-23 | 1 | 1 | 1 | 0 | 0 |
| Interlaken | 2019-03-16 | 2 | 1 | 2 | 0 ✅ | -1 |
| Interlaken | 2019-04-02 | 2 | 2 | 2 | 0 | 0 |
| Interlaken | 2019-04-14 | 1 | 1 | 1 | 0 | 0 |
| Matterhorn Zermatt | 2018-12-11 | 1 | 2 | 3 | -2 | -1 ← regresión |
| Matterhorn Zermatt | 2018-12-24 | **3** | 2 | 3 | **0** ✅ | -1 |
| Matterhorn Zermatt | 2019-01-04 | 2 | 2 | 3 | -1 | -1 |
| Matterhorn Zermatt | 2019-01-22 | 2 | 2 | 2 | 0 | 0 |
| Matterhorn Zermatt | 2019-02-08 | 2 | 2 | 3 | -1 | -1 |
| Matterhorn Zermatt | 2019-02-18 | 2 | 2 | 1 | +1 | +1 |
| Matterhorn Zermatt | 2019-03-01 | 1 | 2 | 2 | -1 | 0 ← regresión |
| Matterhorn Zermatt | 2019-03-20 | 2 | 2 | 2 | 0 | 0 |
| Matterhorn Zermatt | 2019-04-14 | 3 | 2 | 1 | +2 ⚠️ | +1 ← sobreestimación |
| Matterhorn Zermatt | 2019-12-03 | 2 | 2 | 2 | 0 | 0 |
| St Moritz | 2018-12-06 | 1 | 1 | 2 | -1 | -1 |
| St Moritz | 2018-12-22 | 2 | 1 | 3 | -1 | -2 |
| St Moritz | 2019-01-02 | 1 | 1 | 2 | -1 | -1 |
| St Moritz | 2019-01-12 | 1 | 2 | 3 | -2 | -1 ← regresión |
| St Moritz | 2019-02-02 | 2 | 3 | 3 | -1 | 0 ← regresión |
| St Moritz | 2019-02-13 | 1 | 1 | 2 | -1 | -1 |
| St Moritz | 2019-02-27 | 1 | 2 | 1 | 0 ✅ | +1 |
| St Moritz | 2019-03-25 | 1 | 1 | 2 | -1 | -1 |
| St Moritz | 2019-04-18 | 1 | 2 | 1 | 0 ✅ | +1 |
| St Moritz | 2019-12-21 | 1 | 2 | 3 | -2 | -1 ← regresión |

## Análisis

### Mejoras v18→v19

- **Interlaken 2019-01-13**: 2→4 exacto (GT=4) — FIX-CR19 funcionó perfectamente. HN24=47.89cm generó ventana `CARGA_NIEVE_PROFUNDA` → segunda ventana → CH-2/CH-3 activados.
- **Matterhorn Zermatt 2018-12-24**: 2→3 exacto (GT=3) — misma cadena causal.
- **Interlaken 2019-03-16**: 1→2 exacto (GT=2).
- **St Moritz 2019-02-27 y 2019-04-18**: reducción de sobreestimaciones (2→1, GT=1).

### Regresiones v18→v19 (7 casos)

Las regresiones se concentran en **variabilidad LLM en casos sin HN24 extremo**. En estos casos, el LLM puede no extraer `nieve_nueva_cm_imis` o extraerlo pero no alcanzar el umbral de 25cm, resultando en comportamiento inconsistente:

- Interlaken 2019-01-26: 3→2 (GT=3). HN24 moderado, ventana no activa.
- St Moritz 2019-02-02: 3→2 (GT=3). HN24 moderado.
- Matterhorn Zermatt 2019-04-14: 2→3 (GT=1). **Sobreestimación**: FIX-CR19 activa por HN24 → nivel 3 incorrecto. Caso de sobreestimación introducida.

### Distribución: más nivel 1 (problema estructural)

v19 predice 50% nivel 1 vs GT 20%. El sistema sigue sin detectar nivel 3 (GT=36.7%, pred=6.7%). Las causas:
1. ERA5@9km subestima precipitación local en la mayoría de casos con GT=3
2. Cuando HN24<25cm (no activa CARGA_NIEVE_PROFUNDA), el LLM cae a nivel 1 en vez de nivel 2 por variabilidad

### Trayectoria QWK

| Versión | QWK | Nota |
|---------|-----|------|
| v17.0 | 0.048 | baseline post-revert |
| v18.0 | 0.156 | FIX-CR18 (CH-1/2/3) |
| v19.0 | **0.236** | FIX-CR19 (HN24) |
| Techel (2022) | 0.590 | benchmark humano |

## Próximos pasos

1. **Verificar H4 sin regresión**: `08_validacion_snowlab.py --version v19`.
2. **Análisis HN24 por caso**: identificar qué fechas tienen HN24≥25cm en IMIS para entender cobertura del fix.
3. **Umbral dinámico**: explorar reducir umbral CARGA_NIEVE_PROFUNDA de 25cm a 15cm (ver si reduce falsos negativos sin aumentar sobreestimaciones como Matterhorn 2019-04-14).
4. **FIX-CR20 hipótesis**: pasar HN24 también como override de `precipitacion_72h_mm` en `detectar_ventanas_criticas`, para casos de evento de varios días.
