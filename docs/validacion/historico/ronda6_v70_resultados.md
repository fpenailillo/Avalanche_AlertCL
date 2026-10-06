# Ronda 6 — Resultados Validación AndesAI v7.0

**Fecha:** 2026-05-08  
**Versión sistema:** v7.0 (VERSION_GLOBAL=7.0)  
**Reproceso:** 120 runs — ok=118 (92 nuevos + 26 skip v7.0), err=0 (2 reintentos 429 resueltos)  
**Duración reproceso:** ~10h (1 hang TCP eliminado manualmente, 2 reintentos rate-limit exitosos)  
**Branch:** `feat/v7.0-fixes`

---

## Fixes implementados en v7.0 (respecto a v6.2)

| Fix | Archivo(s) | Descripción |
|-----|-----------|-------------|
| **PRE-REQ** | `agentes/datos/constantes_zonas.py` | Centraliza zonas suizas (Interlaken, Matterhorn, St Moritz) + campo `region` en `METADATA_ZONAS` + helper `obtener_region()` |
| **FIX-GEO** | `tool_clasificar_eaws.py` | Cap `tamano≤3` (FIX-T v6.2) ahora condicional: solo en `region=='andes_chile'`. En Alpes el cap no aplica. |
| **FIX-H** | `tool_clasificar_eaws.py` (`_determinar_estabilidad_dominante`) | Default `estabilidad_satelital` cuando ViT=`sin_datos`: `'fair'` en Andes, `'poor'` en Alpes |
| **FIX-S1-SEMANTICA** | `prompts.py` (S1 + S5), `tool_clasificar_eaws.py`, `schema_boletines.json`, `almacenador.py` | EAWS 2025 Tabla 6 Paso 1: si S1 reporta `problema_avalancha_presente=false` → nivel 1 directo sin consultar la matriz |
| **Migración BQ** | `migrar_schema_boletines_v7.py` | Agrega campos `problema_avalancha_presente` (BOOL) y `tipo_problema_eaws` (STRING) a `climas.boletines_riesgo` |

---

## H1 y H3 — Validación Swiss SLF

**Script:** `notebooks_validacion/07_validacion_slf_suiza.py --version v7.0`  
**Ground truth:** `validacion_avalanchas.slf_danger_levels_qc`  
**Muestra:** n=24 pares (3 estaciones × 10 fechas, invierno 2023-2024)  
**Mapeo:** sector preciso (REQ-04): 16/24 vía sector_id exacto, 8/24 vía fallback cantón

### Métricas

| Métrica | v6.2 (R5) | v7.0 (R6) | Δ | Objetivo |
|---------|-----------|-----------|---|----------|
| QWK | −0.031 | **0.000** | +0.031 | ≥ 0.59 |
| F1-macro | 0.244 | **0.056** | −0.188 | ≥ 0.75 |
| Accuracy exacta | 0.333 | **0.125** | −0.208 | — |
| Accuracy ±1 | 0.750 | **0.667** | −0.083 | — |
| Sesgo medio | −0.75 | **−1.33** | −0.58 | — |

**H1 NO ALCANZADA** (F1=0.056, objetivo ≥ 0.75)  
**H3 NO ALCANZADA** (QWK=0.000, objetivo ≥ 0.59)

### Distribución de niveles (n=24)

| Nivel | SLF real | AndesAI v7.0 | AndesAI v6.2 |
|-------|----------|--------------|--------------|
| 1 | 12.5% | **100.0%** | 54.2% |
| 2 | 54.2% | **0.0%** | 33.3% |
| 3 | 20.8% | **0.0%** | 12.5% |
| 4 | 12.5% | **0.0%** | 0.0% |
| 5 | 0.0% | 0.0% | 0.0% |

### Interpretación

**Regresión severa**: el sistema predice nivel 1 en el 100% de los 24 pares (vs 54.2% en v6.2). El QWK mejoró de −0.031 a 0.000, pero F1-macro cayó de 0.244 a 0.056 y sesgo empeoró de −0.75 a −1.33.

**FIX-GEO operó correctamente** en las fechas donde S5 consultó la matriz EAWS (tamano sin cap en Alpes), pero **FIX-S1-SEMANTICA cortocircuitó el efecto** antes de llegar a la matriz: S1 reportó `problema_avalancha_presente=false` en el 100% de los runs, activando EAWS Paso 1 y produciendo nivel 1 directo. Véase la sección de diagnóstico.

---

## H4 — Validación Snowlab La Parva

**Script:** `notebooks_validacion/08_validacion_snowlab.py --version v7.0`  
**Ground truth:** `validacion_avalanchas.snowlab_boletines`  
**Muestra:** n=87 pares (3 sectores × 30 boletines, todos a ≤3 días)  
**Sectores:** La Parva Sector Alto, Bajo, Medio

### Métricas globales

| Métrica | v6.2 (R5) | v7.0 (R6) | Δ | Objetivo |
|---------|-----------|-----------|---|----------|
| QWK | −0.031 | **0.000** | +0.031 | ≥ 0.40 |
| MAE | 1.230 | **0.506** | −0.724 (−59%) | ≤ 1.00 ✓ |
| Sesgo (EAWS−Snowlab) | +0.885 | **−0.506** | −1.391 (invertido) | ≤ +0.60 |
| F1-macro | 0.145 | **0.163** | +0.018 | — |
| % nivel 1-2 | 58% | **100%** | +42pp | ≥ 65% ✓ |
| MAE tormentas (Snowlab≥3) | N/D | **2.417** | — | ≤ 1.00 ✗ |

**H4 NO ALCANZADA** (QWK=0.000, sesgo=−0.506 invertido)  
*MAE global cumplido (0.506 < 1.00) ✓ — pero por razón incorrecta (todo nivel 1)*  
*% nivel 1-2 cumplido (100%) ✓ — pero trivialmente (sistema colapsa a nivel 1)*  
*Constraint MAE tormentas VIOLADO (2.417 > 1.00) ✗*

### Métricas por sector

| Sector | n | MAE | Sesgo | QWK |
|--------|---|-----|-------|-----|
| La Parva Sector Alto | 30 | 0.67 | −0.67 | 0.000 |
| La Parva Sector Bajo | 30 | 0.27 | −0.27 | 0.000 |
| La Parva Sector Medio | 27 | 0.59 | −0.59 | 0.000 |

### Distribución de niveles (n=87)

| Nivel | Snowlab | AndesAI v7.0 | AndesAI v6.2 |
|-------|---------|--------------|--------------|
| 1 | 69% (60) | **100% (87)** | 15% (13) |
| 2 | 17% (15) | **0% (0)** | 43% (37) |
| 3 | 9% (8) | **0% (0)** | 32% (28) |
| 4 | 3% (3) | **0% (0)** | 9% (8) |
| 5 | 1% (1) | **0% (0)** | 1% (1) |

### Matriz de confusión v7.0

```
              AndesAI
          1   2   3   4   5
Snowlab 1 [60   0   0   0   0]  (60 casos, 69%)
        2 [15   0   0   0   0]  (15 casos, 17%)
        3 [ 8   0   0   0   0]  ( 8 casos,  9%)
        4 [ 3   0   0   0   0]  ( 3 casos,  3%)
        5 [ 1   0   0   0   0]  ( 1 caso,   1%)
```

---

## Diagnóstico de la regresión — Causa raíz

### CR-6 (nuevo): FIX-S1 se activa en el 100% de los runs retroactivos

```sql
SELECT problema_avalancha_presente, COUNT(*) AS n
FROM `climas-chileno.clima.boletines_riesgo`
WHERE STARTS_WITH(version_prompts, 'v7.0')
GROUP BY 1
-- Resultado: false=120, true=0
```

**Todos los 120 runs retroactivos tienen `problema_avalancha_presente=false`.**

S1 (Qwen3-80B) aplica correctamente la nueva sección del prompt: al no detectar precipitación reciente activa, viento fuerte con nieve disponible, ni anomalía SWE positiva en los datos retroactivos, reporta `no_distinct_avalanche_problem`. Esto activa el guard EAWS Paso 1 en S5, que retorna nivel 1 sin consultar la matriz.

### Por qué S1 nunca detecta trigger en retroactivos

Los datos retroactivos de validación (LaParva jun-sep 2024/2025; Alpes dic 2023 - abr 2024) llegan a través de BigQuery histórico. La consulta a condiciones actuales (`obtener_condiciones_actuales_meteo`) retorna **0 filas** para fechas históricas en la mayoría de los casos, y la tendencia 72h muestra `ESTABLE` o `CICLO_DIURNO_NORMAL`. Con esos factores neutros, S1 concluye correctamente que no hay trigger activo — pero el ground truth Snowlab registra niveles 2-5 en el 31% de los pares.

### Desacoplamiento conceptual

La hipótesis de FIX-S1 era válida en principio: días calmos reales → nivel 1 EAWS. El problema es que **la señal meteorológica retroactiva es insuficiente para distinguir días calmos de días con actividad de avalanchas**. S1 no puede inferir "lluvia sobre nieve el 15 julio 2024" desde datos meteorológicos históricos con resolución de varios días. El sistema dice "no hay trigger detectable" cuando en realidad el trigger existió pero ya no es observable con la arquitectura actual de datos.

### Comparación de dirección del sesgo

| Versión | Sesgo H4 | Interpretación |
|---------|----------|----------------|
| v5.0 | +1.609 | Sistema sobre-predice (siempre alto) |
| v6.2 | +0.885 | Sobre-predicción reducida pero persistente |
| **v7.0** | **−0.506** | **Sistema sub-predice (siempre nivel 1)** |

v7.0 invirtió el sesgo. Matemáticamente el MAE global mejoró (0.506 vs 1.230) porque el 69% de los días son realmente nivel 1, pero el QWK sigue en 0 y el constraint MAE tormentas se viola (2.417).

---

## Análisis por fix: ¿qué funcionó?

| Fix | Efecto observado | Veredicto |
|-----|-----------------|-----------|
| **FIX-GEO** | Tamano sin cap en Alpes — confirmado en código y BQ (`fuente_tamano_eaws` no tiene `cap_calmo` para Alpes). Pero FIX-S1 cortocircuita antes de la matriz, por lo que el efecto en métricas no es visible. | ✅ Implementado correctamente — efecto no medible en Ronda 6 |
| **FIX-H** | Default `'poor'` en Alpes cuando sat=sin_datos — confirmado en logs. Igualmente cortocircuitado por FIX-S1. | ✅ Implementado correctamente — efecto no medible en Ronda 6 |
| **FIX-S1-SEMANTICA** | Activa en 100% de runs retroactivos → nivel 1 universal. Intención correcta (EAWS Paso 1); implementación correcta; **premisa incorrecta**: datos retroactivos no tienen resolución suficiente para detectar triggers activos. | ⚠️ Implementado correctamente, premisa no válida para datos retroactivos |

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
| **6** | **v7.0** | **0.000** | **0.056** | **0.125** | **0.667** | **−1.33** |
| Ref. | Techel 2022 | 0.590 | 0.550 | 0.640 | 0.950 | — |

### H4 — Snowlab La Parva

| Ronda | Versión | QWK | MAE | Sesgo | F1-macro | % niv 1-2 |
|-------|---------|-----|-----|-------|----------|-----------|
| 2 | v3.2 | −0.016 | 2.103 | +1.989 | 0.104 | ~5% |
| 3 | v4.0 | −0.006 | 2.138 | +2.023 | 0.030 | ~0% |
| 4 | v5.0 | −0.000 | 1.724 | +1.609 | 0.084 | 21% |
| 5 | v6.2 | −0.031 | 1.230 | +0.885 | 0.145 | 58% |
| **6** | **v7.0** | **0.000** | **0.506** | **−0.506** | **0.163** | **100%** |
| Objetivo | — | ≥ 0.40 | ≤ 1.00 | ≤ +0.60 | — | ≥ 65% |

---

## Causas raíz residuales actualizadas

| ID | Descripción | Estado v7.0 |
|----|-------------|-------------|
| CR-1 | `tamano` topográfico Andes sobreestima nivel en días calmos | ✅ Resuelto (FIX-GEO aplica FIX-T solo en Andes) |
| CR-4 | Sin ViT en invierno alpino → `estabilidad_satelital` subestima H1/H3 | ✅ Resuelto (FIX-H default 'poor' en Alpes) — efecto no medible en R6 |
| CR-5 | Gap distribucional: Snowlab 69% nivel 1 vs AndesAI v6.2 15% nivel 1 | ⚠️ Invertido: v7.0 predice 100% nivel 1 |
| **CR-6 nuevo** | **FIX-S1 siempre activa EAWS Paso 1 en retroactivos** — datos históricos no tienen resolución suficiente para detectar triggers activos | 🔴 Nueva causa raíz introducida en v7.0 |

---

## Recomendaciones para v7.5

### Corrección prioritaria: calibrar FIX-S1 para datos retroactivos

FIX-S1-SEMANTICA es conceptualmente correcto pero necesita una condición de activación más robusta. Dos opciones:

**Opción A — Umbral de confianza en S1** (menor intrusión):
Modificar el prompt de S1 para que solo reporte `problema_avalancha_presente=false` cuando tenga datos meteorológicos con confianza suficiente. Si `datos_meteorologicos_ok=false` → no emitir el campo (dejar `None`, que activa el path retrocompatible en la tool).

**Opción B — Guardia adicional en S5 basada en datos disponibles** (más robusto):
En `ejecutar_clasificar_riesgo_eaws_integrado`, activar EAWS Paso 1 solo cuando `datos_meteorologicos_ok=True` AND `problema_avalancha_presente is False`. Si no hay datos meteo recientes, continuar con el path estándar.

La Opción B es preferible: añade una condición en `tool_clasificar_eaws.py` sin tocar prompts, y mantiene el comportamiento correcto en producción (donde `datos_meteorologicos_ok` es casi siempre `True`).

### Para FIX-GEO y FIX-H

Ambos fixes son correctos y permanecen para v7.5. Para medir su efecto aislado, se puede diseñar un experimento sin FIX-S1 (desactivando el guard `problema_avalancha_presente is False`) y reprocesar solo las 30 fechas suizas.

### Datos adicionales para H4

Investigar por qué el 31% de los pares Snowlab muestran niveles 2-5 en fechas que el sistema ve como calmas. Opciones:
- Añadir consulta a ERA5 histórico para precipitación 72h previa a la fecha de validación
- Usar `WeatherNext2` (disponible desde 2026-05-05) para retroalimentar datos históricos

---

*Generado desde sesión Claude Code 2026-05-08. Datos fuente en BigQuery `climas-chileno.clima.boletines_riesgo` (version_prompts STARTS_WITH 'v7.0').*  
*Reproceso: PID 15977, log `/tmp/reproceso_v70.log`.*
