# REQ-2026-XX: Integración del Dataset Caro et al. (2026) en AndesAI

**Estado**: Pendiente
**Prioridad**: Alta
**Fecha**: 2026-05-21
**Autor**: Francisco Peñailillo (Pancho)
**Director de tesis**: Dr. Mauricio Solar
**Skill principal**: `snow-alert-dev`
**Flujos involucrados**: F3 (data pipeline), F4 (academic validation), F6 (thesis documentation)

---

## 1. Contexto

El paper **Caro et al. (2026)** publicó en *Earth System Science Data* el primer dataset
diario homogeneizado y con control de calidad de profundidad de nieve (SD) para los
Andes del Sur, periodo 2010–2024, integrando 81 estaciones de DGA, CEAZA, UdeChile,
CIEP e IANIGLA.

- **DOI dataset**: 10.5281/zenodo.20089265
- **Repo QC**: github.com/javiermedinamen-art/hidromet/tree/main/sd_cleaning_sample
- **Herramienta interactiva**: javiermedinamen-art.github.io/hidromet

Este recurso es directamente relevante para AndesAI por tres razones:

1. Provee **ground truth validado** para nuestra zona piloto (cuenca del Maipo,
   21 estaciones, incluyendo La Parva, Farellones, Laguna Negra, Las Melosas).
2. Documenta un **hallazgo no-lineal SD–elevación** que invalida el supuesto de
   gradiente positivo lineal asumido por estudios previos y por defecto en
   modelos transferidos desde SLF (Suiza).
3. Publica una **metodología de QC replicable y de código abierto** (MAD spike
   removal, zero-level correction, physical range check, PCI multivariable) que
   podemos adoptar y adaptar.

Este requerimiento agrupa tres tareas que comparten contexto (el paper) pero
generan entregables independientes en infraestructura, código y documentación.

---

## 2. Objetivos

### Tarea 1 — Ground Truth Validado para Zona de Estudio

Ingerir las 21 estaciones de la cuenca del Maipo (y opcionalmente 7 de Elqui
para análisis comparativo) del dataset Caro et al. 2026 a una nueva tabla de
BigQuery en el dataset `clima`, con esquema normalizado y trazabilidad de
fuente. Esta tabla servirá como referencia de validación para:

- Subagente S3 (meteorológico): comparar inferencias con observaciones
- Subagente S1 (PINNs topográfico): validar predicciones de acumulación
- Subagente S5 (integrador EAWS): backtesting de boletines pasados

### Tarea 2 — Hallazgo Crítico Incorporado a Marco Teórico y Conclusiones

Documentar en el capítulo correspondiente de la tesis el hallazgo de
no-linealidad SD–elevación en cuenca del Maipo (pico en ~3,300 m, decaimiento
sobre 4,000 m por sublimación inducida por viento) y sus implicancias para:

- La calibración del transfer learning desde SLF a condiciones chilenas
- El diseño del subagente S1 (PINNs) para inferencia de acumulación
- La definición de zonas de iniciación de avalanchas en el rango altitudinal
  donde coincide máximo de pendiente crítica (30–45°) con máximo de SD
- Las conclusiones de tesis sobre adaptación regional del modelo

### Tarea 3 — Adopción de Metodología QC Replicable

Adaptar el procedimiento de QC del paper a nuestro pipeline de ingesta DGA en
GCP, implementando como módulo Python reutilizable:

- MAD spike removal por cuenca
- Zero-level correction con ventana móvil
- Physical range check parametrizable
- Versión adaptada del Physical Consistency Index (PCI) para validar
  consistencia de pronósticos (no solo observaciones históricas)

---

## 3. Tareas Detalladas

### 3.1 Tarea 1: Ingesta del Dataset Caro et al. 2026

#### 3.1.1 Descarga y exploración inicial

```bash
# Crear directorio de trabajo
mkdir -p data/external/caro_2026
cd data/external/caro_2026

# Descargar desde Zenodo
wget https://zenodo.org/records/20089265/files/[archivo].zip
unzip [archivo].zip
```

Antes de proceder, ejecutar exploración:
- Listar estructura del dataset (formatos, archivos, metadata)
- Identificar archivos correspondientes a estaciones del Maipo
- Verificar formato temporal (diario, periodo 2010–2024)
- Confirmar que existen versiones raw y clean

#### 3.1.2 Diseño del esquema BigQuery

Crear tabla `climas-chileno.clima.snow_depth_caro_2026` con esquema:

```sql
CREATE TABLE `climas-chileno.clima.snow_depth_caro_2026` (
  station_id STRING NOT NULL,
  station_name STRING NOT NULL,
  basin STRING NOT NULL,
  andean_zone STRING NOT NULL,  -- 'Arid', 'Mediterranean', 'Wet'
  country STRING NOT NULL,       -- 'CL', 'AR'
  latitude FLOAT64 NOT NULL,
  longitude FLOAT64 NOT NULL,
  elevation_m FLOAT64 NOT NULL,
  observation_date DATE NOT NULL,
  snow_depth_cm FLOAT64,
  qc_status STRING NOT NULL,     -- 'raw' o 'clean'
  data_source STRING NOT NULL,   -- 'DGA', 'CEAZA', 'UdeChile', 'CIEP', 'IANIGLA'
  sensor_model STRING,           -- 'Campbell/SR50A', 'Lufft/SHM31', etc.
  ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  paper_reference STRING DEFAULT 'Caro et al. 2026, doi:10.5194/essd-2026-324'
)
PARTITION BY observation_date
CLUSTER BY station_id, basin;
```

#### 3.1.3 Pipeline de ingesta

Crear `src/ingestion/load_caro_2026.py` con:

```python
"""
Carga del dataset Caro et al. 2026 (Zenodo 10.5281/zenodo.20089265)
a BigQuery clima.snow_depth_caro_2026.

Prioriza estaciones de cuenca del Maipo y Elqui para validación
contra subagentes AndesAI.
"""

PRIORITY_STATIONS_MAIPO = [
    'La Parva', 'Farellones', 'Laguna Negra', 'Las Melosas',
    'Las Hualtatas', 'Valle Echaurren Norte', 'Termas del Plomo',
    'Portillo Argentino', 'G. Tupungatito Bajo', 'G. Olivares Alfa',
    'G. Olivares Gamma', 'G. Juncal Sur', 'Valle Olivares',
    'AMTC10', 'AMTC12', 'AMTC13', 'AMTC8',
    'Piuquenes6', 'Piuquenes7', 'Piuquenes10', 'Piuquenes14'
]

PRIORITY_STATIONS_ELQUI = [
    'Tapado (TPF)', 'G. Tapado Corrales', 'Los Corrales',
    'La Laguna', 'Llano de Las Liebres', 'Cerro Olivares', 'El Jote'
]

# Tareas:
# 1. Cargar archivos del dataset (CSV o NetCDF según formato)
# 2. Filtrar estaciones prioritarias
# 3. Reorganizar a esquema long format (una fila por estación-fecha)
# 4. Cargar metadata de Table A1 del paper
# 5. Cargar ambas versiones (raw y clean) con qc_status
# 6. Insertar en BigQuery con verificación de duplicados
# 7. Generar reporte de ingesta (estaciones cargadas, periodo, gaps)
```

#### 3.1.4 Validación post-ingesta

Ejecutar queries de validación:

```sql
-- Conteo por estación y zona
SELECT
  station_name,
  basin,
  COUNT(*) AS total_obs,
  COUNT(snow_depth_cm) AS valid_obs,
  MIN(observation_date) AS first_obs,
  MAX(observation_date) AS last_obs,
  ROUND(AVG(snow_depth_cm), 2) AS avg_sd_cm
FROM `climas-chileno.clima.snow_depth_caro_2026`
WHERE qc_status = 'clean'
GROUP BY station_name, basin
ORDER BY basin, station_name;

-- Verificar gap entre raw y clean
SELECT
  station_name,
  COUNT(CASE WHEN qc_status = 'raw' THEN 1 END) AS raw_obs,
  COUNT(CASE WHEN qc_status = 'clean' THEN 1 END) AS clean_obs,
  ROUND(
    100.0 * (1 - COUNT(CASE WHEN qc_status = 'clean' THEN 1 END) /
                  COUNT(CASE WHEN qc_status = 'raw' THEN 1 END)),
    2
  ) AS pct_removed_by_qc
FROM `climas-chileno.clima.snow_depth_caro_2026`
GROUP BY station_name
ORDER BY pct_removed_by_qc DESC;
```

#### 3.1.5 Documentación

- Crear `docs/datasets/caro_2026.md` con: origen, esquema, estaciones cubiertas,
  cómo citar, limitaciones conocidas
- Actualizar `log_claude.md` con sesión de ingesta

---

### 3.2 Tarea 2: Documentación del Hallazgo No-Lineal SD–Elevación

#### 3.2.1 Análisis exploratorio reproducible

Crear notebook `notebooks/sd_elevation_analysis.ipynb` que:

1. Consulte `clima.snow_depth_caro_2026` filtrando cuenca del Maipo, periodo
   accumulation (mayo-octubre)
2. Reproduzca el análisis del paper (Figura 5 y 6):
   - CDF de SD por estación, agrupado en años secos/normales/húmedos
   - Percentiles 25, 50, 75 por estación vs. elevación
   - Identificación del pico de acumulación por cuenca
3. Compare con SLF (datos suizos) si están disponibles, mostrando contraste
4. Genere figuras para incluir en la tesis

#### 3.2.2 Redacción de sección en marco teórico

Agregar al capítulo correspondiente (probablemente "Estado del Arte" o
"Caracterización del Manto Nival Andino") una subsección que cubra:

**Estructura sugerida** (~1.5 páginas, IEEE Arial 12pt):

> **X.X Distribución no-lineal de profundidad de nieve con elevación en los Andes Centrales**
>
> Estudios recientes han documentado que la relación entre profundidad de nieve
> (SD) y elevación en los Andes del Sur no sigue un patrón lineal positivo, como
> se asumía en trabajos previos basados en redes observacionales limitadas
> [Cornwell et al. 2016; Cortés & Margulis 2017].
>
> Caro et al. [2026], analizando 21 estaciones validadas en la cuenca del Maipo
> (33°S), reportan que la acumulación máxima de nieve se localiza
> aproximadamente a 3,300 m s.n.m., con disminución progresiva sobre los
> 4,000 m. Este patrón es consistente con estudios localizados que documentan
> sublimación intensificada por exposición al viento sobre los 4,500 m
> [Ayala et al. 2017, glaciar Juncal Norte].
>
> Esta no-linealidad tiene tres implicancias críticas para AndesAI:
>
> 1. **Coincidencia espacial con zonas de iniciación EAWS**: El rango de máxima
>    acumulación (3,000–3,500 m) coincide con elevaciones donde dominan
>    pendientes de 30–45°, rango crítico para iniciación de avalanchas según
>    metodología EAWS.
>
> 2. **Limitación del transfer learning directo desde SLF**: Los modelos
>    entrenados con datos del Swiss SLF asumen condiciones alpinas donde la
>    sublimación es menor y la acumulación crece monotónicamente con elevación.
>    Aplicar estos modelos sin recalibración subestima la acumulación a media
>    elevación y sobreestima a alta elevación en condiciones chilenas.
>
> 3. **Necesidad de incorporar exposición al viento en S1 (PINNs)**: Las
>    variables explicativas del subagente topográfico deben incluir índices
>    de exposición eólica, no solo elevación y pendiente.

#### 3.2.3 Redacción de párrafo en conclusiones

Agregar a la sección de conclusiones de la tesis:

> Este trabajo confirma la relevancia del hallazgo de Caro et al. [2026]
> respecto a la no-linealidad de la relación SD–elevación en los Andes
> Centrales chilenos. Al incorporar este patrón en la arquitectura de AndesAI
> —específicamente en el subagente S1 mediante variables de exposición eólica
> y en el subagente S5 mediante recalibración de umbrales EAWS por banda
> altitudinal—, el sistema logra reducir el error de pronóstico de
> acumulación en X% respecto a una implementación de transfer learning directo
> desde Swiss SLF. Este resultado sugiere que el desarrollo de sistemas
> operacionales de pronóstico de avalanchas en regiones de climatología
> continental requiere adaptaciones regionales fundamentadas en datos
> observacionales locales validados, y no es trasladable mecánicamente desde
> sistemas alpinos europeos.

#### 3.2.4 Actualizar tabla de referencias IEEE

Insertar en la lista de referencias (renumerar según orden de aparición):

```
[XX] A. Caro et al., "The Southern Andes Daily Snow Depth Dataset (2010–2024):
     Quality-Controlled Dataset from Chile and Argentina," Earth System Science
     Data Discussions, in review, 2026. doi: 10.5194/essd-2026-324
```

---

### 3.3 Tarea 3: Adopción de Metodología QC

#### 3.3.1 Estudio del código de referencia

Clonar y estudiar el repo de referencia:

```bash
git clone https://github.com/javiermedinamen-art/hidromet.git
cd hidromet/sd_cleaning_sample
# Analizar implementación aplicada a Valle Olivares (33°S)
```

Documentar en `docs/qc/caro_reference_notes.md`:
- Parámetros usados (ventanas, umbrales k, rangos físicos)
- Estructura de funciones
- Dependencias

#### 3.3.2 Implementación adaptada para AndesAI

Crear módulo `src/qc/snow_depth_qc.py`:

```python
"""
Control de calidad para observaciones de profundidad de nieve.
Adaptado de Caro et al. (2026) - github.com/javiermedinamen-art/hidromet

Diferencias con el paper:
- Procesamiento incremental (no batch) para datos en streaming desde DGA
- Parametrización por estación, no solo por cuenca
- Integración con BigQuery via google-cloud-bigquery
- Métricas exportadas a Cloud Monitoring para observabilidad
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class QCParameters:
    """Parámetros de QC por zona o estación."""
    zero_level_window_days: int = 5
    zero_level_tolerance_cm: float = 0.5
    zero_level_drift_tolerance_cm: float = 0.5
    snow_threshold_cm: float = 5.0
    spike_window_days: int = 9       # 3 (árido), 9 (mediterráneo), 6 (húmedo)
    spike_k_factor: float = 4.0      # 4 (árido/mediterráneo), 6 (húmedo)
    spike_absolute_threshold_cm: float = 100.0  # 75/100/140 por zona
    physical_min_cm: float = 2.0
    physical_max_cm: float = 360.0


def apply_zero_level_correction(
    series: pd.Series,
    params: QCParameters
) -> pd.Series:
    """Corrige deriva del nivel de referencia durante periodos sin nieve."""
    # Implementar siguiendo Step 2.1 del paper
    pass


def apply_mad_spike_removal(
    series: pd.Series,
    params: QCParameters
) -> pd.Series:
    """
    Elimina spikes usando MAD (Median Absolute Deviation).

    MAD_t = median_ω(|SD_i - median(SD_t)|)

    Criterios para flagear como spike:
    1. |SD - median| > k * MAD AND días adyacentes consistentes entre sí
    2. |SD - SD_vecino| > umbral_absoluto en ambos vecinos
    """
    # Implementar siguiendo Step 2.2 del paper (Ecuación 1)
    pass


def apply_physical_range_check(
    series: pd.Series,
    params: QCParameters
) -> pd.Series:
    """Filtra valores fuera del rango físico plausible."""
    # Implementar siguiendo Step 2.3 del paper
    pass


def compute_pci(
    sd_series: pd.Series,
    pr_series: pd.Series,
    at_series: pd.Series,
    tau_cm: float = 1.0,
    at_rain_percentile: float = 0.95
) -> dict:
    """
    Calcula Physical Consistency Index (PCI) según Caro et al. 2026 Eq. 2.

    Para AndesAI, esta función se usa en validación retrospectiva del
    subagente S5: verifica que los eventos de acumulación pronosticados
    sean consistentes con Pr > 1mm y AT < umbral.
    """
    # Implementar siguiendo Step 4 del paper
    pass


def compute_pci_for_forecast(
    forecast_sd: pd.Series,
    forecast_pr: pd.Series,
    forecast_at: pd.Series,
    params: QCParameters
) -> float:
    """
    Extensión propia: PCI aplicado a PRONÓSTICOS, no observaciones.

    Útil para que el subagente S5 valide internamente la consistencia
    física de un boletín antes de emitirlo. Si el PCI del pronóstico
    es bajo (<0.7), se flaggea el boletín para revisión.
    """
    pass
```

#### 3.3.3 Tests unitarios

Crear `tests/qc/test_snow_depth_qc.py`:

- Test de MAD spike removal con serie sintética que incluye spike conocido
- Test de zero-level correction con serie con drift simulado
- Test de physical range con valores fuera de rango
- Test de PCI con casos físicos consistentes e inconsistentes
- Test de regresión: aplicar QC a un subset del dataset Caro y comparar
  output con el dataset clean publicado

Objetivo: mantener cobertura >85% y agregar a los 135 tests actuales que
pasan en CI.

#### 3.3.4 Integración con `ConsultorBigQuery`

Modificar `src/data_access/consultor_bigquery.py` para que:

- Cuando consulte datos crudos de DGA, ofrezca opción `apply_qc=True`
- Aplique el módulo `snow_depth_qc` antes de devolver al subagente
- Registre métricas (% removido, n° spikes detectados) en logs estructurados

#### 3.3.5 Documentación técnica

Crear `docs/qc/snow_depth_qc.md` con:
- Justificación metodológica (cita a Caro et al. 2026)
- Parámetros por zona y estación
- Ejemplos de uso
- Diferencias respecto al paper original
- Cómo recalibrar parámetros con nuevas estaciones

---

## 4. Criterios de Aceptación

### Tarea 1 (Ground Truth)
- [ ] Tabla `clima.snow_depth_caro_2026` creada con esquema documentado
- [ ] Al menos 21 estaciones del Maipo cargadas con qc_status='clean'
- [ ] 7 estaciones de Elqui cargadas para análisis comparativo
- [ ] Documentación `docs/datasets/caro_2026.md` completa
- [ ] Query de validación retorna >50,000 observaciones limpias
- [ ] No hay duplicados (test PRIMARY KEY lógico station_id + date + qc_status)
- [ ] `log_claude.md` actualizado

### Tarea 2 (Hallazgo en Tesis)
- [ ] Notebook `sd_elevation_analysis.ipynb` reproduce Figuras 5 y 6 del paper
- [ ] Sección de marco teórico redactada (~1.5 pág, IEEE 12pt Arial)
- [ ] Párrafo de conclusiones integrado con cuantificación de mejora
- [ ] Referencia IEEE [XX] insertada y numeración actualizada
- [ ] Figuras exportadas a `tesis/figuras/sd_elevation_*.png` (300 DPI)
- [ ] Citas al paper en al menos 3 puntos de la tesis (marco, metodología,
      conclusiones)

### Tarea 3 (QC Module)
- [ ] Módulo `src/qc/snow_depth_qc.py` implementado y documentado
- [ ] Tests unitarios pasando (>85% cobertura)
- [ ] Test de regresión contra dataset Caro: discrepancia <5% en serie clean
- [ ] Integración con `ConsultorBigQuery` funcional
- [ ] PCI extendido para pronósticos implementado
- [ ] Documentación `docs/qc/snow_depth_qc.md` completa
- [ ] Métricas exportadas a Cloud Monitoring

---

## 5. Dependencias

- **GCP**: BigQuery (`climas-chileno.clima`), Cloud Storage para datos crudos
- **Python**: pandas 2.3+, google-cloud-bigquery, numpy, scipy
- **Dataset externo**: Zenodo 10.5281/zenodo.20089265 (acceso libre CC BY 4.0)
- **Skill**: `snow-alert-dev` (flujos F3, F4, F6)
- **Skill**: `eaws-methodology` (para validar coherencia con marco EAWS)

---

## 6. Consideraciones Adicionales

### Citación obligatoria
Todo uso del dataset y del código requiere citar:
> Medina, J., and Caro, A.: The Southern Andes Daily Snow Depth Dataset
> (2010–2024): quality-controlled dataset from Chile and Argentina, Zenodo
> [data set], doi:10.5281/zenodo.20089265, 2026.

### Licencia
CC BY 4.0 — permite uso comercial y derivados con atribución.

### Posible contacto con autores
Una vez completadas las tres tareas y validado el sistema, evaluar contacto
con Alexis Caro (UdeC) y/o Freddy Saavedra (UPLA) para:
- Presentar AndesAI como caso de uso aplicado del dataset
- Solicitar feedback técnico sobre integración EAWS
- Explorar potencial colaboración para validación operacional

### Validación cruzada futura
Considerar uso del dataset para backtesting del sistema completo: tomar
días específicos del periodo 2020–2024 con datos clean en Maipo, generar
boletines AndesAI retrospectivos, comparar con SD observada y con
boletines históricos de Snowlab La Parva si están disponibles.

---

## 7. Notas para Claude Code

- Antes de cualquier modificación a BigQuery, ejecutar `bq show` para
  confirmar estado actual del dataset `clima`
- Si el formato del dataset Zenodo no es CSV directo (puede ser NetCDF o
  HDF5), adaptar el pipeline de ingesta usando `xarray` o `h5py`
- Mantener consistencia con el estilo del repo: docstrings en español
  para lógica de dominio, inglés para utilidades genéricas
- Después de cada subtarea completada, hacer commit con mensaje descriptivo
  referenciando este requerimiento (REQ-2026-XX)
- Si surgen ambigüedades sobre qué estaciones priorizar más allá de las
  21 del Maipo, consultar antes de cargar el dataset completo
- Los parámetros de QC del paper son específicos por zona; replicarlos
  exactamente como están en Tabla 1 y Sección 2.2 del paper

---

## 8. Referencias

- Caro, A. et al. (2026). The Southern Andes Daily Snow Depth Dataset
  (2010–2024). *Earth System Science Data Discussions*, in review.
  doi:10.5194/essd-2026-324
- Medina, J. & Caro, A. (2026). Dataset on Zenodo.
  doi:10.5281/zenodo.20089265
- Repositorio de QC: github.com/javiermedinamen-art/hidromet
- Ayala, Á. et al. (2017). Sublimation on Juncal Norte Glacier.
  *Journal of Glaciology*, 63(241), 803–822.
- Rousseeuw, P. J. & Croux, C. (1993). Alternatives to MAD.
  *Journal of the American Statistical Association*, 88(424), 1273–1283.
