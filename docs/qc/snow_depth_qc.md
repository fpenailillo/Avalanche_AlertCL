# Módulo de QC: snow_depth_qc.py

**Ruta**: `datos/qc/snow_depth_qc.py`
**Basado en**: Caro et al. (2026), github.com/javiermedinamen-art/hidromet

## Justificación metodológica

El dataset de profundidad de nieve (SD) de estaciones in-situ en los Andes presenta
errores instrumentales sistemáticos:

- **Drift del nivel cero**: el sensor reporta valores positivos (0.2–0.5 cm) en
  períodos sin nieve por deriva térmica o humedad.
- **Spikes**: lecturas instantáneas anómalas causadas por obstáculos temporales,
  aves o interferencia electromagnética.
- **Valores físicamente imposibles**: lecturas negativas o superiores al máximo
  plausible según la zona climática.

El paper de referencia (Caro et al. 2026) documenta un pipeline replicable de QC
aplicado a 81 estaciones de los Andes del Sur. Este módulo adapta esa metodología
para uso en AndesAI.

## Parámetros por zona (Tabla 1 del paper)

| Parámetro | Árida | Mediterránea | Húmeda |
|---|---|---|---|
| `ventana_spike_dias` | 3 | 9 | 6 |
| `factor_k_mad` | 4.0 | 4.0 | 6.0 |
| `umbral_absoluto_spike_cm` | 75 | 100 | 140 |
| `ventana_nivel_cero_dias` | 5 | 5 | 5 |
| `tolerancia_drift_cm` | 0.5 | 0.5 | 0.5 |
| `minimo_fisico_cm` | 2.0 | 2.0 | 2.0 |
| `maximo_fisico_cm` | 360 | 360 | 360 |

Zonas disponibles: `PARAMETROS_POR_ZONA["arida" | "mediterranea" | "humeda"]`.
Las estaciones del Maipo (33°S) son zona **mediterránea**.

## Funciones implementadas

### `correccion_nivel_cero(serie, params)` — Step 2.1

Identifica ventanas temporales donde SD debería ser 0 (mediana < umbral_nieve y
todos los valores < tolerancia_drift) y los corrige a 0.

### `eliminacion_spikes_mad(serie, params)` — Step 2.2, Ecuación 1

```
MAD_t = median_ω(|SD_i - median(SD_t)|)
```

Marca un punto como spike si:
1. `|SD_t - mediana| > k * MAD`
2. Los vecinos adyacentes son consistentes entre sí (su diferencia < umbral_absoluto),
   lo que indica que el punto es el único anómalo (no parte de una tormenta).

### `verificacion_rango_fisico(serie, params)` — Step 2.3

Reemplaza por NaN valores fuera de `[minimo_fisico_cm, maximo_fisico_cm]`.

### `calcular_pci(sd, pr, ta, tau_cm, percentil_lluvia)` — Step 4, Ecuación 2

Physical Consistency Index: verifica que incrementos de SD sean físicamente
consistentes con precipitación y temperatura de nieve.
Retorna `pci_global` ∈ [0, 1]. Valores > 0.8 indican alta consistencia.

### `calcular_pci_pronostico(sd, pr, ta, params)` — **[EXPERIMENTAL]**

> **ADVERTENCIA**: Esta función es una extensión propia, no validada por Caro et al. (2026).
> Aplica el concepto de PCI a pronósticos del subagente S5 antes de emitir un boletín.
> Si PCI_pronostico < 0.7, se recomienda revisión manual del boletín.

### `aplicar_pipeline_qc(serie, params)` — Pipeline completo

Aplica los 3 pasos secuencialmente:
`nivel_cero → spike_mad → rango_fisico`.

## Ejemplos de uso

```python
import pandas as pd
from datos.qc.snow_depth_qc import PARAMETROS_POR_ZONA, aplicar_pipeline_qc

# Cargar serie raw de La Parva (zona mediterránea)
serie_raw = pd.Series([45.2, 47.8, 350.0, 49.1, 50.3], dtype=float)
params = PARAMETROS_POR_ZONA["mediterranea"]

# Aplicar pipeline completo
serie_clean = aplicar_pipeline_qc(serie_raw, params)
# serie_clean → [45.2, 47.8, NaN, 49.1, 50.3]
```

Desde `ConsultorBigQuery` con `apply_qc=True`:

```python
resultado = consultor.obtener_snow_depth_caro(
    estacion="La Parva",
    fecha_inicio="2023-06-01",
    fecha_fin="2023-09-30",
    qc_status="raw",
    apply_qc=True,
)
print(resultado["qc_metricas"])
# {"n_spikes_detectados": 3, "pct_removido": 1.25, "zona_parametros": "mediterranea"}
```

## Diferencias respecto al paper original

| Aspecto | Paper Caro 2026 | Este módulo |
|---|---|---|
| Procesamiento | Batch sobre toda la red | Por estación (incremental) |
| Parametrización | Por cuenca | Por zona climática (más granular) |
| PCI | Solo observaciones históricas | + Extensión a pronósticos (experimental) |
| Integración | Script standalone | Módulo Python + hook en ConsultorBigQuery |
| Observabilidad | N/A | Métricas en logs estructurados AndesAI |

## Cómo recalibrar parámetros con nuevas estaciones

1. Consultar la Tabla 1 del paper para la zona climática de la estación.
2. Instanciar `ParametrosQC` con los valores correspondientes:
   ```python
   from datos.qc.snow_depth_qc import ParametrosQC
   params_custom = ParametrosQC(ventana_spike_dias=6, factor_k_mad=5.0)
   ```
3. Validar contra datos clean conocidos usando `test_regresion_caro_subset` como referencia.

## Tests

```bash
python3 -m pytest agentes/tests/test_snow_depth_qc.py -v
```

Cobertura objetivo: ≥ 85% (criterio REQ-2026-09 §4 Tarea 3).
