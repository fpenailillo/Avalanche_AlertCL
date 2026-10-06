# Ronda 14 — Validación H1/H3 Suiza v18.0 (FIX-CR18-CH-1/2/3)

**Fecha ejecución:** 2026-05-18/19  
**Versión:** v18.0  
**GT:** IMIS DEAPSnow RF2 2018-2020 (`slf_meteo_snowpack.dangerLevel`)  
**n:** 29/30 (St Moritz 2018-12-06 timeout en reproceso — reintento en curso)

## Cambios v18.0 respecto a v17.0

- **FIX-CR18-CH-1** (prompts.py S5): S5 ya no intenta llamar `obtener_condiciones_actuales_meteo` (no registrada en S5); lee `condiciones_meteo_disponibles` del contexto de S3. Añade instrucción explícita de pasar siempre `viento_kmh`.
- **FIX-CR18-CH-2** (tool_clasificar_eaws.py): umbral `ventanas_criticas ≥ 2` para boost frecuencia en Alpes + NEVADA_RECIENTE (vs ≥ 3 global). No afecta Andes Chile.
- **FIX-CR18-CH-3** (tool_clasificar_eaws.py): tamaño mínimo 3 en Alpes con NEVADA_RECIENTE + ≥ 2 ventanas (tormenta masiva D3+). No afecta Andes Chile.

## Resultados H1/H3

### Comparativa v17.0 → v18.0

| Métrica | v17.0 (n=30) | v18.0 (n=29) | Delta | Objetivo |
|---------|-------------|-------------|-------|----------|
| QWK | 0.048 | **0.152** | **+0.104** ✅ | ≥ 0.100 mejora |
| F1-macro | 0.198 | **0.264** | **+0.066** | ≥ 0.250 |
| Acc exacta | 0.333 | **0.379** | +0.046 | — |
| Acc ±1 | 0.833 | **0.862** | +0.029 | — |
| Sesgo medio | -0.37 | -0.48 | -0.11 ⚠️ | reducir |

### vs Techel (2022)

| Métrica | Techel 2022 | AndesAI v18.0 | Estado |
|---------|-------------|---------------|--------|
| QWK | 0.59 | 0.152 | ❌ (gap 0.44) |
| F1-macro | 0.55 | 0.264 | ❌ |
| Acc exacta | 0.64 | 0.379 | ❌ |
| Acc ±1 | 0.95 | 0.862 | — |

### Distribución de niveles

| Nivel | SLF GT (%) | AndesAI v18 (%) | v17.0 (%) |
|-------|-----------|-----------------|-----------|
| 1 | 20.7% | 31.0% | — |
| 2 | 37.9% | **62.1%** | — |
| 3 | 37.9% | 6.9% | — |
| 4 | 3.4% | 0.0% | — |
| 5 | 0.0% | 0.0% | — |

## Tabla detallada de predicciones (29 pares)

| Estación | Fecha | AndesAI | SLF GT | Dif |
|----------|-------|---------|--------|-----|
| Interlaken | 2018-12-07 | 1 | 3 | -2 |
| Interlaken | 2018-12-17 | 1 | 3 | -2 |
| Interlaken | 2018-12-27 | 2 | 2 | 0 |
| Interlaken | 2019-01-13 | 2 | 4 | -2 |
| Interlaken | 2019-01-26 | **3** | 3 | **0** ✅ |
| Interlaken | 2019-02-13 | 2 | 2 | 0 |
| Interlaken | 2019-02-23 | 1 | 1 | 0 |
| Interlaken | 2019-03-16 | 1 | 2 | -1 |
| Interlaken | 2019-04-02 | 2 | 2 | 0 |
| Interlaken | 2019-04-14 | 1 | 1 | 0 |
| Matterhorn Zermatt | 2018-12-11 | 2 | 3 | -1 |
| Matterhorn Zermatt | 2018-12-24 | 2 | 3 | -1 |
| Matterhorn Zermatt | 2019-01-04 | 2 | 3 | -1 |
| Matterhorn Zermatt | 2019-01-22 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2019-02-08 | 2 | 3 | -1 |
| Matterhorn Zermatt | 2019-02-18 | 2 | 1 | +1 |
| Matterhorn Zermatt | 2019-03-01 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2019-03-20 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2019-04-14 | 2 | 1 | +1 |
| Matterhorn Zermatt | 2019-12-03 | 2 | 2 | 0 |
| St Moritz | 2018-12-06 | — | — | timeout* |
| St Moritz | 2018-12-22 | 1 | 3 | -2 |
| St Moritz | 2019-01-02 | 1 | 2 | -1 |
| St Moritz | 2019-01-12 | 2 | 3 | -1 |
| St Moritz | 2019-02-02 | **3** | 3 | **0** ✅ |
| St Moritz | 2019-02-13 | 1 | 2 | -1 |
| St Moritz | 2019-02-27 | 2 | 1 | +1 |
| St Moritz | 2019-03-25 | 1 | 2 | -1 |
| St Moritz | 2019-04-18 | 2 | 1 | +1 |
| St Moritz | 2019-12-21 | 2 | 3 | -1 |

*St Moritz 2018-12-06: timeout (480s) en reproceso principal; reintento en curso.

## Análisis de resultados

### Mejora confirmada vs v17.0

Los tres fixes producen una mejora real: QWK +0.104 (0.048 → 0.152). La mejora proviene principalmente de:
- CH-1: `condiciones_meteo_disponibles` y `viento_kmh` ahora se pasan correctamente a S5 → S5 ya no falla silenciosamente al intentar llamar una tool no registrada.
- CH-2/CH-3: en casos con NEVADA_RECIENTE + ≥2 ventanas críticas, la frecuencia sube y el tamaño se fuerza a 3 → nivel 3 en lugar de 2.

Ejemplo: Interlaken 2019-01-26 y St Moritz 2019-02-02 ahora predicen correctamente nivel=3.

### Underestimación persistente

El sistema sigue concentrando predicciones en nivel 2 (62.1% vs GT 37.9%). Las causas estructurales no resueltas:

1. **ERA5 @9km subestima precipitación local**: Las estaciones suizas están en valles y bajo influencia orográfica fuerte. ERA5 promedia sobre 9km → precipitaciones reales 2-3× mayores.
2. **ventanas_criticas_detectadas variabilidad LLM**: El LLM (Qwen3-80B) extrae `num_ventanas_criticas` del output de `detectar_ventanas_criticas` con variabilidad run-to-run. En el caso Interlaken 2019-01-13 (GT=4), el run de validación dio ventanas=1 (vs ventanas=2 en otro run), impidiendo activar CH-2/CH-3.
3. **Sin datos Sclass2/pwl_100 en contexto S5**: La capa de debilidad persistente (capa hundida, temperatura cruza, escarcha de profundidad) no llega al contexto de S5 → no puede ajustar estabilidad a poor/very_poor independientemente del meteo.

### Caso límite: Interlaken 2019-01-13 (GT=4, pred=2)

El peor miss del dataset. A pesar de que IMIS reporta HN24=47.9cm (tormenta masiva), ERA5 subestima y el LLM extrae ventanas=1 en este run. CH-2/CH-3 requieren ventanas≥2 y no se activan. La matriz `poor + a_few + 2` da nivel=2.

## Próximos pasos

1. **Completar run faltante**: St Moritz 2018-12-06 (reintento en curso).
2. **Verificar H4 sin regresión**: `08_validacion_snowlab.py --version v18` — guards `region=andes_chile` protegen La Parva.
3. **Análisis causa raíz profundo**: diagnosticar por qué ERA5 subestima tan fuertemente en estas fechas específicas (¿sesgo orográfico sistemático?).
4. **Potencial FIX-CR19**: si el análisis confirma sesgo ERA5 sistemático, considerar corrección orográfica más agresiva para `alpes_swiss` (actualmente usa `correccion_orografica` pero puede ser insuficiente).
