# Resultados de Validación — AndesAI Sistema Multi-Agente

**Proyecto:** Tesis Doctoral MTI UTFSM — Francisco Peñailillo M.
**Sistema:** AndesAI, predicción de riesgo de avalanchas EAWS (5 subagentes)
**Última actualización:** 2026-05-02 (Ronda 4 — v5.0)

---

## Resumen de hipótesis

| Hipótesis | Descripción | Objetivo | v4.0 (R3) | v5.0 (R4) | Estado |
|-----------|-------------|----------|-----------|-----------|--------|
| H1 | F1-macro ≥ 75% en clasificación EAWS vs SLF Suiza | F1 ≥ 0.75 | 0.155 | 0.235 | ✗ No alcanzada |
| H3 | QWK comparable a Techel et al. (2022) | QWK ≥ 0.59 | +0.162 | +0.143 | ✗ No alcanzada |
| H4 sesgo | Sesgo La Parva ≤ +0.80 | Sesgo ≤ +0.80 | +2.023 | +1.609 | ✗ No alcanzada |
| H4 QWK | QWK ≥ 0.40 vs Snowlab La Parva | QWK ≥ 0.40 | −0.006 | −0.000 | ✗ No alcanzada |

---

## H1 y H3 — Validación Swiss SLF

**Script:** `notebooks_validacion/07_validacion_slf_suiza.py`
**Ground truth:** `validacion_avalanchas.slf_danger_levels_qc` (SLF Suiza 2001-2024)
**Muestra:** n=24 pares emparejados (3 estaciones × 10 fechas invierno 2023-2024)
**Mapeo:** sector geográfico preciso REQ-04 (sector_id exacto + fallback cantón modal)

### Progresión por rondas

| Ronda | Versión | QWK | F1-macro | Acc exacta | Acc ±1 | Sesgo |
|-------|---------|-----|----------|------------|--------|-------|
| 1 | v3.0 (sin satélite) | −0.056 | 0.197 | — | 0.708 | −0.79 |
| 2 | v3.2 (con satélite, mapeo cantón) | +0.109 | 0.191 | 0.250 | 0.750 | −0.54 |
| 2b | v3.2 (con satélite, sector preciso) | +0.016 | 0.161 | 0.208 | 0.750 | −0.50 |
| 3 | v4.0 (REQs implementados) | +0.162 | 0.155 | 0.250 | 0.792 | −0.92 |
| **4** | **v5.0 (REQ-03 Alpes, REQ-06 diurno)** | **+0.143** | **0.235** | **0.292** | **0.833** | **−0.67** |
| Ref. | Techel et al. 2022 | 0.590 | 0.550 | 0.640 | 0.950 | — |

### Distribución de niveles predichos vs reales

| Nivel | SLF real (%) | AndesAI v5.0 R4 (%) | AndesAI v4.0 R3 (%) | AndesAI v3.2 (%) |
|-------|-------------|---------------------|---------------------|------------------|
| 1 | 12.5 | 41.7 | 62.5 | 45.8 |
| 2 | 54.2 | 45.8 | 33.3 | 29.2 |
| 3 | 20.8 | 8.3 | 4.2 | 20.8 |
| 4 | 12.5 | 4.2 | 0.0 | 4.2 |
| 5 | 0.0 | 0.0 | 0.0 | 0.0 |

*REQ-03 fix (factor=1.0 Alpes) redujo la sobre-emisión de nivel 1 de 62.5% → 41.7%, acercando la distribución al ground truth SLF. Sesgo mejoró −0.92 → −0.67.*

### Análisis de mejoras entre rondas

**Ronda 1 → Ronda 2:** QWK −0.056 → +0.109 (+0.165). Los datos satelitales (NDSI, ERA5, SAR en `imagenes_satelitales`) son el driver principal.

**Ronda 2 → Ronda 3:** QWK +0.016 → +0.162 (+0.146). Las señales MODIS LST y SAR humedad (REQ-02a/02b) enriquecen el contexto satelital de S2.

**Ronda 3 → Ronda 4 (mixto):** F1 +0.155 → +0.235 (+0.080, mejora), QWK +0.162 → +0.143 (−0.019, leve regresión), Sesgo −0.92 → −0.67 (+0.25, mejora esperada). REQ-03 fix eliminó la penalización orográfica andina en los Alpes, distribuyendo niveles con menos sesgo. La leve regresión en QWK es consistente con la mejora en F1: la distribución se volvió menos concentrada en nivel 1, produciendo errores de ±1 en casos intermedios.

**Regresión de sesgo Ronda 3 (−0.50 → −0.92):** REQ-03 aplica corrección orográfica ERA5 calibrada para Andes (reduce precipitación 15-35% según altitud). En los Alpes el régimen orográfico es diferente → la reducción penalizaba la señal meteorológica → el modelo predecía demasiado conservador en Europa. Resuelto en Ronda 4 con factor=1.0 para coordenadas europeas.

### Causa raíz — gap de dominio Andes→Alpes

El sistema fue calibrado en topografía andina (PINN, ViT, parámetros EAWS para Andes). En los Alpes suizos:
- Los sectores SLF tienen niveles 2-4 en condiciones que en Andes serían nivel 1-2
- El PINN usa métricas topográficas de La Parva/Valle Nevado; la fricción y cohesión en granito alpino difieren de la roca volcánica andina
- ERA5 @9km subrepresenta la orografía alpina más compleja

→ H1 y H3 rechazadas. Resultado publicable: cuantifica el gap de transferencia de dominio entre sistemas montañosos.

**Causa raíz residual (CR-4):** En invierno alpino con cobertura nubosa frecuente no hay datos ópticos ViT → `estabilidad_satelital` cae a `fair` por defecto. El SLF reporta niveles 3-4 en condiciones que AndesAI clasifica con estabilidad `fair`. Fix propuesto (FIX-H): asignar `estabilidad_satelital='poor'` cuando el ViT retorna `sin_datos` en coordenadas europeas (alineado con praxis SLF de asumir peor caso sin datos).

---

## H4 — Validación Snowlab La Parva

**Script:** `notebooks_validacion/08_validacion_snowlab.py`
**Ground truth:** `validacion_avalanchas.snowlab_boletines` (30 boletines, Domingo Valdivieso Ducci L2 CAA)
**Muestra:** n=87 pares (3 sectores × 30 boletines, 85/87 a ≤3 días de distancia)

### Progresión por rondas

| Ronda | Versión | QWK | MAE | Sesgo | F1-macro |
|-------|---------|-----|-----|-------|----------|
| 2 | v3.2 | −0.016 | 2.103 | +1.989 | 0.104 |
| 3 | v4.0 | −0.006 | 2.138 | +2.023 | 0.030 |
| **4** | **v5.0 (REQ-06, REQ-01)** | **−0.000** | **1.724** | **+1.609** | **0.084** |
| Objetivo | — | ≥ 0.40 | — | ≤ +0.80 | — |

*Mejoras Ronda 4: MAE −0.414 (−19%), Sesgo −0.414 (−20%), F1 +0.054. REQ-06 (CICLO_DIURNO_NORMAL neutro) y REQ-01 (cap calma con ciclo diurno) redujeron la sobreestimación en condiciones de fusión normal, pero el gap estructural persiste.*

### Matriz de confusión v4.0 (Ronda 3)

```
                    AndesAI
              1    2    3    4    5
Snowlab  1  [ 0    1   32   24    3 ]  (60 casos)
         2  [ 0    0    5    8    2 ]  (15 casos)
         3  [ 0    0    4    3    1 ]  ( 8 casos)
         4  [ 0    0    3    0    0 ]  ( 3 casos)
         5  [ 0    0    1    0    0 ]  ( 1 caso)
```

### Distribución de niveles Ronda 4

| Nivel | Snowlab (%) | AndesAI v5.0 (%) | Gap |
|-------|-------------|-----------------|-----|
| 1 | 69% | 0% | **−69pp** |
| 2 | 17% | 21% | −4pp |
| 3 | 9% | 62% | **+53pp** |
| 4+ | 3% | 17% | +14pp |

AndesAI emite nivel 1 en 0 de 90 boletines La Parva. Snowlab clasifica el 69% de los días como nivel 1.

### Hallazgo crítico — piso matemático de nivel 3 (Ronda 4)

El análisis de causas raíz (notebook `09_diagnostico_causas_raiz_v5.ipynb`) identificó 3 causas interdependientes:

**CR-1 (causa primaria): `tamano_eaws=5` desde datos topográficos estáticos**

La topografía de La Parva (desnivel ≈1000m, zona inicio ≈646ha, pendiente media 68°) siempre produce `tamano=5` en la función `estimar_tamano_potencial()`. La matriz EAWS establece:

```
fair + a_few + tamano=5 → nivel 3 (siempre)
fair + a_few + tamano=3 → nivel 2
fair + a_few + tamano=2 → nivel 1
```

Adicionalmente hay un bug: `_determinar_tamano()` solo acepta strings ("1"-"5") en su check explícito; cuando el LLM pasa un entero, el check falla y siempre se ejecuta el cálculo dinámico → tamano=5. El tamano refleja el potencial máximo del terreno (estático), no las condiciones actuales del manto.

**CR-2: `DIA_ALTO_RIESGO_PRONOSTICADO` genera ventanas críticas artificiales**

`detectar_ventanas_criticas()` crea una ventana cada vez que el pronóstico muestra `dias_alto_riesgo > 0`. En verano andino, ciclos térmicos normales siempre producen días de temperatura alta en el pronóstico de 5 días. Resultado: 97% de los días calmos tienen `ventanas_criticas ≥ 1`, inflando la frecuencia de "algunas" a "varias" en la matriz EAWS y subiendo el nivel.

**CR-3: Ciclo autorreforzante de REQ-01**

```
nivel=3 → historial: [3,3,3,3] → dias_consecutivos_nivel_bajo=0 → sin cap → nivel=3 → ...
```

El cap de calma sostenida requiere ≥4 días consecutivos de nivel≤2. Como el sistema siempre emite nivel 3 (por CR-1 + CR-2), el historial nunca acumula los días necesarios. Adicionalmente, ~50% de los boletines omiten el parámetro `dias_consecutivos_nivel_bajo` al llamar al clasificador.

### Fixes planificados — v6.0

| Fix | Descripción | Archivos | Impacto estimado |
|-----|-------------|----------|-----------------|
| **FIX-T** | Cap `tamano≤3` cuando `estado_pinn=ESTABLE` + factor neutro + `ventanas<2`. Fix bug integer/string | `tool_clasificar_eaws.py`, `eaws_constantes.py` | Alto: nivel 2-3 → nivel 1-2 en calmos |
| **FIX-V** | Excluir `DIA_ALTO_RIESGO_PRONOSTICADO` del contador de ventanas para bump frecuencia | `tool_ventanas_criticas.py` | Medio: 97% días calmos con vent≥1 → vent=0 |
| **FIX-D** | Fortalecer prompt S5 para pasar SIEMPRE `dias_consecutivos_nivel_bajo` | `prompts.py` (S5) | Medio: habilita cadena REQ-01 |
| **FIX-H** | Default `estabilidad_satelital='poor'` sin ViT en Alpes invierno | `prompts.py` (S4/S5) | Bajo: mejora incremental H1/H3 |

**Criterio de éxito v6.0:**
- H4: sesgo ≤ +0.80, QWK ≥ 0.20, % nivel 1-2 ≥ 30%
- H1/H3: sesgo ≤ −0.40, QWK ≥ 0.25 (gap estructural documentado como limitación)

---

## Metodología del reprocesamiento retroactivo

Para comparar versiones sobre el mismo ground truth se usó `OrquestadorAvalancha.generar_boletin(fecha_referencia=...)`:
- Las queries BQ filtran datos históricos por `fecha_referencia`
- Las APIs externas (ERA5, Open-Meteo) devuelven datos actuales como aproximación
- El procesamiento es cronológico para que REQ-01 pueda leer la cadena de predicciones anteriores
- Script: `notebooks_validacion/reprocesar_retroactivo.py`

| Ronda | Total runs | Errores | Stalls Databricks | Tiempo total |
|-------|-----------|---------|-------------------|--------------|
| Ronda 3 (v4.0) | 120 | 0 | 0 | ~3.5h |
| Ronda 4 (v5.0) | 120 | 1 (nivel=None, run 95) | 3 (TCP hang, ~30-45min c/u) | ~6h (con reinicios) |

*Run 95 (La Parva Sector Bajo 2025-07-25): boletín guardado en BQ+GCS pero con `nivel=None`. Caso aislado, no afecta las métricas de validación (se omite en el cómputo de n=87).*

**Limitación del método:** los datos de API en tiempo real (Open-Meteo, ERA5) corresponden a condiciones actuales (mayo 2026), no a las fechas históricas de validación. Solo los datos almacenados en BQ (`imagenes_satelitales`, `condiciones_actuales`, `pronostico_horas`) reflejan el estado histórico exacto.

---

## Archivos relevantes

| Archivo | Descripción |
|---------|-------------|
| `notebooks_validacion/07_validacion_slf_suiza.py` | Validación H1/H3 (ejecutar para métricas actuales) |
| `notebooks_validacion/08_validacion_snowlab.py` | Validación H4 (ejecutar para métricas actuales) |
| `notebooks_validacion/09_diagnostico_causas_raiz_v5.ipynb` | Análisis causas raíz Ronda 4 — árbol CR-1/CR-2/CR-3/CR-4, simulaciones FIX-T/V/D/H |
| `notebooks_validacion/reprocesar_retroactivo.py` | Replay retroactivo con nueva versión de código |
| `notebooks_validacion/baseline_v32_ronda2.json` | Métricas v3.2 preservadas (JSON) |
| `/tmp/ronda4_suiza.log` | Log completo validación H1/H3 Ronda 4 |
| `/tmp/ronda4_snowlab.log` | Log completo validación H4 Ronda 4 |
| `log_claude.md` | Historial de sesiones y decisiones de implementación |
| `claude/requirements/` | Especificaciones REQs implementados |

---

## Próximos pasos — v6.0

1. **FIX-T** — `tool_clasificar_eaws.py`: cap tamano≤3 en condiciones calmas + fix bug integer/string
2. **FIX-V** — `tool_ventanas_criticas.py`: excluir `DIA_ALTO_RIESGO_PRONOSTICADO` de ventanas
3. **FIX-D** — `prompts.py` (S5): instrucción explícita de pasar `dias_consecutivos_nivel_bajo`
4. Reprocesar Ronda 5 (120 runs, mismo script)
5. **FIX-H** (post-Ronda 5) — prompt S5: default conservador sin ViT en Alpes
