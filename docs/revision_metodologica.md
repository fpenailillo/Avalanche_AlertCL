# Revisión de consistencia metodológica y calidad de ingeniería

**Repositorio:** Avalanche_AlertCL (AndesAI)
**Fecha de revisión:** 2026-06-12
**Alcance:** pipeline de datos (`datos/`), sistema multi-agente (`agentes/`), validación científica (`notebooks_validacion/`, `docs/validacion/`), frontend y CI/CD.

---

## Resumen ejecutivo

El proyecto tiene una base sólida: trazabilidad de prompts con hashes SHA-256, suite de ~530 tests con tests de regresión por cada FIX, reportes de validación por ronda con commit/branch/fecha, manejo de errores con reintentos y un marco ético-legal documentado. Los reportes recientes (p. ej. Ronda 18) son ejemplares en honestidad: diagnostican una regresión de H4 y explican su causa raíz en vez de ocultarla.

Los problemas principales no están en la ejecución de cada ronda sino en la **consolidación**: los documentos-resumen quedaron congelados en rondas antiguas y contradicen los reportes recientes, los criterios de éxito de las hipótesis cambiaron entre rondas sin una justificación centralizada, y el ciclo iterativo de corregir→revalidar sobre los mismos conjuntos de prueba (18 rondas) introduce un riesgo de sobreajuste al test set que la tesina debe declarar y mitigar.

Las correcciones de bajo riesgo identificadas en esta revisión ya fueron aplicadas (ver §4). El resto queda como recomendaciones priorizadas (§5).

---

## 1. Fortalezas a destacar

| Fortaleza | Evidencia |
|---|---|
| Versionado de prompts con integridad verificable | `agentes/prompts/registro_versiones.py` — semver por subagente + hash SHA-256 + changelog (VERSION_GLOBAL v25.17) |
| Tests de regresión por FIX | `agentes/tests/` — 28 archivos, ~530 tests, incl. `test_fix_pinn_wn2.py`, `test_req01_persistencia_temporal.py` |
| Trazabilidad por ronda de validación | `docs/validacion/rondaN_*.md` — cada ronda registra versión, branch, commit, fecha y nº de runs |
| Diagnóstico honesto de regresiones | `docs/validacion/ronda18_v25_resultados.md` — explica por qué H4 empeoró (fuentes WN2/S2 no disponibles en validación histórica) en vez de reportar solo el MAE global que mejoró |
| Manejo de errores y reintentos | `agentes/subagentes/base_subagente.py` (backoff exponencial), excepciones custom (`ErrorOrquestador`, `ErrorSubagente`) |
| Higiene de secretos | `.gitignore` robusto; sin API keys en el código ni en el historial; tokens vía env vars / Secret Manager |
| Frontend con degradación elegante | `frontend/src/services/boletin.js` — fetch a GCS con timeout y fallback a datos demo con aviso visible |

---

## 2. Hallazgos: consistencia metodológica

### M1 (crítico) — Documentos-resumen de validación congelados y contradictorios ✅ corregido

`docs/validacion/RESULTADOS_VALIDACION.md` quedó en la Ronda 3 (v4.0, 2026-05-02) y `notebooks_validacion/RESULTADOS_VALIDACION.md` en la Ronda 5 (v6.2, 2026-05-03), mientras los reportes por ronda llegan hasta la Ronda 18 (v25.0, 2026-05-23). Quien lea solo los resúmenes concluye QWK H3 = −0.031 cuando el valor vigente es +0.3496 (`ronda18_v25_resultados.md`). **Aplicado:** ambos documentos ahora llevan una nota de "documento histórico" con puntero al estado vigente, y el de `docs/` incluye un índice de las 18 rondas.

### M2 (crítico) — Criterios de éxito que cambian entre rondas sin justificación consolidada

- H3: el objetivo era QWK ≥ 0.59 (Techel et al. 2022) en los resúmenes; en `ronda18_v25_resultados.md` se evalúa contra "Objetivo H3 (≥0.35)" y se declara el 0.59 "inalcanzable con n=30".
- H4: objetivo QWK ≥ 0.60 en `docs/validacion/RESULTADOS_VALIDACION.md` vs ≥ 0.40 en `notebooks_validacion/RESULTADOS_VALIDACION.md`.

Relajar umbrales después de ver los resultados ("moving the goalposts") es la objeción metodológica más probable de un comité. **Recomendación:** documento único de hipótesis con los umbrales originales, los vigentes, la fecha y la justificación de cada cambio; en la tesina, presentar los resultados contra ambos umbrales y justificar la recalibración con argumentos independientes del resultado (p. ej. potencia alcanzable con n=30).

### M3 (alto) — Cambio de dataset de validación a mitad del proceso

H1/H3 se validaron primero con n=24 (3 estaciones × 10 fechas, invierno 2023-24, `notebooks_validacion/07_validacion_slf_suiza.py`) y desde la Ronda 13 con el test set DEAPSnow 2018-2020, n=30 (`ronda13_v17_suiza_resultados.md`). Las progresiones entre rondas con datasets distintos no son comparables directamente. **Recomendación:** declarar el cambio de dataset en la tesina y no mezclar ambas series en una misma tabla de progresión sin anotarlo.

### M4 (alto) — Riesgo de sobreajuste al conjunto de prueba por el ciclo fix→revalidar

Las 18 rondas diagnostican errores inspeccionando los mismos pares que luego se usan para validar (87 pares Snowlab; 24/30 pares suizos). Tras 18 iteraciones, las métricas finales sobre esos conjuntos son estimaciones optimistas del desempeño real (el conjunto de prueba actuó de facto como conjunto de desarrollo). `ronda18_v25_resultados.md` ya identifica la solución correcta: **validación prospectiva en la temporada 2025 (junio–septiembre)** con datos nunca vistos. **Recomendación:** declarar esta limitación explícitamente en la tesina y tratar las métricas históricas como métricas de desarrollo, reservando la validación prospectiva como evaluación confirmatoria.

### M5 (alto) — H2 validada únicamente con datos sintéticos calibrados al objetivo

`notebooks_validacion/n06_analisis_nlp_sintetico.py` genera los datos con `generar_datos_sinteticos(n=100, f1_objetivo=0.78, ...)` — es decir, el F1 objetivo es un parámetro de entrada de la simulación. El script lo declara honestamente en su docstring ("cota inferior… datos SINTÉTICOS"), pero los documentos-resumen no lo destacan. **Recomendación:** en la tesina, H2 debe presentarse como estudio de viabilidad/simulación, no como hipótesis validada empíricamente, o re-validarse con los relatos reales de `datos/relatos/andes_handbook_routes.csv`.

### M6 (alto) — Maquinaria estadística implementada pero no reportada

`notebooks_validacion/n05_pruebas_estadisticas.py` implementa bootstrap IC 95% (10.000 iteraciones, seed=42), test de McNemar, z-test y análisis de potencia — pero ningún reporte de ronda publica intervalos de confianza ni p-values; solo estimaciones puntuales. Además, las 4 hipótesis se evalúan con α=0.05 cada una, sin corrección por comparaciones múltiples. **Recomendación:** ejecutar `n05` contra los datos de la Ronda 18 y reportar IC 95% para QWK/F1; aplicar Bonferroni–Holm o declarar H4 como hipótesis primaria preespecificada.

### M7 (medio) — Tamaños muestrales pequeños sin análisis de potencia declarado

n=24/30 (Suiza) y n=87 (Snowlab). El propio `01_validacion_f1_score.py` advierte "Se recomienda ≥50". El análisis de potencia existe en `n05` (`calcular_n_minimo`) pero no se reporta. Con n=30, un QWK de 0.35 tiene un IC muy ancho — esto debe acompañar a cualquier afirmación de cumplimiento o incumplimiento de objetivos.

### M8 (medio) — Artefactos de resultados sin respaldo reproducible

Solo existen JSONs de la Ronda 2 (`baseline_v32_ronda2.json`, `resultados_ronda2_v32_slf_suiza*.json`). Las métricas de las rondas 3–18 viven solo en markdown, sin JSON con timestamp, versión y dataset. **Recomendación:** al ejecutar la validación final para la tesina, guardar el JSON de métricas con metadata completa (versión, commit, dataset, fecha, n) junto a cada reporte.

### M9 (menor) — Scripts de validación duplicados ✅ corregido

`05_pruebas_estadisticas.py` ≡ `n05_pruebas_estadisticas.py` y `06_analisis_nlp_sintetico.py` ≡ `n06_analisis_nlp_sintetico.py` eran idénticos byte a byte. El prefijo `n` existe porque un módulo Python no puede empezar con dígito y los tests los importan (`agentes/tests/test_subagentes.py`). **Aplicado:** se eliminaron las copias con dígito; `n05`/`n06` son las canónicas (los 36 tests que las importan pasan).

### M10 (menor) — Inconsistencia en la denominación del grado ✅ corregido

Los resúmenes de validación decían "Tesis Doctoral MTI UTFSM" mientras el README dice "Tesis de Magíster en Tecnologías de la Información". **Aplicado:** unificado a Magíster (según README); verificar cuál es el correcto.

---

## 3. Hallazgos: ingeniería

### I1 (alto) — Configuración GCP hardcodeada ✅ corregido parcialmente

`agentes/datos/cliente_llm.py` tenía el secret de Databricks con proyecto fijo (`projects/climas-chileno/...`) y el proyecto Gemini repetido en 3 clases. **Aplicado:** constantes de módulo configurables vía `GOOGLE_CLOUD_PROJECT`, `DATABRICKS_SECRET_NAME` y `GEMINI_GCP_PROJECT`, con los valores actuales como default (sin romper despliegues); `.env.example` actualizado. **Pendiente (menor):** IDs en `datos/analizador_avalanchas/main.py` y `agentes/despliegue/job_cloud_run.yaml`.

### I2 (alto) — CI sin verificación de calidad ✅ corregido parcialmente

`.github/workflows/deploy.yml` solo hacía build+deploy. **Aplicado:** paso `npm run lint` antes del build (verificado: pasa limpio). **Pendiente:** los ~530 tests de `agentes/tests/` no corren en ningún CI; un workflow que ejecute el subconjunto que no requiere credenciales GCP daría protección contra regresiones (la mayoría pasa sin GCP; en este entorno: 138 passed / 16 failed solo por falta del SDK `google-cloud`).

### I3 (medio) — Versionado disperso entre componentes

`VERSION_GLOBAL = 25.17` en `agentes/prompts/registro_versiones.py`; `VERSION_METODOLOGIA = 'v1.0.0'` en `datos/monitor_satelital/constantes.py`; defaults `v25.1`/`v25.2` en `07_validacion_slf_suiza.py` y `08_validacion_snowlab.py`. **Recomendación:** un único origen de versión (p. ej. `agentes/__init__.py.__version__`) consumido por los demás, y actualizar los defaults de los scripts de validación al ejecutar nuevas rondas.

### I4 (medio) — Scripts ad-hoc y componentes obsoletos sin marcar

`agentes/scripts/demo_v24_ajuste_tormenta.py`, `demo_fix_sat_storm.py`, `migrar_schema_boletines.py` vs `migrar_schema_boletines_v7.py`, y `agentes/subagentes/subagente_nlp/` (reemplazado por S4 Situational Briefing). Nota: `demo_v24_ajuste_tormenta.py` SÍ se cita en `ronda18_v25_resultados.md` como evidencia de la mejora operacional — no eliminarlo sin actualizar esa referencia. **Recomendación:** sección "scripts vigentes vs históricos" en `agentes/README.md` o mover los obsoletos a `agentes/scripts/legacy/`.

### I5 (medio) — Sin entorno Python reproducible para validación y tests

Hay `requirements.txt` por Cloud Function (correcto para despliegue), pero no existe un `pyproject.toml` o `requirements-dev.txt` raíz que permita reproducir el entorno de notebooks y tests (pytest ni siquiera está listado). **Recomendación:** `requirements-dev.txt` con pytest + numpy/pandas/scipy + google-cloud-* y documentar `pip install -r requirements-dev.txt` en el README.

### I6 (menor) — `print()` vs `logging` en scripts

Las capas de producción (`datos/`, `agentes/subagentes/`) usan `logging` consistentemente; los scripts CLI y notebooks mezclan `print()`. Aceptable para scripts de análisis; revisar solo los que corren en Cloud Run.

---

## 4. Correcciones aplicadas en esta revisión

1. Eliminados `notebooks_validacion/05_pruebas_estadisticas.py` y `06_analisis_nlp_sintetico.py` (duplicados exactos de `n05`/`n06`, que son los importados por los tests).
2. Notas de estado + índice de las 18 rondas en `docs/validacion/RESULTADOS_VALIDACION.md`; nota de estado y mapeo de versiones en `notebooks_validacion/RESULTADOS_VALIDACION.md`.
3. `agentes/datos/cliente_llm.py`: secret de Databricks y proyecto Gemini configurables por entorno, consolidados en constantes de módulo; `.env.example` documenta `DATABRICKS_SECRET_NAME`.
4. Paso de lint agregado a `.github/workflows/deploy.yml`.
5. "Tesis Doctoral" → "Tesis de Magíster" en ambos resúmenes de validación.

El frontend se mantuvo sin cambios, por decisión del autor.

---

## 5. Recomendaciones priorizadas (no aplicadas)

| # | Acción | Esfuerzo | Impacto para la defensa |
|---|--------|----------|------------------------|
| 1 | Documento único de hipótesis: umbrales originales vs vigentes con justificación de cada cambio (M2) | Bajo | Muy alto — neutraliza la objeción de "moving the goalposts" |
| 2 | Declarar el ciclo fix→revalidar como fase de desarrollo y reservar la temporada 2025 como validación confirmatoria (M4) | Bajo (redacción) | Muy alto |
| 3 | Ejecutar `n05_pruebas_estadisticas.py` sobre la Ronda 18 y reportar IC 95% + corrección por comparaciones múltiples (M6, M7) | Medio | Alto |
| 4 | Reposicionar H2 como simulación o re-validar con relatos reales (M5) | Medio | Alto |
| 5 | Guardar JSON de métricas con metadata (versión, commit, dataset, n) por cada ronda futura (M8) | Bajo | Alto |
| 6 | Workflow CI para los tests de `agentes/` sin credenciales GCP (I2) | Medio | Medio |
| 7 | Unificar el origen de versión del sistema (I3) | Bajo | Medio |
| 8 | `requirements-dev.txt` raíz para reproducibilidad del entorno (I5) | Bajo | Medio |
| 9 | Marcar/mover scripts obsoletos y `subagente_nlp` legacy (I4) | Bajo | Bajo |
