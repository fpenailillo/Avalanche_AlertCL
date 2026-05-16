# REQ-MEJORAS-MODELO-V1 — Mejoras post-validación AndesAI
**Fecha:** 2026-05-01  
**Basado en:** `reporte_validacion_andesai_2026.md` (commit `31a4d0c`)  
**Prioridad:** Alta — mejoras al modelo antes de nueva ronda de validación  
**Autor:** Francisco Peñailillo — UTFSM MTI 2024

---

## Contexto

La primera ronda de validación (abril 2026) identificó dos problemas distintos:

1. **Piso efectivo en nivel 3 (H4 — La Parva):** AndesAI sobreestima sistemáticamente en días de calma (+2.32 niveles, 86% de los casos). El sistema no puede confirmar baja peligrosidad porque S5 no recibe señales positivas de estabilidad del manto — solo detecta ausencia de señales activas. En tormentas funciona bien (MAE=0.75).

2. **Gap de transferibilidad Alpes (H1/H3):** QWK=0.109 vs benchmark Techel 2022 (0.59). Causas: dominio diferente, ERA5 sobreestima precipitación orográfica alpina, mapeo estación→sector SLF aproximado.

**Decisiones de diseño confirmadas:**
- Calibración: debe estar distribuida en cada agente especializado (no calibrador post-hoc centralizado en S5).
- Fuentes de datos: usar exclusivamente el stack Google (Earth Engine, Google Weather API, ERA5-Land vía GEE). No integrar fuentes externas regionales como CEAZA.
- Infraestructura estadística (bootstrap IC, McNemar): postergada para después de mejorar el modelo.

---

## REQ-01 — Feature de persistencia temporal en S5

**Problema:** S5 evalúa cada boletín de forma independiente. Sin memoria de días anteriores, no puede distinguir "calma sostenida" de "calma puntual".

**Solución:** Agregar como input a S5 un vector de persistencia derivado del historial de boletines propios en BigQuery.

**Implementación:**

1. En `agentes/s5_integrador/tool_integrar_eaws.py`, antes de llamar al LLM integrador, consultar BigQuery para obtener los últimos N boletines de la misma ubicación:

```python
# Tabla: clima.risk_bulletins (o donde se almacenen los boletines)
# Filtro: location_id = actual, fecha < hoy, ORDER BY fecha DESC LIMIT 7
```

2. Calcular features derivadas:
   - `dias_consecutivos_nivel_bajo`: contador de días consecutivos con nivel ≤ 2
   - `nivel_promedio_7d`: promedio de los últimos 7 boletines
   - `precipitacion_acumulada_72h`: desde S3/ERA5, suma últimas 72h
   - `tendencia`: diferencia nivel_hoy_menos_1 - nivel_hoy_menos_4 (positiva = escalando, negativa = bajando)

3. Incluir estas features en el prompt de S5 como sección explícita:

```
## Contexto histórico de la ubicación
- Días consecutivos con nivel ≤ 2: {dias_consecutivos_nivel_bajo}
- Nivel promedio últimos 7 días: {nivel_promedio_7d:.1f}
- Precipitación acumulada 72h: {precipitacion_acumulada_72h:.1f} mm
- Tendencia reciente: {tendencia} (negativo = condiciones mejorando)

Si días_consecutivos_nivel_bajo ≥ 4 Y precipitacion_acumulada_72h < 5mm,
considerar fuertemente que las condiciones de calma están confirmadas.
```

4. Agregar campo `persistence_features` al registro de boletín en BigQuery para trazabilidad.

**Archivos a modificar:**
- `agentes/s5_integrador/tool_integrar_eaws.py`
- `agentes/s5_integrador/prompts/integrador_prompt.py` (o equivalente)
- `agentes/consultor_bigquery/consultor_bigquery.py` (nuevo método `get_bulletin_history`)

**Tests requeridos:**
- Test unitario: `get_bulletin_history` retorna lista vacía cuando no hay historial (primera ejecución).
- Test integración: persistencia reduce nivel predicho en secuencia de días calmos sintéticos.

**Impacto esperado:** Reducir sobreestimación en días de calma. Si últimos 5 días fueron nivel 1-2 sin precipitación, S5 puede confirmar calma con más confianza.

---

## REQ-02 — GEE: extracción de features de estado del manto para S2/S5

**Problema:** S5 no tiene señales positivas de estabilidad. Las fuentes actuales (ERA5 meteorológico, SAR para nieve húmeda/seca) detectan eventos activos pero no confirman "manto consolidado y frío".

**Solución:** Extraer tres nuevas variables desde Google Earth Engine usando el script GEE ya existente para La Parva/Valle Nevado como base. Exportar a BigQuery tabla `imagenes_satelitales` (o nueva tabla `estado_manto_gee`).

### REQ-02a — LST MODIS (temperatura superficie)

**Fuente GEE:** `MODIS/061/MOD11A1` (Terra, diario, 1km) + `MODIS/061/MYD11A1` (Aqua).  
**Variable:** `LST_Day_1km` (escalar: K × 0.02 − 273.15 = °C).  
**Feature derivada:** `lst_superficie_celsius`, `lst_positivo_dias_consecutivos` (días seguidos con LST > 0°C).

```javascript
// En script GEE existente (La Parva bbox: west=-70.45, south=-33.45, east=-70.15, north=-33.25)
var lst = ee.ImageCollection('MODIS/061/MOD11A1')
  .filterDate(startDate, endDate)
  .filterBounds(geometry)
  .select('LST_Day_1km')
  .map(function(img) {
    return img.multiply(0.02).subtract(273.15)
      .rename('lst_celsius')
      .copyProperties(img, ['system:time_start']);
  });
```

**Interpretación para S5:**
- LST < -5°C sostenido → manto frío, metamorfismo lento, menor riesgo de avalanchas húmedas.
- LST > 0°C varios días → manto activándose, posible nieve húmeda.
- LST oscilando cerca de 0°C → ciclo diurno, riesgo vespertino.

### REQ-02b — SAR Sentinel-1: índice humedad superficial

**Fuente GEE:** `COPERNICUS/S1_GRD` (C-band, VV+VH, ~12 días revisita en La Parva).  
**Variable:** backscatter VV en dB sobre píxeles con pendiente 30-45° (ya clasificados en script GEE existente).  
**Feature derivada:** `sar_vv_db_media`, `sar_delta_vs_baseline` (cambio respecto a media de temporada).

```javascript
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterDate(startDate, endDate)
  .filterBounds(geometry)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .select(['VV', 'VH']);
// Calcular media en zona de pendiente crítica (30-45°)
// usar máscara de pendiente del script NASADEM existente
```

**Interpretación para S5:**
- VV cae > 3dB respecto a baseline → superficie húmeda → manto activo.
- VV estable o alto → superficie seca → manto consolidado.

### REQ-02c — ERA5-Land: temperatura del suelo como proxy manto basal

**Fuente GEE:** `ECMWF/ERA5_LAND/HOURLY` → `soil_temperature_level_1` (0-7cm) y `soil_temperature_level_2` (7-28cm).  
**Feature derivada:** `temp_suelo_l1_celsius`, `gradiente_termico_suelo` (diferencia L1-L2, positivo = manto enfriándose desde abajo).

**Interpretación para S5:** Gradiente térmico negativo sostenido (temperatura más fría en superficie que en profundidad) indica metamorfismo cinético activo — factor de riesgo para capas frágiles persistentes incluso en días sin precipitación aparente.

### Exportación a BigQuery

Crear o extender tabla BigQuery con schema:

```sql
-- Tabla: clima.estado_manto_gee
CREATE TABLE IF NOT EXISTS `climas-chileno.clima.estado_manto_gee` (
  fecha DATE NOT NULL,
  location_id STRING NOT NULL,         -- 'la_parva', 'valle_nevado', etc.
  lst_celsius FLOAT64,                  -- MODIS LST superficie
  lst_positivo_dias_consecutivos INT64, -- días seguidos LST > 0°C
  sar_vv_db FLOAT64,                    -- Sentinel-1 backscatter VV
  sar_delta_baseline FLOAT64,           -- cambio respecto a media temporada
  temp_suelo_l1_celsius FLOAT64,        -- ERA5-Land capa 0-7cm
  temp_suelo_l2_celsius FLOAT64,        -- ERA5-Land capa 7-28cm
  gradiente_termico FLOAT64,            -- L1 - L2 (°C)
  cobertura_nubosa_pct FLOAT64,         -- % cobertura nubosa MODIS QC
  fuente_lst STRING,                    -- 'MOD11A1' | 'MYD11A1' | 'ERA5_proxy'
  ingested_at TIMESTAMP
);
```

**Script Python a crear:** `pipelines/backfill_estado_manto_gee.py`  
Usar Earth Engine Python API (`import ee`) con autenticación via service account GCP (`climas-chileno`).

**Archivos a crear/modificar:**
- `pipelines/backfill_estado_manto_gee.py` (nuevo)
- `agentes/s2_satelital/tool_analizar_imagenes.py` — consumir `estado_manto_gee` como feature adicional
- `agentes/s5_integrador/tool_integrar_eaws.py` — incluir estado manto en contexto

**Tests requeridos:**
- Test: exportación GEE retorna al menos 1 fila por fecha en rango definido.
- Test: `tool_analizar_imagenes` no falla si `estado_manto_gee` retorna NULL (backward compatible).

---

## REQ-03 — Corrección sesgo ERA5 orográfico (H1/H3)

**Problema:** ERA5 @9km sobreestima precipitación en topografía alpina compleja. En los 24 pares suizos, el sesgo medio es -0.54 niveles (subestimación de peligro), parcialmente atribuible a que ERA5 sobreestima precipitación pero S5 no calibra por altitud/exposición.

**Solución:** Factor de corrección multiplicativo sobre precipitación ERA5 según altitud de la estación.

**Implementación en S3:**

```python
# En agentes/s3_meteorologico/tool_procesar_clima.py

ERA5_OROGRAPHIC_CORRECTION = {
    # (altitud_min, altitud_max): factor_multiplicativo
    (0, 1500): 1.0,       # sin corrección bajo 1500m
    (1500, 2500): 0.85,   # ERA5 sobreestima ~15% en zona andina media
    (2500, 3500): 0.75,   # sobreestima ~25% en zona andina alta
    (3500, 9999): 0.65,   # sobreestima ~35% sobre 3500m
}

def apply_orographic_correction(precipitacion_mm: float, altitud_m: float) -> float:
    """Aplica corrección orográfica a precipitación ERA5."""
    for (alt_min, alt_max), factor in ERA5_OROGRAPHIC_CORRECTION.items():
        if alt_min <= altitud_m < alt_max:
            return precipitacion_mm * factor
    return precipitacion_mm
```

**Nota:** Los factores de corrección son iniciales basados en literatura ERA5. Calibrar sobre los 24 pares suizos disponibles en `validacion_avalanchas.slf_danger_levels_qc` para ajustar por zona geográfica (Andes vs. Alpes pueden requerir factores distintos). Agregar campo `altitud_estacion_m` a la tabla de estaciones si no existe.

**Archivos a modificar:**
- `agentes/s3_meteorologico/tool_procesar_clima.py`
- `agentes/s3_meteorologico/schemas.py` (agregar `altitud_estacion_m` al schema de estación)

**Tests requeridos:**
- Test unitario: `apply_orographic_correction(10.0, 3000)` retorna valor < 10.0.
- Test: corrección no rompe pipeline en estaciones sin altitud registrada (default altitud=0 → factor 1.0).

---

## REQ-04 — Mapeo estación→sector SLF preciso (H1/H3)

**Problema:** El mapeo actual usa el nivel modal del cantón como proxy del nivel del sector SLF más cercano a cada estación, introduciendo ruido en el ground truth.

**Solución:** Para cada estación suiza, identificar el sector SLF geográficamente más cercano usando coordenadas de los sectores SLF disponibles en `validacion_avalanchas.slf_danger_levels_qc`.

**Implementación:**

1. Consultar sectores SLF únicos con sus coordenadas aproximadas (o usar el prefijo de sector para inferir cantón/región).
2. Para cada estación AndesAI suiza (Interlaken, Matterhorn Zermatt, St. Moritz), calcular distancia geográfica a todos los sectores disponibles y asignar el más cercano.
3. Crear tabla de mapeo estático:

```python
# En agentes/validacion/mapeo_estaciones_slf.py
STATION_TO_SLF_SECTOR = {
    'interlaken': {
        'sector_id': '4113',           # actual — verificar con coordenadas
        'lat': 46.6863, 'lon': 7.8632, # coordenadas Interlaken
        'altitud_m': 570,
        'canton': 'Bern'
    },
    'matterhorn_zermatt': {
        'sector_id': '2223',           # verificar — Zermatt está en sector específico del Valais
        'lat': 46.0207, 'lon': 7.7491,
        'altitud_m': 1608,
        'canton': 'Valais'
    },
    'st_moritz': {
        'sector_id': '6113',           # verificar con dataset SLF
        'lat': 46.4975, 'lon': 9.8437,
        'altitud_m': 1856,
        'canton': 'Graubuenden'
    }
}
```

4. Al ejecutar validación, usar sector exacto en lugar de nivel modal del cantón.

**Archivos a crear/modificar:**
- `agentes/validacion/mapeo_estaciones_slf.py` (nuevo o ampliar existente)
- `notebooks_validacion/07_validacion_slf_suiza.py` — usar nuevo mapeo

**Tests requeridos:**
- Test: todos los sector_id del mapeo existen en `validacion_avalanchas.slf_danger_levels_qc`.

---

## REQ-05 — Activar WeatherNext 2 en S3

**Problema:** WeatherNext 2 está implementado (según notas de desarrollo) pero no activado por defecto.

**Solución:** Activar `USE_WEATHERNEXT2=true` en configuración de producción y ejecutar comparativa sobre las 24 fechas de validación suiza para medir impacto.

**Implementación:**

1. Verificar que `USE_WEATHERNEXT2` está correctamente documentado en `cloud_run/orquestador/config.py` o equivalente.
2. Activar en Secret Manager GCP (`climas-chileno`) o variable de entorno del Cloud Run Job `orquestador-avalanchas`.
3. Ejecutar backfill sobre las 24 fechas suizas de validación con WeatherNext 2 activo.
4. Comparar QWK/F1 Ronda 2 (ERA5) vs. Ronda 3 (WeatherNext 2) sobre los mismos 24 pares.

**Entregable:** Tabla comparativa Ronda 2 vs. Ronda 3 para incluir en tesis (cuantifica contribución de WeatherNext 2 a H1/H3).

**Archivos a revisar:**
- `agentes/s3_meteorologico/` — buscar `USE_WEATHERNEXT2` o `weathernext`
- `cloud_run/orquestador/` — configuración de variables

---

## Orden de ejecución recomendado

| Orden | REQ | Impacto en hipótesis | Esfuerzo estimado |
|-------|-----|---------------------|-------------------|
| 1 | REQ-01 (persistencia temporal) | H4 directamente | ~6h |
| 2 | REQ-02a (LST MODIS) | H4 señal positiva de calma | ~8h |
| 3 | REQ-04 (mapeo SLF preciso) | H1/H3 ground truth | ~3h |
| 4 | REQ-03 (corrección ERA5) | H1/H3 sesgo precipitación | ~4h |
| 5 | REQ-02b (SAR humedad) | H4 señal manto activo | ~8h |
| 6 | REQ-02c (ERA5 suelo) | H4 señal manto basal | ~5h |
| 7 | REQ-05 (WeatherNext 2) | H1/H3 meteorología | ~3h |

**Total estimado:** ~37h de desarrollo + re-validación sobre los 87 pares Snowlab y 24 pares SLF.

---

## Criterio de éxito para esta iteración

| Métrica | Actual | Objetivo iteración |
|---------|--------|--------------------|
| QWK Snowlab (H4) | -0.016 | ≥ 0.20 |
| MAE calma (Snowlab ≤ 2) | 2.32 | ≤ 1.50 |
| Sesgo calma | +2.32 | ≤ +1.00 |
| QWK SLF Suiza (H3) | 0.109 | ≥ 0.20 |
| MAE tormenta (Snowlab ≥ 3) | 0.75 | mantener ≤ 1.0 |

**Constraint crítico:** REQ-01 y REQ-02 no deben degradar el MAE en condiciones de tormenta (actualmente 0.75) — verificar con los 12 pares de tormenta en cada PR.

---

*Referencia: `reporte_validacion_andesai_2026.md` · Proyecto GCP: `climas-chileno` · Rama sugerida: `feat/mejoras-modelo-v2`*
