# REQ-v7.0 — Fixes quirúrgicos post-Ronda 5

**Fecha:** 2026-05-03
**Versión objetivo:** v7.0
**Basado en:** Validación Ronda 5 (v6.2) + Informe Técnico v7.0 + Techel et al. 2025 Part B
**Branch:** `feat/v7.0-fixes`
**Autor:** Francisco Peñailillo — UTFSM MTI 2024

---

## Estado de partida (v6.2 Ronda 5)

| Métrica | v6.2 | Objetivo v7.0 |
|---------|------|---------------|
| QWK Snowlab H4 | −0.031 | ≥ 0.00 (positivo) |
| MAE H4 | 1.230 | ≤ 1.00 |
| Sesgo H4 | +0.885 | ≤ +0.60 |
| % nivel 1-2 H4 | 58% | ≥ 65% |
| QWK SLF H1/H3 | −0.031 | ≥ +0.10 (recuperar regresión) |
| F1-macro H1/H3 | 0.244 | ≥ 0.25 |

**Causa raíz principal identificada:**
- H4: S1 no distingue riesgo topográfico potencial vs activo → nivel base siempre ≥ 2 en La Parva
- H1/H3: FIX-T cap `tamano≤3` aplicado globalmente → subestima en Alpes (54% nivel 1 vs 12.5% real)

**Filosofía v7.0:** tres fixes quirúrgicos en archivos existentes antes de agregar arquitectura nueva.
No introducir nueva infraestructura. No modificar Cloud Run, BigQuery ni Cloud Functions.

---

## FIX-GEO — Cap `tamano` condicional por región geográfica

**Prioridad:** 🔴 Urgente — revierte regresión H1/H3 sin tocar H4
**Archivo:** `agentes/subagentes/subagente_topografico/tools/tool_clasificar_eaws.py`
(o el archivo donde vive `_determinar_tamano()` y FIX-T de v6.2)
**Esfuerzo:** ~2h

### Problema

FIX-T implementado en v6.2 aplica `tamano = min(tamano, 3)` cuando
`estado_pinn == ESTABLE` y `ventanas_criticas < 2`. En La Parva (topografía
volcánica extrema, 510 ha zona inicio) esto es correcto. En los Alpes suizos,
donde el terreno es menos extremo y el SLF ya captura las condiciones reales,
el cap produce subestimación sistemática → regresión QWK H1/H3 de +0.143 a −0.031.

Evidencia: distribución v6.2 H1/H3 muestra 54.2% nivel 1 predicho vs 12.5% real SLF.

### Solución

Agregar parámetro `region` a `_determinar_tamano()` y aplicar el cap
solo cuando `region == "andes_chile"`.

```python
# En tool_clasificar_eaws.py

# Mapa estático de ubicaciones → región EAWS
REGION_POR_UBICACION = {
    # Andes Chile — cap activo
    "La Parva Sector Alto": "andes_chile",
    "La Parva Sector Medio": "andes_chile",
    "La Parva Sector Bajo": "andes_chile",
    "Valle Nevado": "andes_chile",
    "El Colorado": "andes_chile",
    "Antuco": "andes_chile",
    "Chapa Verde": "andes_chile",
    "Las Araucarias": "andes_chile",
    "Volcán Osorno": "andes_chile",
    # Alpes suizos — sin cap
    "Interlaken": "alpes_suizos",
    "Matterhorn Zermatt": "alpes_suizos",
    "St Moritz": "alpes_suizos",
}

def _determinar_tamano(
    datos_topograficos: dict,
    estado_pinn: str,
    ventanas_criticas: int,
    nombre_ubicacion: str,          # ← nuevo parámetro
) -> int:
    """Determina el tamaño EAWS máximo a reconer con.

    FIX-GEO (v7.0): el cap tamano≤3 solo aplica en Andes Chile.
    En Alpes suizos no se aplica cap — ERA5 y SLF ya reflejan
    las condiciones reales del terreno alpino.
    """
    region = REGION_POR_UBICACION.get(nombre_ubicacion, "andes_chile")
    tamano = _calcular_tamano_base(datos_topograficos)

    # FIX-T (v6.2): cap cuando PINN indica estabilidad y sin ventanas críticas
    # FIX-GEO (v7.0): solo aplicar en Andes, no en Alpes
    if (
        region == "andes_chile"
        and estado_pinn == "ESTABLE"
        and ventanas_criticas < 2
    ):
        tamano = min(tamano, 3)

    return tamano
```

Propagar `nombre_ubicacion` hacia `_determinar_tamano()` desde el caller
(buscar todas las llamadas a esta función en el archivo y agregar el parámetro).

### Tests requeridos

```python
# test_clasificar_eaws.py

def test_cap_tamano_aplica_en_andes():
    """FIX-GEO: cap activo en La Parva."""
    resultado = _determinar_tamano(
        datos_topograficos={"tamano_base": 4},
        estado_pinn="ESTABLE",
        ventanas_criticas=0,
        nombre_ubicacion="La Parva Sector Alto",
    )
    assert resultado == 3  # cap aplicado

def test_cap_tamano_no_aplica_en_alpes():
    """FIX-GEO: sin cap en Alpes suizos."""
    resultado = _determinar_tamano(
        datos_topograficos={"tamano_base": 4},
        estado_pinn="ESTABLE",
        ventanas_criticas=0,
        nombre_ubicacion="Interlaken",
    )
    assert resultado == 4  # sin cap

def test_cap_tamano_alpes_ventanas_criticas():
    """FIX-GEO: tampoco aplica cap en Alpes con ventanas críticas."""
    resultado = _determinar_tamano(
        datos_topograficos={"tamano_base": 5},
        estado_pinn="INESTABLE",
        ventanas_criticas=3,
        nombre_ubicacion="St Moritz",
    )
    assert resultado == 5  # sin modificación

def test_ubicacion_desconocida_usa_andes_por_defecto():
    """FIX-GEO: ubicación no mapeada → andes_chile (comportamiento seguro)."""
    resultado = _determinar_tamano(
        datos_topograficos={"tamano_base": 4},
        estado_pinn="ESTABLE",
        ventanas_criticas=0,
        nombre_ubicacion="Portillo",  # no en mapa
    )
    assert resultado == 3  # default seguro = cap Andes
```

### Criterio de éxito

Ronda 6 H1/H3: distribución nivel 1 predicho baja de 54.2% hacia ~20–30%,
QWK vuelve a rango +0.10–+0.15. H4 La Parva: métricas sin cambio (cap sigue activo).

---

## FIX-H — ViT `sin_datos` en Europa → estabilidad `poor` por defecto

**Prioridad:** 🔴 Alta — mejora H1/H3 sin afectar H4
**Archivo:** `agentes/subagentes/subagente_satelital/tools/tool_analizar_imagenes.py`
(o el archivo donde se genera `estabilidad_satelital` / `estado_vit`)
**Esfuerzo:** ~3h

### Problema

Cuando ViT retorna `sin_datos` (coordenadas fuera del área de entrenamiento,
imagen nubosa, o sensor no disponible), el sistema asigna por defecto
`estabilidad_satelital = 'fair'`. En La Parva esto es aceptable — hay datos
satelitales disponibles la mayoría del tiempo. En las estaciones suizas
(Interlaken, Matterhorn, St Moritz), ViT retorna `sin_datos` frecuentemente
porque el modelo fue entrenado con imágenes andinas, no alpinas.

Resultado: S5 recibe `estabilidad_satelital = 'fair'` como si el manto
estuviera confirmado estable → subestimación sistemática en H1/H3.

Techel Part B Sección 5.1: a nivel de peligro 2 (moderate), el 62% de los
casos usa el panel de estabilidad `poor`. El default `fair` produce sesgo
hacia niveles bajos consistente con la regresión observada.

### Solución

Diferenciar el default según región geográfica del boletín.

```python
# En tool_analizar_imagenes.py

# Coordenadas aproximadas para detectar región
BBOX_ANDES_CHILE = {
    "lat_min": -42.0, "lat_max": -17.0,
    "lon_min": -75.0, "lon_max": -65.0,
}

def _inferir_region_por_coords(lat: float, lon: float) -> str:
    """Infiere región EAWS a partir de coordenadas."""
    bbox = BBOX_ANDES_CHILE
    if (bbox["lat_min"] <= lat <= bbox["lat_max"] and
            bbox["lon_min"] <= lon <= bbox["lon_max"]):
        return "andes_chile"
    return "otro"  # Europa, etc.

def _estabilidad_default_por_region(region: str) -> str:
    """
    FIX-H (v7.0): default de estabilidad satelital cuando ViT no tiene datos.

    Andes Chile: 'fair' — ViT fue entrenado aquí, sin_datos es raro
                          y suele indicar nubosidad transitoria.
    Otro (Europa, Alpes): 'poor' — ViT no tiene datos de entrenamiento
                          para esta región; la incertidumbre debe
                          reflejarse en un default más conservador.
    """
    return "fair" if region == "andes_chile" else "poor"

def analizar_imagenes_satelitales(
    nombre_ubicacion: str,
    lat: float,
    lon: float,
    datos_satelitales: dict,
) -> dict:
    """Analiza imágenes satelitales y retorna estabilidad EAWS."""

    estado_vit = datos_satelitales.get("estado_vit", "sin_datos")

    if estado_vit == "sin_datos":
        region = _inferir_region_por_coords(lat, lon)
        estabilidad_default = _estabilidad_default_por_region(region)
        return {
            "estabilidad_satelital": estabilidad_default,
            "estado_vit": "sin_datos",
            "razon_default": f"ViT sin datos — region={region}, default={estabilidad_default}",
            "confianza": "baja",
        }

    # ... lógica existente cuando ViT tiene datos ...
```

Verificar que `lat` y `lon` de cada ubicación estén disponibles en el contexto
del subagente satelital. Si no, obtenerlos de `clima.zonas_objetivo` vía
`consultor_bigquery.py`.

### Tests requeridos

```python
# test_satelital.py

def test_default_sin_datos_andes():
    """FIX-H: sin datos ViT en Andes → fair."""
    resultado = analizar_imagenes_satelitales(
        nombre_ubicacion="La Parva Sector Alto",
        lat=-33.354, lon=-70.298,
        datos_satelitales={"estado_vit": "sin_datos"},
    )
    assert resultado["estabilidad_satelital"] == "fair"

def test_default_sin_datos_europa():
    """FIX-H: sin datos ViT en Europa → poor (más conservador)."""
    resultado = analizar_imagenes_satelitales(
        nombre_ubicacion="Interlaken",
        lat=46.686, lon=7.863,
        datos_satelitales={"estado_vit": "sin_datos"},
    )
    assert resultado["estabilidad_satelital"] == "poor"

def test_con_datos_vit_no_afectado():
    """FIX-H: cuando ViT tiene datos, FIX-H no interfiere."""
    resultado = analizar_imagenes_satelitales(
        nombre_ubicacion="Interlaken",
        lat=46.686, lon=7.863,
        datos_satelitales={"estado_vit": "ALERTADO", "score_anomalia": 7.2},
    )
    # la lógica existente debe procesar normalmente
    assert resultado["estabilidad_satelital"] != "sin_datos"
    assert "razon_default" not in resultado
```

### Criterio de éxito

Ronda 6 H1/H3: sesgo negativo se reduce de −0.75 hacia −0.40 a −0.50.
H4 La Parva: sin cambio (coordenadas andinas → `fair` como antes).

---

## FIX-S1-SEMANTICA — S1 distingue riesgo potencial vs activo

**Prioridad:** 🟡 Alta — ataca CR-5 (gap distribucional 69% vs 15% nivel 1)
**Archivos:**
- `agentes/subagentes/subagente_topografico/prompts.py` (o `system_prompt`)
- `agentes/subagentes/subagente_integrador/prompts.py`
**Esfuerzo:** ~5h (prompt engineering + validación)

### Problema

CR-5 identificado en Ronda 5: Snowlab clasifica 69% de días como nivel 1,
AndesAI solo alcanza 15%. La causa raíz es semántica:

S1 evalúa la topografía de La Parva (510 ha zona inicio, pendientes 35-45°,
desnivel ≈1000m) y reporta "riesgo moderado-alto" aunque no haya precipitación
reciente ni inestabilidad activa del manto. S5 recibe esta señal y la interpreta
como evidencia de peligro → nivel 2-3.

EAWS 2025 Tabla 6 Paso 1 es explícito: si no hay problemas de avalancha
presentes (`no_distinct_avalanche_problem`), el nivel es 1-Low directamente,
sin consultar la matriz.

La topografía de La Parva define el Reference Unit (dónde puede ocurrir una
avalancha) pero no constituye per se un "problema de avalancha presente".

### Solución

**Parte A — Cambio en prompt de S1:**

Agregar sección explícita en el system prompt / instrucciones de S1:

```
## Distinción crítica: riesgo potencial vs activo (EAWS 2025)

La topografía de La Parva (pendientes 35-45°, 510 ha de zona de inicio)
define el DÓNDE puede ocurrir una avalancha (Reference Unit), pero NO
constituye evidencia de un problema de avalancha activo.

Al reportar tu análisis topográfico, DEBES distinguir explícitamente:

**riesgo_topografico_potencial** (siempre presente en terreno alpino/andino):
- Pendientes en rango crítico
- Zonas de inicio identificadas
- Exposición al viento
→ Este factor define la ZONA DE PELIGRO pero NO eleva el nivel EAWS

**problema_avalancha_activo** (requiere trigger + estado del manto):
- Precipitación de nieve ≥ 10cm en 24-48h, O
- Lluvia sobre nieve (FUSION_ACTIVA_CON_CARGA confirmada), O
- Viento fuerte con nieve transportable disponible, O
- Anomalía SWE positiva confirmada por ERA5 o SAR
→ Este factor SÍ activa la evaluación de la matriz EAWS

Si NO hay trigger activo, reporta:
  problema_avalancha_presente: false
  tipo_problema: "no_distinct_avalanche_problem"
  razon: "[explicación de por qué no hay trigger activo]"

Si hay trigger activo, reporta:
  problema_avalancha_presente: true
  tipo_problema: "[new_snow | wind_slab | wet_snow | persistent_weak_layer]"
```

**Parte B — Cambio en prompt de S5 (integrador):**

Agregar manejo explícito del caso `problema_avalancha_presente: false`:

```
## Workflow EAWS — Paso 1 (CRÍTICO)

Antes de consultar la matriz EAWS, verifica el reporte de S1:

SI todos los subagentes reportan problema_avalancha_presente: false:
  → nivel_eaws_24h = 1
  → nivel_eaws_48h = 1
  → nivel_eaws_72h = 1
  → descripcion = "Sin problemas de avalancha identificados. Terreno
                   técnico pero manto estable. Nivel Bajo."
  → NO consultar la matriz EAWS
  → STOP — no continuar con pasos 2-7

SI al menos un subagente reporta problema_avalancha_presente: true:
  → Continuar con pasos 2-7 del workflow EAWS normalmente
  → Usar el tipo de problema reportado para seleccionar el panel correcto

Esta lógica implementa el Paso 1 del workflow EAWS 2025 (Tabla 6):
"If no avalanche problems are present, the avalanche danger level is 1-Low."
```

**Parte C — Campo nuevo en schema boletín:**

Agregar campo `problema_avalancha_presente` (BOOLEAN) y `tipo_problema_eaws`
(STRING) a `clima.boletines_riesgo` para trazabilidad:

```python
# En agentes/salidas/schema_boletines.json — agregar:
{
    "name": "problema_avalancha_presente",
    "type": "BOOL",
    "mode": "NULLABLE",
    "description": "FIX-S1-SEMANTICA: si hay al menos un problema EAWS activo"
},
{
    "name": "tipo_problema_eaws",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "new_snow|wind_slab|wet_snow|persistent_weak_layer|no_distinct_problem"
},
```

### Tests requeridos

```python
# test_s1_semantica.py

def test_sin_precipitacion_reporta_problema_false():
    """FIX-S1: sin trigger activo → problema_avalancha_presente=False."""
    # Simular: 0mm precipitación 72h, ciclo diurno normal, PINN ESTABLE
    output_s1 = ejecutar_s1_con_condiciones(
        precipitacion_72h_mm=0,
        factor_meteorologico="CICLO_DIURNO_NORMAL",
        estado_pinn="ESTABLE",
        ubicacion="La Parva Sector Alto",
    )
    assert output_s1["problema_avalancha_presente"] == False
    assert output_s1["tipo_problema"] == "no_distinct_avalanche_problem"

def test_nevada_reciente_reporta_problema_true():
    """FIX-S1: nevada reciente → problema_avalancha_presente=True."""
    output_s1 = ejecutar_s1_con_condiciones(
        precipitacion_72h_mm=25,
        factor_meteorologico="NEVADA_RECIENTE",
        estado_pinn="INESTABLE",
        ubicacion="La Parva Sector Alto",
    )
    assert output_s1["problema_avalancha_presente"] == True
    assert output_s1["tipo_problema"] in ["new_snow", "wind_slab"]

def test_s5_nivel1_cuando_sin_problema():
    """FIX-S1: S5 emite nivel 1 directamente si no hay problema activo."""
    boletin = ejecutar_pipeline_completo(
        mocks={
            "s1": {"problema_avalancha_presente": False},
            "s2": {"estado_vit": "ESTABLE"},
            "s3": {"factor_meteorologico": "CICLO_DIURNO_NORMAL",
                   "ventanas_criticas": 0},
        },
        ubicacion="La Parva Sector Alto",
    )
    assert boletin["nivel_eaws_24h"] == 1
    assert boletin["nivel_eaws_48h"] == 1

def test_s5_consulta_matriz_cuando_hay_problema():
    """FIX-S1: S5 consulta matriz EAWS si hay problema activo."""
    boletin = ejecutar_pipeline_completo(
        mocks={
            "s1": {"problema_avalancha_presente": True,
                   "tipo_problema": "new_snow"},
            "s3": {"factor_meteorologico": "NEVADA_RECIENTE",
                   "ventanas_criticas": 2},
        },
        ubicacion="La Parva Sector Alto",
    )
    assert boletin["nivel_eaws_24h"] >= 2  # la matriz produce ≥2 con nevada
```

### Criterio de éxito

Ronda 6 H4:
- % nivel 1-2 predicho sube de 58% → ≥ 70%
- Sesgo baja de +0.885 → ≤ +0.50
- QWK pasa a positivo (≥ 0.05)
- MAE baja de 1.230 → ≤ 0.90

---

## Orden de implementación

```
1. FIX-GEO   → 2h  → commit → correr test_clasificar_eaws.py → verde
2. FIX-H     → 3h  → commit → correr test_satelital.py → verde
3. FIX-S1    → 5h  → commit → correr test_s1_semantica.py → verde
4. Bump VERSION_GLOBAL a 7.0
5. Reprocesar retroactivo (reprocesar_con_estado.py)
6. Calcular Ronda 6 (07 + 08 validacion)
7. Actualizar RESULTADOS_VALIDACION.md
```

**Total estimado:** ~10h código + ~100min reproceso + métricas.

---

## Constraint crítico para los tres fixes

**No degradar MAE en tormentas.** Los 12 pares Snowlab con nivel ≥ 3
(tormentas) tienen MAE actual ≈ 0.75. Ninguno de los tres fixes debe
empeorar este valor. Verificar explícitamente en Ronda 6:

```python
# En 08_validacion_snowlab.py — agregar sección:
pares_tormenta = pares[pares["snowlab_nivel"] >= 3]
mae_tormenta = abs(pares_tormenta["andesai"] - pares_tormenta["snowlab"]).mean()
print(f"MAE tormentas (≥3): {mae_tormenta:.3f}  [objetivo: ≤ 1.00]")
```

---

## Post-v7.0 (no implementar ahora)

Estas ideas del Informe Técnico v7.0 son válidas pero agregan complejidad
antes de estabilizar las métricas base. Quedan para v7.5:

- Sliders continuos 0-100 tipo ALBINA en S5
- Subdivisión temporal mañana/tarde
- Gatekeeper Boolean `Liquid_Water` para nieve húmeda (esperar REQ-02 GEE)
- D1/D2 con High Uncertainty Flag en celdas de transición

---

## Archivos a modificar (resumen)

| Fix | Archivo principal | Archivos secundarios |
|-----|------------------|---------------------|
| FIX-GEO | `tool_clasificar_eaws.py` | Tests |
| FIX-H | `tool_analizar_imagenes.py` | `consultor_bigquery.py` (coords) |
| FIX-S1 | `prompts.py` (S1 + S5) | `schema_boletines.json`, `almacenador.py` |

**Archivos que NO se tocan:**
- `agentes/despliegue/` (Cloud Run sin cambios)
- `datos/` (Cloud Functions sin cambios)
- `notebooks_validacion/` (solo agregar métrica MAE tormentas en 08)
- `consultor_bigquery.py` (salvo coords para FIX-H si necesario)

---

*Referencia: Ronda 5 v6.2 — QWK H4=−0.031, H1/H3=−0.031*
*Target Ronda 6 v7.0 — QWK H4≥0.05, H1/H3≥+0.10*
*Proyecto GCP: `climas-chileno` | Branch: `feat/v7.0-fixes`*
