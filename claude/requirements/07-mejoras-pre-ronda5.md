# REQ-07 — Mejoras pre-Ronda 5 (v6.0 → v6.1)
**Fecha:** 2026-05-03
**Basado en:** EDA `docs/validacion/EDA_DATOS_VALIDACION.md` + análisis causas raíz `notebooks_validacion/09_diagnostico_causas_raiz_v5.ipynb`
**Prioridad:** Alta — deben implementarse antes de lanzar el reproceso Ronda 5
**Autor:** Francisco Peñailillo — UTFSM MTI 2024

---

## Contexto

La Ronda 4 (v5.0) con los FIX-T/V/D implementados mejoró H4 parcialmente (sesgo +2.023→+1.609),
pero el análisis EDA identificó tres problemas adicionales que deben resolverse antes de reprocesar:

1. **REQ-07a (crítico):** Los scripts de validación no filtran por versión → métricas de Ronda 5 serán incorrectas por duplicados v5+v6 en BQ.
2. **REQ-07b (alto):** `FUSION_ACTIVA` se activa en días sin precipitación reciente → sigue generando piso nivel 3 incluso con FIX-T/V/D aplicados.
3. **REQ-07c (medio):** Las imágenes satelitales del reproceso son de 2026, no de las fechas históricas 2024-2025 → el ViT/SAR usa estado actual del manto como proxy.

Orden de ejecución recomendado: **07a → 07b → reprocesar → 07c** (07c es opcional para Ronda 5).

---

## REQ-07a — Filtro de versión en scripts de validación

### Objetivo
Asegurar que `07_validacion_slf_suiza.py` y `08_validacion_snowlab.py` evalúen solo boletines v6 al calcular métricas de Ronda 5.

### Estado actual
Ambos scripts consultan `clima.boletines_riesgo` sin filtrar por `version_prompts`. Tras el reproceso v6 habrá registros v5+v6 para las mismas `(nombre_ubicacion, fecha_emision)`:
- Suiza: 25 pares con v5 + v6 (ambos en BQ, BigQuery no tiene UNIQUE constraint)
- La Parva: 90 pares con v3.2 + v5 + v6 (hasta 3 versiones por par)

Sin filtro, las queries retornan filas duplicadas y la métrica final mezcla versiones.

### Estado deseado
Ambos scripts filtran por `version_prompts = 'v6.0'` por defecto, con argumento `--version` opcional para comparar rondas anteriores.

### Tareas técnicas

**07_validacion_slf_suiza.py** — función `obtener_nuestros_boletines()` (línea 76):

```python
# Agregar parámetro version_filter con default 'v6'
def obtener_nuestros_boletines(
    cliente, ubicaciones, fechas, version_filter="v6"
) -> dict:
    query = f"""
        SELECT nombre_ubicacion, DATE(fecha_emision) as fecha, nivel_eaws_24h
        FROM `{GCP_PROJECT}.clima.boletines_riesgo`
        WHERE nombre_ubicacion IN ({ubicaciones_sql})
          AND DATE(fecha_emision) IN ({fechas_sql})
          AND STARTS_WITH(version_prompts, @version)
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY nombre_ubicacion, DATE(fecha_emision)
            ORDER BY fecha_emision DESC
        ) = 1
        ORDER BY nombre_ubicacion, fecha
    """
```

La cláusula `QUALIFY ROW_NUMBER()` garantiza un solo registro por par incluso si hay múltiples del mismo prefijo de versión.

Agregar argumento CLI:
```python
parser.add_argument("--version", default="v6",
    help="Prefijo de versión a evaluar (default: v6)")
```

**08_validacion_snowlab.py** — constante `SQL_BOLETINES_ANDESAI` (línea 74):

```python
SQL_BOLETINES_ANDESAI = """
SELECT
    br.nombre_ubicacion,
    DATE(br.fecha_emision)  AS fecha_eaws,
    br.nivel_eaws_24h,
    br.nivel_eaws_48h,
    br.nivel_eaws_72h
FROM `climas-chileno.clima.boletines_riesgo` br
WHERE br.nombre_ubicacion IN (
    'La Parva Sector Alto', 'La Parva Sector Medio', 'La Parva Sector Bajo'
)
  AND br.nivel_eaws_24h IS NOT NULL
  AND DATE(br.fecha_emision) >= '2024-06-01'
  AND STARTS_WITH(br.version_prompts, 'v6')
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY br.nombre_ubicacion, DATE(br.fecha_emision)
    ORDER BY br.fecha_emision DESC
) = 1
ORDER BY nombre_ubicacion, fecha_eaws
"""
```

Agregar argumento CLI equivalente al de 07.

### Criterios de aceptación
- Ejecutar `python 07_validacion_slf_suiza.py` con solo v5 en BQ → imprime "0 boletines encontrados, versión=v6"
- Ejecutar `python 07_validacion_slf_suiza.py --version v5` → retorna los 25 pares v5 correctamente
- Ejecutar `python 08_validacion_snowlab.py` → sin duplicados; `len(df_eaws)` == cantidad exacta de fechas únicas v6 × 3 sectores

### Estimación
**~30 min.** Cambio quirúrgico en 2 archivos.

---

## REQ-07b — FIX-S3: umbral FUSION_ACTIVA condicional a precipitación reciente

### Objetivo
Evitar que el factor meteorológico `FUSION_ACTIVA` active el piso de nivel 3 en días de ciclo térmico normal sin precipitación reciente, diferenciando el "ciclo de fusión activo" del "ciclo térmico basal andino".

### Estado actual
En `agentes/subagentes/subagente_meteorologico/` el factor `FUSION_ACTIVA` se asigna cuando:
```
diurno_temp_max > 0°C  AND  nocturno_temp_min < −2°C
```
Este ciclo ocurre en ~90% de los días de verano andino en La Parva, independientemente de si hay carga de nieve activa. El EDA (sección 6.3) confirma que es el principal driver del sesgo en H4, más allá del tamano (CR-1).

**Diagnóstico más preciso que lo registrado en CR-1/2:** el notebook 09 identificó tamano=5 como causa raíz, pero el EDA aclara que `FUSION_ACTIVA` también mantiene el nivel en 3 incluso cuando FIX-T capea el tamano en 3 — porque con tamano=3 + `FUSION_ACTIVA` + `a_few` la matriz EAWS puede seguir dando nivel 2-3. La eliminación del bump de ventanas (FIX-V) ayuda, pero si `FUSION_ACTIVA` es el factor base, el nivel no baja a 1.

### Estado deseado
`FUSION_ACTIVA` se reclasifica como `CICLO_DIURNO_NORMAL` (factor neutro, ya implementado en v5) cuando se cumplen las tres condiciones simultáneas:
1. `precipitacion_acumulada_72h < 5 mm` (sin carga de nieve reciente)
2. `hn48 == 0` (sin altura de nieve nueva en 48h)
3. `temperatura_max_72h < umbral_fusion_significativa` (no hay fusión con agua libre activa)

Cuando las tres se cumplen, el ciclo térmico es "basal andino" y no debe empujar el nivel.

### Tareas técnicas

**Archivo:** `agentes/subagentes/subagente_meteorologico/tools/tool_ventanas_criticas.py`
(y/o el módulo que clasifica `factor_meteorologico`)

1. Identificar la función que asigna `FUSION_ACTIVA`. Buscar:
```bash
grep -n "FUSION_ACTIVA\|factor_meteorologico\|diurno_temp_max" \
  agentes/subagentes/subagente_meteorologico/tools/tool_ventanas_criticas.py
```

2. Agregar condición de precipitación reciente como guard:
```python
def _es_fusion_activa_real(
    temp_max: float,
    temp_min: float,
    precip_72h: float,
    hn48: float,
) -> bool:
    """
    True solo si hay ciclo de fusión con carga de nieve activa.
    Evita clasificar el ciclo térmico basal andino como FUSION_ACTIVA.
    """
    ciclo_termico = temp_max > 0.0 and temp_min < -2.0
    if not ciclo_termico:
        return False
    # Con carga de nieve activa: fusión real
    if precip_72h >= 5.0 or hn48 > 0:
        return True
    # Sin carga: ciclo basal → tratar como CICLO_DIURNO_NORMAL
    return False
```

3. Agregar campo `precipitacion_acumulada_72h` al contexto meteorológico que ya se consulta en S3 (disponible en `condiciones_actuales` y `pronostico_horas`).

4. Actualizar prompt de S3 para reflejar el nuevo criterio en el sistema de clasificación de factores.

5. Mantener `FUSION_ACTIVA` como factor activo cuando `precip_72h ≥ 5 mm` o `hn48 > 0` — el comportamiento en tormentas no cambia.

### Criterios de aceptación
- Test unitario: día calmo (temp_max=8°C, temp_min=-5°C, precip_72h=0, hn48=0) → `factor_meteorologico='CICLO_DIURNO_NORMAL'`
- Test unitario: día post-nevada (temp_max=5°C, temp_min=-3°C, precip_72h=20, hn48=15) → `factor_meteorologico='FUSION_ACTIVA'`
- Simulación con datos reales: para las 90 fechas Snowlab con `factor_meteo=FUSION_ACTIVA` en v5, verificar que `_es_fusion_activa_real()` reclasifica ≥50% como `CICLO_DIURNO_NORMAL`
- Tests existentes: `python -m pytest agentes/tests/ -v --tb=short -q` sigue pasando (256+)

### Riesgos y mitigaciones
| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| `precip_72h` no disponible en todas las fechas históricas de reproceso | Media | Usar fallback: si campo es None, mantener comportamiento v5 (FUSION_ACTIVA cuando ciclo térmico activo) |
| Reclasificar días de tormenta como calmos | Baja | Guard explícita: si `hn48 > 0` OR `precip_72h ≥ 5`, siempre FUSION_ACTIVA independientemente del resto |
| Impacto negativo en detección de tormentas (MAE=0.75 actual) | Baja | Tests comparativos en los 12 pares Snowlab de nivel ≥ 3 antes de reprocesar |

### Estimación
**~3-4 horas.** Incluye identificar la función, implementar guard, agregar test unitario, y verificación con los 90 pares Snowlab existentes (v5) antes de reprocesar.

---

## REQ-07c — Backfill de imágenes satelitales para fechas históricas 2024-2025

### Objetivo
Generar entradas en `clima.imagenes_satelitales` para las 30 fechas Snowlab (2024-06-15 → 2025-09-19) y las 10 fechas suizas (2023-12-01 → 2024-04-15), de modo que el reproceso v6 use datos satelitales del contexto temporal correcto en lugar de imágenes de 2026.

### Estado actual
El EDA (sección 9.4) documenta el problema: `imagenes_satelitales` cubre `mar 2026 – may 2026`. Durante el reproceso, el ViT y SAR leen el estado actual del manto (otoño 2026 en los Andes — manto en retroceso), no el estado en las fechas de validación (invierno 2024-2025 — manto en crecimiento/estable).

Esto introduce un sesgo sistemático: el reproceso usa contexto de manto empobrecido cuando debería usar contexto de manto activo.

### Estado deseado
Para cada fecha de validación existe al menos un registro en `imagenes_satelitales` (o fecha ±3 días) con NDSI, SAR, LST y ERA5 correspondientes al período histórico correcto.

La Cloud Function `extractor_historico` (REQ-06, commit `9e92638`) ya tiene capacidad de backfill histórico para ERA5/Open-Meteo. Necesita adaptarse para imágenes satelitales.

### Tareas técnicas

1. **Verificar disponibilidad de datos Sentinel-2/SAR históricos en GEE** para las 30+10 fechas de validación:
```python
# Google Earth Engine puede acceder a datos históricos de Sentinel-2 (desde 2015)
# y Sentinel-1 SAR (desde 2014). Verificar que las fechas de La Parva estén cubiertas.
import ee
ee.Initialize()
col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
    .filterBounds(ee.Geometry.Point([-70.298, -33.354])) \
    .filterDate("2024-06-01", "2024-09-30") \
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
print(col.size().getInfo())  # esperado: ≥5 imágenes útiles
```

2. **Adaptar script `agentes/datos/backfill/backfill_satelital.py`** para aceptar fechas históricas arbitrarias (actualmente está hardcodeado para estaciones suizas con fecha actual). Agregar argumento `--fechas-csv` que reciba un archivo con `ubicacion,fecha` por línea.

3. **Ejecutar backfill** para las 40 fechas de validación (30 Snowlab + 10 Suiza):
```bash
python agentes/datos/backfill/backfill_satelital.py \
    --fechas-csv notebooks_validacion/fechas_validacion_historico.csv \
    --proyecto climas-chileno
```

4. **Verificar cobertura post-backfill** antes de reprocesar:
```sql
SELECT DATE(fecha_captura), nombre_ubicacion, COUNT(*) as n
FROM `climas-chileno.clima.imagenes_satelitales`
WHERE nombre_ubicacion IN ('La Parva Sector Alto','La Parva Sector Medio','La Parva Sector Bajo')
  AND DATE(fecha_captura) BETWEEN '2024-06-01' AND '2025-10-01'
GROUP BY 1, 2
ORDER BY 1
```

### Criterios de aceptación
- Al menos 25/30 fechas Snowlab tienen registro en `imagenes_satelitales` (±3 días)
- Al menos 8/10 fechas Suiza tienen registro
- NDSI disponible (no NULL) en ≥80% de los registros generados
- SAR disponible en ≥20% (limitado por cadencia Sentinel-1, aceptable)

### Riesgos y mitigaciones
| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| Alta cobertura nubosa en fechas específicas (invierno andino) | Alta | Aceptar ±7 días; SAR no depende de nubes |
| Quota GEE excedida (Community: 150 EECU-hr/mes) | Media | Procesar en lotes de 10 fechas por día; monitorear quota |
| Datos Suiza diciembre 2023 con oscuridad / nieve total (nubosidad) | Alta | Usar SAR primariamente para Alpes en invierno; NDSI=NULL es aceptable |

### Estimación
**~6-8 horas.** Incluye adaptar el script, ejecutar el backfill, y verificar cobertura.

> **Nota:** REQ-07c es OPCIONAL para Ronda 5. Con FIX-T/V/D + REQ-07b ya se espera una mejora significativa en H4. El backfill histórico mejora la calidad del contexto ViT, pero el sesgo principal (piso nivel 3) viene de la lógica EAWS/S3, no del ViT. Priorizar 07a y 07b primero.

---

## Hallazgos adicionales del EDA (no requieren código, relevantes para tesis)

### Independencia estadística de los pares H4
Los 87 pares de H4 no son estadísticamente independientes: los 3 sectores de La Parva están a **<3 km entre sí** y comparten masa de aire (EDA sección 7). El n efectivo para intervalos de confianza es **~29 boletines Snowlab**, no 87 pares.

Para la tesis: reportar ambos (n=87 como "pares emparejados" y n=29 como "boletines Snowlab únicos"). Los IC 95% deben calcularse con bootstrap sobre los 29 boletines, no sobre los 87 pares, para no inflar artificialmente la precisión.

### Umbral H4 inconsistente entre documentos
- `docs/validacion/RESULTADOS_VALIDACION.md` → H4 objetivo: QWK ≥ 0.60
- `notebooks_validacion/RESULTADOS_VALIDACION.md` → H4 objetivo: QWK ≥ 0.40

Definir el umbral oficial para la tesis y unificar ambos documentos. El CLAUDE.md también especifica ≥ 0.60 (tabla de hipótesis). **Recomendación:** usar ≥ 0.40 como umbral "razonable para tesis" y documentar ≥ 0.60 como objetivo aspiracional de sistema operacional.

### `docs/validacion/RESULTADOS_VALIDACION.md` desactualizado
Solo llega a Ronda 3 (v4.0). No incluye Ronda 4 (v5.0). Actualizar después de Ronda 5.

---

## Secuencia recomendada de ejecución

```
1. Implementar REQ-07a  (30 min)   → filtro version_prompts en 07/08
2. Implementar REQ-07b  (3-4 h)   → FIX-S3 FUSION_ACTIVA condicional
3. Ejecutar reproceso   (3.5 h)   → python notebooks_validacion/reprocesar_retroactivo.py
4. Ejecutar Ronda 5     (15 min)  → python 07_validacion_slf_suiza.py && python 08_validacion_snowlab.py
5. REQ-07c (opcional)   (6-8 h)   → backfill histórico satelital → Ronda 6
```

---

## Referencias técnicas
- `notebooks_validacion/09_diagnostico_causas_raiz_v5.ipynb` — simulaciones CR-1/2/3/4 y FIX-T/V/D
- `docs/validacion/EDA_DATOS_VALIDACION.md` — estadísticas detalladas de todas las tablas BQ
- `docs/validacion/reporte_validacion_andesai_2026.md` — narrative report con par-a-par Suiza
- `agentes/subagentes/subagente_meteorologico/tools/tool_ventanas_criticas.py` — lógica S3 (FIX-S3)
- `notebooks_validacion/reprocesar_retroactivo.py` — script reproceso (v6, 120 runs)
- `agentes/datos/backfill/backfill_satelital.py` — base para REQ-07c
- EDA sección 6.3: threshold exacto FUSION_ACTIVA (`temp_max > 0°C AND temp_min < -2°C`)
- EDA sección 9.4: limitación metodológica datos satelitales (2026 vs 2024-2025)
