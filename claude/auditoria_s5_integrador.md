# Auditoría S5 Integrador + `tool_clasificar_eaws.py`
**Fecha:** 2026-05-23 | **Branch:** feat/v7.0-fixes | **Versión pipeline:** v25.0

---

## 1. Matriz canónica EAWS — referencia normativa

La implementación en `datos/analizador_avalanchas/eaws_constantes.py` reproduce correctamente la EAWS_MATRIX de Müller et al. (2025) con cuatro paneles (`very_poor`, `poor`, `fair`, `good`) × cuatro frecuencias × cinco tamaños. Las celdas que producen **nivel ≥ 3** según la matriz canónica son:

| Estabilidad | Frecuencia | Tamaño min. para D≥3 | D1 resultante |
|---|---|---|---|
| `very_poor` | `many` | 2 | 3 |
| `very_poor` | `some` | 2 | 3 |
| `very_poor` | `a_few` | 3 | 3 |
| `very_poor` | `nearly_none` | 5 | 3 |
| `poor` | `many` | 2 | 3 |
| `poor` | `some` | 3 | 3 |
| `poor` | `a_few` | 5 | 3 |
| `fair` | `many` | 3 | 3 |
| `fair` | `some` | 5 | 3 |

**Referencias:** Müller et al. (2025) NHESS 25, 4503–4525; Techel et al. (2020) The Cryosphere 14, 3503–3521.

---

## 2. Caps detectados que cierran el techo en nivel ≤ 2

Los tres caps actúan en cadena sobre la rama Andes Chile. Ninguno tiene equivalente simétrico en Alpes.

### 2.1 FIX-CR17A — cap de estabilidad (más severo)

**Archivo:** `tool_clasificar_eaws.py:521-539` (función `_determinar_estabilidad_dominante`)

**Predicado de activación:**
```python
_region_dom == "andes_chile"
AND NOT _factor_activo           # factor ∈ {ESTABLE, CICLO_DIURNO_NORMAL, ""}
AND ventanas_criticas_detectadas == 0
AND idx_base > 1                 # estabilidad base peor que 'fair'
```

**Efecto:** Cuando PINN (S1) reporta `estabilidad_topografica='poor'` o `very_poor` pero no hay factor meteorológico activo ni ventanas críticas, fuerza `idx_base = 1` (`'fair'`). El ajuste meteorológico posterior (línea 541-547) no tiene con qué trabajar: si el factor es neutro, `ajuste_meteo=None` y `idx_final = idx_base = 1`.

**Celdas de EAWS_MATRIX bloqueadas:**

| Combinación canónica | D1 esperado | D1 real (post-CR17A) |
|---|---|---|
| `poor × some × 3` | **3** | 2 (cap a `fair × some × 3`) |
| `poor × many × 3` | **4** | 3* (solo si `vc≥3` activa boost freq) |
| `very_poor × some × 2` | **3** | 1–2 (`fair × some × 2 → 2`) |
| `very_poor × a_few × 3` | **3** | 2 (`fair × a_few × 3 → 2`) |

*La combinación `fair × many × 3 = 3` requiere que `ventanas_criticas ≥ 3` para que `_determinar_frecuencia` booste a `many`. Pero CR17A se activa solo cuando `vc=0`, por lo que ese path es mutuamente excluyente.*

**Contraste con EAWS (Müller 2025 §3.1, Statham 2018 §4):**
La estabilidad del manto (`poor`, `very_poor`) es una **propiedad del manto**, no un estado activo condicionado a un driver meteorológico presente. El CMAH define la estabilidad como la sensibilidad de las capas débiles (PWL, SH, FCC) a sobrecarga —independiente de que haya nevado recientemente. Capear la estabilidad a `fair` por ausencia de trigger activo confunde **sensibilidad estructural** con **triggering dinámico**, que son dos de los tres factores EAWS ortogonales.

### 2.2 FIX-CR7C — cap de tamaño explícito

**Archivo:** `tool_clasificar_eaws.py:393-408`

**Predicado de activación:**
```python
fuente_tamano == "explicito"
AND _region == "andes_chile"
AND tamano_final > 3
AND NOT _factor_activo_tamano
```

**Efecto:** Si S5 pasa `tamano_eaws=4` o `5` (valor del output de S1) pero el factor es neutro, cap duro a `tamano_final=3`. La matriz canónica sí distingue `poor × many × 4 → 4` de `poor × many × 3 → 3+`, pero este cap los iguala para Andes calmo.

**Contraste EAWS:** El tamaño es el **máximo potencial** del terreno (Tabla 4, Müller 2025), no el tamaño esperado en condiciones de calma. La multiplicación del tamaño de zona de inicio por el factor de pendiente es geometría invariante —no depende del clima actual. La distinción entre D=3 y D=4 no debería ser eliminada por este cap para terreno macizamente alto como La Parva Sector Alto.

### 2.3 FIX-T + FIX-GEO — cap de tamaño dinámico

**Archivo:** `tool_clasificar_eaws.py:377-391`

**Predicado de activación:**
```python
_region == "andes_chile"
AND tamano_final > 3
AND NOT _factor_activo_tamano
AND ventanas_criticas_detectadas < 2
```

**Efecto:** Análogo a FIX-CR7C pero aplicado al tamaño calculado dinámicamente por `estimar_tamano_potencial()`. La diferencia es que FIX-CR7C cubre la rama `fuente=explicito` y FIX-T/FIX-GEO cubre el tamaño dinámico.

### 2.4 Cap de calma sostenida (secundario)

**Archivo:** `tool_clasificar_eaws.py:553-558`

**Predicado de activación:** `dias_consecutivos_nivel_bajo >= 4 AND NOT _factor_activo`

**Efecto:** Independientemente de CR17A, refuerza cap en `fair` al final de `_determinar_estabilidad_dominante`. En H4 retroactivo, el historial de 7 días que reporta `obtener_historial_ubicacion` puede tener boletines previos con nivel≤2 generados por los caps anteriores → retroalimentación positiva del conservadurismo.

### 2.5 Frecuencia default `a_few`

**Archivo:** `tool_clasificar_eaws.py:589`

```python
idx_base = escala.index(frecuencia_topografica) if frecuencia_topografica in escala else 1
```

Si S5 no pasa `frecuencia_topografica` (o es None), `idx_base=1` = `a_few`. Con `fair × a_few × 3 → 2` (EAWS_MATRIX línea 348), esto impide llegar a 3 incluso después de CR17A. El LLM debería pasar siempre `frecuencia_estimada_eaws` de S1, pero en corridas retroactivas puede omitirlo.

---

## 3. Estado del calibrador estadístico

**Archivo:** `agentes/validacion/calibrador.py` + `coeficientes_calibracion.json`

### Alpes (alpes_swiss) — shift_only ACTIVO

```json
"calibracion_aplicable": true,
"calibracion_modo": "shift_only",
"alpha": 0.7,  "beta": 1.0,
"sesgo_antes": -0.7,
"qwk_cv_shift_only": 0.2498,  "qwk_cv_sin": 0.1912   (+0.0586 en CV)
"delta_qwk_cv (OLS)": -0.019   ← gate OLS rechazada, pero shift_only aprobada
```

El calibrador `shift_only` suma `+0.7` al nivel raw y redondea:
- `nivel_raw=1` → `round(1.7)` = **2**
- `nivel_raw=2` → `round(2.7)` = **3**

Esto significa que **el calibrador sí convierte nivel_raw=2 en nivel 3** para Alpes. El problema es que CR17A no está presente en Alpes (solo Andes), y en Alpes el techo es más leve —pero con la distribución actual (>50% nivel_raw=1), el calibrador convierte la mayoría a nivel 2, y solo los nivel_raw=2 escalan a 3. La distribución resultante sigue subestimando.

**Observación crítica:** El calibrador fue entrenado con `n=30` pares de versión `v20`. Los boletines de validación H3 usan `--version v13`. **El calibrador no aplica a los boletines v13 que mide el notebook H3**. El `QWK=-0.103` de H3 es sobre boletines generados sin calibrador y sin FIX-WN2, FIX-HN24-SIZE, ni FIX-CR7A-REFACTOR de v20+.

### Andes Chile (andes_chile) — identidad

```json
"calibracion_aplicable": false,
"calibracion_modo": "identidad",
"delta_qwk_cv": -0.1723   ← calibración empeoraría H4
"razon_no_aplicar": "OLS rechazado ([beta_en_rango, mejora_qwk_cv]); shift-only rechazado..."
```

Sin calibración en Andes: el nivel raw es el final. Los caps explican por qué β=0.321 < 0.5 (fuera de rango): la pendiente de la regresión GT→pred es muy baja porque el sistema está artificialmente comprimido en un rango estrecho.

---

## 4. Discrepancia de versiones — validación H3

**Hallazgo crítico:** `notebooks_validacion/07_validacion_slf_suiza.py` (líneas 418-419) usa `default="v13"`. El código vigente es `v25.0`. Cualquier mejora implementada desde v14 en adelante (FIX-CA-WINDOW, FIX-CR7A-REFACTOR, FIX-HN24-SIZE, FIX-CALIB-REG, FIX-WN2) **no está siendo medida** en las métricas H3 reportadas.

| Ítem | v13 (medido hoy) | v25 (código vigente) |
|---|---|---|
| FIX-CA-WINDOW (ventana temporal) | NO | SÍ |
| FIX-CR7A-REFACTOR (compuerta calma) | NO | SÍ |
| FIX-HN24-SIZE (tamaño por HN24 IMIS) | NO | SÍ |
| Calibrador shift_only +0.7 | NO | SÍ |
| FIX-CR17A | NO (introducido en v17) | SÍ |

Para evaluar el código actual hay que ejecutar:
```bash
python notebooks_validacion/07_validacion_slf_suiza.py --version v25
```
Esto requiere que existan boletines `v25` con `nombre_ubicacion ∈ {Interlaken, Matterhorn Zermatt, St Moritz}` en `climas-chileno.clima.boletines_riesgo`. Si no existen (el pipeline solo corre en zonas activas), se necesita lanzar `orquestador-avalanchas` con esas coordenadas y fechas de invierno 2023-2024.

---

## 5. Auditoría del prompt S5 (prompts.py)

**Hallazgos:**

| Sección | Línea | Evaluación |
|---|---|---|
| Extracción `num_ventanas_criticas` | 54-58 | ✅ Correcto — explícitamente instruye NO usar `dias_alto_riesgo` |
| `condiciones_meteo_disponibles` | 86-91 | ✅ Correcto — gate conservadora bien explicada |
| `CICLO_DIURNO_NORMAL → SIN AJUSTE` | 103 | ⚠️ Necesita aclaración — se trata como ESTABLE para caps, lo que equivale a activar CR17A y CR7C diariamente en La Parva (ciclo térmico normal activado ~9 meses del año) |
| Calma sostenida → nivel ≤ 2 | 108-111 | ⚠️ El prompt documenta el comportamiento esperado del cap, pero la frase "nivel resultante será ≤ 2" es una restricción de diseño, no un comportamiento emergente |
| Libertad del LLM para subir nivel | 95-113 | ✅ El LLM no decide el nivel directamente — todo está cedido a la tool. El prompt solo instruye qué pasar. No hay sesgo descendente en el prompt. |

**Conclusión del prompt:** El prompt S5 no introduce sesgo conservador adicional. Los caps están en código, no en instrucciones. La única interacción relevante es que `CICLO_DIURNO_NORMAL` activado por S3 en condiciones andinas normales gatilla ambos caps.

---

## 6. Auditoría del flujo S3 → S5

**Variables que desbloquean nivel ≥ 3:**

| Variable | Fuente | Umbral para unlock | Frecuencia en H4 retrospectivo (estimada) |
|---|---|---|---|
| `factor_meteorologico ≠ ESTABLE/CICLO_DIURNO_NORMAL` | S3 | Cualquier activo | Baja: solo durante tormentas (≈15-20% días temporada) |
| `ventanas_criticas_detectadas ≥ 3` | S3 `tool_ventanas_criticas` | ≥3 para boost freq | Muy baja: requiere trigger EAWS + manto crítico simultáneos |
| `nieve_nueva_cm_wn2 ≥ 25` | S3 vía WN2 | Con factor activo | Baja: WN2 disponible desde 2025-07; no cubre H4 histórico |

**Diagnóstico:**  El 80-85% de los días de la temporada La Parva 2024-2025 el sistema opera en estado `factor=CICLO_DIURNO_NORMAL` o `factor=ESTABLE` con `vc=0`. Todos esos días caen en los caps y producen nivel ≤ 2, aunque el manto PINN esté en `poor`. Los 12 eventos Snowlab≥3 del dataset H4 corresponden a nevadas intensas retroactivas que ERA5 subestima — la precipitación no supera el umbral para generar `NEVADA_RECIENTE` en `obtener_tendencia_meteorologica`. En esos días `nieve_nueva_cm_wn2` tampoco estaba disponible (WN2 no existía en 2024).

---

## 7. Auditoría de tests

| Archivo | Tests de nivel ≥ 3 | Observación |
|---|---|---|
| `test_fix_cr7.py` (24 tests) | 0 | Todos verifican que caps funcionan: nivel≤2 o nivel=1 |
| `test_fix_cr10.py` (9 tests) | 0 | Solo verifica detección de ventanas y precipitación |
| `test_fix_wn2.py` (31 tests) | 3 (líneas 509, 550, 568) | Único archivo con nivel≥3 — todos requieren `nieve_nueva_cm_wn2≥25` con `NEVADA_RECIENTE` |
| `test_fix_cr14.py` (si existe) | No encontrado | — |

**Hallazgo:** El test suite **no tiene ningún caso que verifique** que la ruta `poor × some × 3 → nivel 3` sea accesible via la matriz estándar sin nieve fresca. La corrección de CR17A no tendría tests de regresión.

---

## 8. Hallazgos priorizados

### HIGH

**H1 — FIX-CR17A confunde estabilidad estructural con trigger activo**
- Archivo: `tool_clasificar_eaws.py:521-539`
- Impacto: Bloquea la celda `poor × some × 3 → 3` en Andes en todos los días sin nevada reciente. Los 12 eventos Snowlab≥3 del dataset H4 probablemente caen aquí.
- Contraste normativo: Müller 2025 §3.1 + Statham 2018 §4 — la clase de estabilidad del manto es independiente del trigger actual.
- Fix propuesto: Convertir cap duro a **atenuación condicional**: si `factor=neutro AND vc=0`, bajar idx_base en 1 paso (no capearlo a `fair` absolutamente). `poor → fair` solo si `dias_consecutivos_nivel_bajo ≥ 3`; `very_poor → poor` siempre.

**H2 — Validación H3 mide v13 (4 versiones mayor antes de los fixes actuales)**
- Archivo: `notebooks_validacion/07_validacion_slf_suiza.py:418-419`
- Impacto: QWK=-0.103 y F1=0.078 reportados para H3 NO representan el código actual (v25). El calibrador shift_only, FIX-HN24-SIZE, y FIX-CA-WINDOW no aplican a esos boletines.
- Fix: Cambiar `default="v13"` a `default="v25"` y lanzar reproceso de boletines SLF con el pipeline actual.

### MEDIUM

**M1 — Calibrador Alpes activo pero entrenado con datos desactualizados**
- El calibrador shift_only +0.7 fue entrenado con `n=30` pares `v20`. Con 30 pares los CI bootstrap son amplios (`alpha_ci95=[0.875, 2.2705]`). La ganancia real en CV es `+0.0586 QWK`, no grande. Conviene re-entrenarlo con boletines `v25` una vez disponibles.

**M2 — Test suite no valida rutas a nivel ≥ 3 vía matriz estándar**
- No hay test que falle si se elimina la ruta `poor × some × 3`. Cualquier refactor de CR17A necesita tests nuevos.
- Tests mínimos necesarios: `poor × some × 3 → 3` sin nieve fresca; `poor × many × 2 → 3`; `very_poor × a_few × 3 → 3`.

**M3 — `CICLO_DIURNO_NORMAL` activa caps durante ~270 días al año en La Parva**
- El factor `CICLO_DIURNO_NORMAL` se clasifica en `_FACTORES_NEUTROS` (línea 156) por diseño correcto (Müller 2025: ciclo diurno no es un driver de inestabilidad de manto). Pero al hacerlo activa todos los caps de la rama Andes calmo. Durante temporada completa (mayo-octubre), la mayoría de los días con manto `poor` (capas débiles estructurales) caen en esta categoría.
- Posible solución: separar semánticamente `CICLO_DIURNO_NORMAL` de `ESTABLE` para CR17A: CICLO_DIURNO_NORMAL = fenómeno neutro (sin ajuste meteo, sin boost freq) pero no debería activar el cap de estabilidad topográfica.

### LOW

**L1 — Frecuencia default `a_few` cuando S5 no pasa `frecuencia_topografica`**
- Línea 589: `idx_base = ... else 1` (= `a_few`)
- En runs donde S1 no pasa `frecuencia_estimada_eaws`, la combinación post-CR17A es `fair × a_few × {1,2,3}` → máximo nivel 2. No es crítico si S1 siempre popula el campo, pero hay runs retroactivos donde puede no estar presente.

---

## 9. Fixes propuestos — ordenados por impacto esperado

| Prioridad | Fix | Archivo:línea | Tipo | Delta QWK estimado |
|---|---|---|---|---|
| 1 | Convertir CR17A a atenuación condicional (no cap duro) | `tool_clasificar_eaws.py:521-539` | Lógica | H4: +0.05 a +0.15 (12 eventos GT≥3 desbloqueados) |
| 2 | Reprocesar boletines SLF con v25 + actualizar default H3 | `07_validacion_slf_suiza.py:418-419` + Cloud Run | Operacional | H3: QWK real medible (hoy es incognoscible) |
| 3 | Separar CICLO_DIURNO_NORMAL de _FACTORES_NEUTROS en CR17A | `tool_clasificar_eaws.py:156,521` | Lógica | H4: moderado, depende de días afectados |
| 4 | Tests de regresión para rutas ≥ 3 vía matriz estándar | `agentes/tests/test_fix_cr17a.py` (nuevo) | Tests | Previene regresiones futuras |
| 5 | Re-entrenar calibrador Alpes con boletines v25 | `calibrador.py --entrenar --version v25` | Estadístico | H3: +0.02 a +0.05 QWK si n≥50 pares |

---

## 10. Próximos pasos

1. **Sesión siguiente — Implementar Fix #1:** Refactorizar FIX-CR17A para diferenciar el cap según `dias_consecutivos_nivel_bajo`. En días con historial corto (< 3) y manto `poor`, no capear. En calma sostenida confirmada (≥4 días), mantener cap actual.

2. **Depende de Cloud Run — Fix #2:** Ejecutar `orquestador-avalanchas` con coordenadas Interlaken, Matterhorn Zermatt, St Moritz para fechas de invierno 2023-2024 (septiembre-abril), generar boletines con `version_prompts=v25.x`. Actualizar `default="v13"` → `default="v25"` en notebook 07.

3. **Depende de Fix #1 — Fix #3:** Una vez que CR17A sea atenuación, evaluar si `CICLO_DIURNO_NORMAL` necesita tratamiento diferenciado o si la atenuación condicional ya lo resuelve implícitamente.

4. **Fix #4 (tests):** Crear `agentes/tests/test_fix_cr17a.py` con casos que validen que `poor × some × 3 → 3` y `very_poor × a_few × 3 → 3` son accesibles sin nieve fresca en el contexto La Parva.

---

## Referencias

- Müller, K., Mitterer, C., Techel, F. et al. (2025). *The EAWS matrix (Part A): conceptual development.* NHESS 25, 4503–4525. https://nhess.copernicus.org/articles/25/4503/2025/
- Müller, K. et al. (2026). *The EAWS matrix (Part B): operational testing.* NHESS 26, 1161–1181. https://nhess.copernicus.org/articles/26/1161/2026/
- Techel, F., Müller, K. & Schweizer, J. (2020). *Snowpack stability, frequency distribution, and avalanche size.* The Cryosphere 14, 3503–3521. https://tc.copernicus.org/articles/14/3503/2020/
- Statham, G., Haegeli, P., Greene, E. et al. (2018). *A conceptual model of avalanche hazard.* Natural Hazards 90, 663–691. https://link.springer.com/article/10.1007/s11069-017-3070-5
- Pérez-Guillén, C. et al. (2022). *Data-driven avalanche danger prediction Switzerland.* NHESS 22, 2031–2056. https://nhess.copernicus.org/articles/22/2031/2022/
- EAWS Matrix standard: https://www.avalanches.org/standards/eaws-matrix/
