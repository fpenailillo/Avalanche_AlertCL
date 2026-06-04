# Diagnóstico y Corrección del Path WN2→PINN→EAWS en AndesAI v25.x

**Proyecto:** Tesis Doctoral — Sistema multi-agente de predicción de riesgo de avalanchas  
**Zona:** La Parva, Andes de Chile (sectores Alto, Bajo, Medio)  
**Ground truth:** Snowlab La Parva (CAA), 30 boletines L2, temporadas 2024-2025  
**Métrica principal:** QWK (Quadratic Weighted Kappa) vs objetivo H4 ≥ 0.40  
**Fecha:** 2026-05-26

---

## 1. Punto de partida

Al iniciar la investigación (v25.0), el sistema multi-agente AndesAI producía boletines con un **techo estructural en nivel ≤2 EAWS**: nunca predicía niveles 3, 4 ni 5, aunque el ground truth Snowlab tuviera 12/30 boletines con peligro ≥ 3.

| Versión | QWK | Distribución AI |
|---------|-----|----------------|
| v25.0 | −0.080 | 100% nivel 1-2 |
| v25.1 | +0.008 | 71% nivel 1, 29% nivel 2, 0% nivel ≥3 |

La hipótesis inicial era que el factor de seguridad del PINN (Mohr-Coulomb estático) no recibía datos temporales de manto nival y retornaba un valor constante por sector.

**Valores constantes del PINN antes del fix:**
- La Parva Sector Alto: FS = 1.83 (siempre)
- La Parva Sector Bajo: FS = 1.96 (siempre)
- La Parva Sector Medio: FS = 1.89 (siempre)

---

## 2. Metodología de diagnóstico

Todos los diagnósticos son **data-driven** — no supuestos sobre el código, sino consultas directas a BigQuery sobre los boletines generados.

**Herramientas utilizadas:**
- `climas-chileno.clima.boletines_riesgo`: boletines generados (campo `tools_llamadas` registra todos los inputs/outputs del LLM)
- `climas-chileno.weathernext_2.weathernext_2_0_0`: ensemble WN2 retroactivo (64 miembros, ventanas 6h)
- `climas-chileno.validacion_avalanchas.snowlab_boletines`: ground truth Snowlab
- Script `08_validacion_snowlab.py`: cálculo de QWK, MAE, matriz de confusión

**Proceso iterativo:**
1. Ejecutar reproceso retroactivo (90 fechas × 3 sectores = 270 boletines → deduplicados a 87 pares)
2. Comparar distribución de `nivel_eaws_24h` con Snowlab
3. Para cada sesgo identificado, consultar los casos de error en BQ y extraer el valor exacto de cada campo intermedio
4. Identificar el mecanismo exacto de falla (no la hipótesis, el dato)
5. Implementar fix puntual y repetir desde 1

---

## 3. Los seis bugs encadenados

### Bug 1 — Tool WN2 no registrada en el subagente topográfico (v25.2)

**Observación:** En los 17 boletines v25.1 de fechas GT≥3, `obtener_pronostico_wn2_ventanas` se llamó **1 vez** (2025-06-14, Sector Medio, llamada por S3). En los otros 16 boletines, `factor_meteorologico = ESTABLE` y el PINN retornaba su valor constante.

**Causa raíz:** `TOOL_PRONOSTICO_WN2_VENTANAS` solo estaba registrada en `subagente_meteorologico/agente.py:59`. El prompt de S1 decía "llama `obtener_pronostico_wn2_ventanas` antes de `calcular_pinn`", pero Qwen3-80B no puede invocar tools no registradas en su subagente, aunque el prompt las mencione.

**Fix:** Registrar la tool en `subagente_topografico/agente.py` + implementar fallback determinista en `tool_calcular_pinn.py` (si el LLM no llama la tool, el código la llama directamente).

**Resultado:** El PINN ahora recibe `nieve_nueva_cm` para las fechas GT≥3.

---

### Bug 2 — p50 del ensemble es 0 en días post-tormenta (v25.3–v25.4)

**Observación:** Para 2024-06-15 (GT=5), la tormenta ocurrió los días 12-14 de junio (HN3d≈87 cm en Farellones DGA 2452 m). El día 15 no hubo precipitación nueva → `nieve_24h_cm_p50_corr = 0.0 cm`.

**Causa raíz:** En un ensemble de 64 miembros con alta incertidumbre, si <50% de los miembros predicen precipitación, `p50 = 0`. La señal de tormenta existe en el percentil p95 (escenario de planificación de riesgo máximo) y en el acumulado 3 días previos.

**Fix:** Ampliar la jerarquía de fallback: `p50_24h (≥5 cm) → p95_24h (≥5 cm) → p95_3d (≥5 cm)`.

**Dato de validación:** Para 2024-06-15, `p95_3d = 173.6 cm` — la tormenta del 12-14 jun está completamente capturada en la ventana 3d.

---

### Bug 3 — Ruido numérico del ensemble bloqueaba el fallthrough (v25.5)

**Observación:** El PINN seguía retornando ESTABLE para 2024-06-15 incluso después del Bug 2.

**Causa raíz:** WN2 siempre retorna `nieve_24h_cm_p50_corr > 0` (~0.1-0.5 cm) por ruido numérico de la interpolación ensemble, incluso en días completamente despejados. La condición era `val_p50 > 0` → True → se usaban 0.13 cm de surcharge, ignorando los 173.6 cm del acumulado 3d.

**Evidencia BQ:** `p50_corr = 0.13 cm` para 2024-06-15 (GT=5, ninguna precipitación real ese día).

**Justificación metodológica:** Schweizer et al. (2003) establecen que HN24h < 5 cm no genera placas de tormenta en terreno alpino. El umbral mínimo de 5 cm es a la vez un filtro de ruido y una limitación física documentada.

**Fix:** `_MIN_NIEVE_CM = 5.0` para todas las ventanas.

---

### Bug 4 — LLM bloqueaba el fallback con valor pequeño de p95_24h (v25.6)

**Observación:** El fallback determinista seguía sin activarse para algunas fechas GT≥3.

**Causa raíz:** El LLM (Qwen3-80B) llamaba `obtener_pronostico_wn2_ventanas`, extraía `nieve_24h_cm_p95_corr = 4.3 cm` de las 83 ventanas 6h, y lo pasaba explícitamente como `nieve_nueva_cm = 4.3`. La condición de activación del fallback era `nieve_nueva_cm is None` → **False** → el fallback 3d (con 173.6 cm) nunca se activaba.

**Fix:** Ampliar la condición a `nieve_nueva_cm is None or nieve_nueva_cm < 5.0`. Si el LLM extrae un valor de 24h pequeño (< umbral), el fallback lo sobreescribe con el valor de ventana 3d cuando éste supera el umbral.

---

### Bug 5 — Fecha incorrecta: el LLM siempre pasaba "2024-06-15" (v25.7)

**Observación:** Después de los cuatro fixes anteriores, el reproceso completo (90 fechas) producía sesgo inverso: todos los boletines tenían `nieve_nueva_cm ≈ 235.7 cm`, independientemente de la fecha real.

**Causa raíz:** El prompt de S1 (`_construir_prompt_usuario` en `base_subagente.py`) solo dice "Analiza la ubicación: {nombre}". No incluye la fecha del boletín. Qwen3-80B infería la fecha del contexto de la herramienta WN2 (que tiene datos de la primera fecha GT≥3 consultada, 2024-06-15) y pasaba `fecha_objetivo = "2024-06-15"` para todos los boletines del reproceso.

**Evidencia BQ:** `tools_llamadas` de boletines de julio y agosto de 2025 mostraban `"fecha_objetivo": "2024-06-15"` — la fecha de la primera tormenta GT=5 del dataset.

**Fix:** En el fallback determinista de `tool_calcular_pinn.py`, priorizar `obtener_fecha_referencia_global()` (fecha real del boletín, establecida por el orquestador antes de ejecutar los subagentes) sobre la fecha que pasa el LLM.

```python
# Priorizar la fecha global del orquestador sobre la del LLM
fecha_ref = obtener_fecha_referencia_global()
if fecha_ref is not None:
    fecha_objetivo = fecha_ref.strftime("%Y-%m-%d")
```

**Resultado v25.7:** QWK = +0.242 (desde +0.008 en v25.1 — mejora de +0.234 en un solo fix).

---

### Bug 6 — Sesgo residual: el LLM mapea PINN ESTABLE → EAWS "poor" (identificado v25.8)

**Observación:** Con v25.7, QWK = +0.242 pero sesgo = +0.448. 35/87 pares GT=1 son predichos como AI≥2. Con v25.8 (umbral p95=30 cm), el sesgo baja a +0.414 y QWK sube a +0.385, pero persisten 31 falsos positivos sin señal WN2 que los justifique.

**Diagnóstico:** Consulta BQ de `tools_llamadas` en los 35 casos erróneos:

```
2024-07-05 La Parva Sector Alto:
  PINN: estado=ESTABLE, FS=1.81
  LLM pasa a clasificar_riesgo_eaws_integrado:
    "estabilidad_topografica": "poor"   ← INCORRECTO
    "frecuencia_topografica": "a_few"
    "tamano_eaws": 2
  Resultado: poor + a_few + D2 → nivel 2  (GT=1)
```

**Distribución del error (v25.8, n=87 boletines):**

| PINN estado | LLM estabilidad_top | nivel AI | n casos |
|---|---|---|---|
| ESTABLE | `good` | 1 | 32 |
| ESTABLE | `fair` | 1 | — |
| ESTABLE | `fair` | 2 | 16 |
| ESTABLE | `poor` | 2 | 15 |
| MARGINAL | `poor` | 2 | 7 |
| INESTABLE | `very_poor` | 2–5 | 11 |
| CRITICO | `very_poor` | 2–3 | 6 |

**Causa raíz:** El LLM desplaza el mapeo un escalón hacia arriba. Interpreta el terreno alpino de La Parva como intrínsecamente "pobre" en estabilidad (visión topográfica estática), sin distinguir entre la estabilidad potencial del terreno (que es constante, igual que el DEM) y la estabilidad actual del manto nival calculada por el PINN (que varía con la carga de nieve).

El mapeo correcto, según la interpretación física de Mohr-Coulomb:

| estado_manto PINN | FS | estabilidad EAWS correcta |
|---|---|---|
| ESTABLE | ≥ 1.5 | `good` |
| MARGINAL | 1.3–1.5 | `fair` |
| INESTABLE | 1.0–1.3 | `poor` |
| CRITICO | < 1.0 | `very_poor` |

**Verificación con la matriz EAWS** (`eaws_constantes.py`):

```python
consultar_matriz_eaws("good", "a_few", 2)  → nivel 1  ✓
consultar_matriz_eaws("fair", "a_few", 2)  → nivel 2  ← falso positivo
consultar_matriz_eaws("poor", "a_few", 2)  → nivel 2  ← falso positivo
```

Con `good`, la matriz da nivel 1 **para cualquier combinación de frecuencia y tamaño**:
- `good + nearly_none/a_few/some + D1/D2/D3` → siempre nivel 1

**Impacto en días de tormenta (GT≥3):** Neutro. PINN INESTABLE con "poor" (en lugar de "very_poor") da:
- `poor + some + D3 = 3` (idéntico a `very_poor + some + D3 = 3`)

**Fix propuesto (v25.9 — FIX-PINN-EAWS-MAP):**
1. `tool_calcular_pinn.py`: añadir campo `estabilidad_eaws` al dict de retorno con mapeo determinista
2. `subagente_topografico/prompts.py`: "DEBES usar el campo `estabilidad_eaws` del PINN directamente como `estabilidad_topografica` — no reinterpretes"

---

## 4. Trayectoria de métricas

```
Versión  | QWK    | MAE   | Sesgo  | MAE_storm | Fallo principal
---------|--------|-------|--------|-----------|------------------
v25.0    | −0.080 |  —    | −0.310 |  2.417    | PINN siempre ESTABLE
v25.1    | +0.008 | 0.632 | −0.218 |  2.000    | Tool WN2 no en S1
v25.7    | +0.242 | 0.885 | +0.448 |  1.417    | Fecha incorrecta (→ sobreest.)
v25.8    | +0.385 | 0.782 | +0.414 |  1.250    | LLM mapeo PINN→EAWS incorrecto
v25.9 ▸  | >0.40  | <0.70 | <+0.15 |  <1.00    | (proyectado — fix determinista)
```

El salto mayor fue v25.1→v25.7 (+0.234) producido por el fix de la fecha global del orquestador. El segundo mayor salto fue v25.7→v25.8 (+0.143) por el umbral diferenciado de p95. El fix pendiente v25.9 proyecta cruzar el umbral H4.

---

## 5. Contribución académica

### 5.1 Hallazgo sobre sistemas multi-agente LLM

**El LLM introduce interpretación no controlada en la interfaz tool→tool.** Cuando S1 obtiene el estado del PINN (`ESTABLE`) y lo traduce a la escala EAWS para pasarlo a S5 (`estabilidad_topografica`), esta traducción no está codificada en ninguna regla explícita del sistema — queda a discreción del LLM. El resultado es un sesgo sistemático que puede detectarse con análisis de datos pero no con inspección del código.

**Lección:** En sistemas multi-agente con herramientas secuenciales, los campos intermedios que cruzan la interfaz entre tools deben ser deterministas cuando existe una correspondencia física exacta. El LLM solo debe tomar decisiones interpretativas cuando no hay alternativa determinista.

### 5.2 Metodología de diagnóstico data-driven

El diagnóstico completo de los seis bugs fue posible gracias a:
1. **Trazabilidad completa:** el campo `tools_llamadas` en `boletines_riesgo` registra el JSON de entrada de cada tool invocada por el LLM. Esto permite reconstruir exactamente qué valores recibió cada función, independientemente de la lógica del LLM.
2. **Reproceso retroactivo controlado:** la capacidad de re-generar boletines para fechas históricas permitió aislar bugs individualmente.
3. **Ground truth de alta calidad:** los 30 boletines L2 de Snowlab CAA (temporadas 2024-2025) proporcionan un benchmark estable para medir el impacto de cada fix.

### 5.3 Sobre el "PINN" del sistema

El componente llamado PINN en este sistema implementa la ecuación de Mohr-Coulomb para estabilidad de taludes (Fredlund & Krahn, 1977), no una Physics-Informed Neural Network en el sentido de Raissi et al. (2018). La denominación se mantiene por continuidad histórica, pero es técnicamente una evaluación determinista de estabilidad de manto nival.

La diferencia es relevante para la tesis: el bottleneck identificado no es arquitectónico (no requiere reentrenar una red neuronal) sino de **alimentación de inputs dinámicos**. El modelo físico es correcto; el problema era que no recibía los datos temporales (carga de nieve del ensemble WN2) necesarios para producir salidas variables en el tiempo.

---

## 6. Próximos pasos

### Inmediato — v25.9 (FIX-PINN-EAWS-MAP)

1. Añadir `estabilidad_eaws` al output de `tool_calcular_pinn.py`
2. Actualizar prompt de S1 con instrucción explícita de mapeo
3. Reproceso completo 90 fechas × 3 sectores (~6h)
4. Validación `08_validacion_snowlab.py --version v25.9`
5. Criterio de éxito: QWK ≥ 0.40, MAE tormentas ≤ 1.00

### Posterior — H3 (Alpes suizos)

La trayectoria H4 no implica mejora automática de H3. Los problemas en Alpes son distintos:
- ERA5 subestima precipitación convectiva en cresta alpina
- Sin datos de manto nival in-situ (Sclass2, pwl_100 de SLF) el sistema no puede detectar capas persistentes débiles

Estos requieren trabajo de ingesta de datos separado y están fuera del alcance del sprint actual.

---

## 7. Referencias

- Schweizer, J., Jamieson, J.B., Schneebeli, M. (2003). Snow avalanche formation. Reviews of Geophysics, 41(4).
- Techel, F., et al. (2022). Spatial variability of avalanche danger. The Cryosphere, 16(10).
- Müller, K., et al. (2025). EAWS Matrix 2025. European Avalanche Warning Services.
- Statham, G., et al. (2018). CMAH — Conceptual Model of Avalanche Hazard. Natural Hazards and Earth System Sciences.
- Raissi, M., Perdikaris, P., Karniadakis, G.E. (2018). Physics-informed neural networks. Journal of Computational Physics, 378, 686-707.
- Fredlund, D.G., Krahn, J. (1977). Comparison of slope stability methods. Canadian Geotechnical Journal, 14(3).
- Caro, A., et al. (2026). Estimación de acumulación nívea en cuencas de Los Andes centrales. DGA Chile. [solo validación offline]
