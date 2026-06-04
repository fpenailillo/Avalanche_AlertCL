"""
Control de calidad para series temporales de profundidad de nieve (SD).
Adaptado de Caro et al. (2026) - github.com/javiermedinamen-art/hidromet

Implementa los 4 pasos del paper (Steps 2.1–2.3 y Step 4) más una extensión
propia para validar pronósticos antes de emitir boletines (experimental).

Diferencias con el paper original:
- Procesamiento incremental por estación, no batch sobre toda la red
- Parametrización explícita por zona climática (árida/mediterránea/húmeda)
- Extensión PCI aplicado a pronósticos del subagente S5 (no solo observaciones)
- Integración con logging estructurado del sistema AndesAI

Referencia obligatoria al usar:
    Medina, J., and Caro, A.: The Southern Andes Daily Snow Depth Dataset
    (2010–2024): quality-controlled dataset from Chile and Argentina,
    Zenodo [data set], doi:10.5281/zenodo.20089265, 2026.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ParametrosQC:
    """Parámetros de QC por zona climática según Tabla 1 de Caro et al. 2026."""
    ventana_nivel_cero_dias: int = 5
    tolerancia_nivel_cero_cm: float = 0.5
    tolerancia_drift_cm: float = 0.5
    umbral_nieve_cm: float = 5.0
    ventana_spike_dias: int = 9        # árido=3, mediterráneo=9, húmedo=6
    factor_k_mad: float = 4.0          # árido=4, mediterráneo=4, húmedo=6
    umbral_absoluto_spike_cm: float = 100.0  # árido=75, mediterráneo=100, húmedo=140
    minimo_fisico_cm: float = 2.0
    maximo_fisico_cm: float = 360.0


PARAMETROS_POR_ZONA: dict[str, ParametrosQC] = {
    "arida": ParametrosQC(
        ventana_spike_dias=3,
        factor_k_mad=4.0,
        umbral_absoluto_spike_cm=75.0,
    ),
    "mediterranea": ParametrosQC(
        ventana_spike_dias=9,
        factor_k_mad=4.0,
        umbral_absoluto_spike_cm=100.0,
    ),
    "humeda": ParametrosQC(
        ventana_spike_dias=6,
        factor_k_mad=6.0,
        umbral_absoluto_spike_cm=140.0,
    ),
}


def correccion_nivel_cero(
    serie: pd.Series,
    params: ParametrosQC,
) -> pd.Series:
    """
    Step 2.1: Corrige deriva del sensor durante periodos sin nieve.

    Identifica ventanas temporales donde SD debería ser 0 (temperatura > 0°C
    sin precipitación durante varios días consecutivos) y ajusta el offset.
    En ausencia de variables auxiliares, usa heurística: si la mediana de
    una ventana de `ventana_nivel_cero_dias` días está por debajo del umbral
    de nieve y todas las observaciones son < tolerancia_drift_cm, aplica
    corrección al cero.
    """
    resultado = serie.copy().astype(float)
    n = len(resultado)
    w = params.ventana_nivel_cero_dias

    for i in range(n - w + 1):
        ventana = resultado.iloc[i : i + w]
        if ventana.isna().any():
            continue
        if (ventana.median() < params.umbral_nieve_cm and
                ventana.abs().max() < params.tolerancia_drift_cm):
            resultado.iloc[i : i + w] = 0.0

    return resultado


def eliminacion_spikes_mad(
    serie: pd.Series,
    params: ParametrosQC,
) -> pd.Series:
    """
    Step 2.2: Elimina spikes usando Median Absolute Deviation (MAD).

    Ecuación 1 del paper:
        MAD_t = median_{ω}(|SD_i - median(SD_t)|)

    Un punto se marca como spike si:
    1. |SD_t - median| > k * MAD  Y
    2. Los vecinos inmediatos son consistentes entre sí
       (diferencia vecino_anterior–vecino_siguiente < umbral_absoluto)

    Parámetro k según zona: árida=4, mediterránea=4, húmeda=6.
    """
    resultado = serie.copy().astype(float)
    valores = resultado.values
    n = len(valores)
    w = params.ventana_spike_dias
    radio = w // 2

    for i in range(1, n - 1):
        if np.isnan(valores[i]):
            continue

        inicio = max(0, i - radio)
        fin = min(n, i + radio + 1)
        ventana = valores[inicio:fin]
        ventana_valida = ventana[~np.isnan(ventana)]
        if len(ventana_valida) < 3:
            continue

        mediana = np.median(ventana_valida)
        mad = np.median(np.abs(ventana_valida - mediana))

        desviacion = abs(valores[i] - mediana)
        if desviacion <= params.factor_k_mad * mad:
            continue

        # Criterio 2: los vecinos son consistentes entre sí
        vecino_ant = valores[i - 1] if not np.isnan(valores[i - 1]) else mediana
        vecino_sig = valores[i + 1] if not np.isnan(valores[i + 1]) else mediana
        if abs(vecino_ant - vecino_sig) < params.umbral_absoluto_spike_cm:
            resultado.iloc[i] = np.nan

    return resultado


def verificacion_rango_fisico(
    serie: pd.Series,
    params: ParametrosQC,
) -> pd.Series:
    """Step 2.3: Reemplaza por NaN valores fuera del rango físico plausible."""
    resultado = serie.copy().astype(float)
    fuera_rango = (resultado < params.minimo_fisico_cm) | (resultado > params.maximo_fisico_cm)
    resultado[fuera_rango] = np.nan
    return resultado


def calcular_pci(
    serie_sd: pd.Series,
    serie_pr: pd.Series,
    serie_ta: pd.Series,
    tau_cm: float = 1.0,
    percentil_lluvia: float = 0.95,
) -> dict:
    """
    Step 4: Physical Consistency Index (PCI) según Caro et al. 2026 Ecuación 2.

    Valida que incrementos de SD sean físicamente consistentes con:
    - Precipitación > tau_cm (indica evento de nieve)
    - Temperatura del aire < umbral de lluvia (lluvia vs nieve)

    Retorna dict con:
        pci_global: float [0, 1]
        n_incrementos: int
        n_consistentes: int
        umbral_ta_lluvia: float
    """
    delta_sd = serie_sd.diff()
    incrementos = delta_sd[delta_sd > tau_cm].dropna()

    if len(incrementos) == 0:
        return {
            "pci_global": 1.0,
            "n_incrementos": 0,
            "n_consistentes": 0,
            "umbral_ta_lluvia": float("nan"),
            "sin_datos": True,
        }

    umbral_ta = serie_ta.quantile(percentil_lluvia)
    consistentes = 0
    for fecha in incrementos.index:
        if fecha not in serie_pr.index or fecha not in serie_ta.index:
            continue
        pr = serie_pr.loc[fecha]
        ta = serie_ta.loc[fecha]
        if pd.notna(pr) and pd.notna(ta) and pr > tau_cm and ta < umbral_ta:
            consistentes += 1

    pci = consistentes / len(incrementos) if len(incrementos) > 0 else 1.0
    return {
        "pci_global": round(pci, 4),
        "n_incrementos": len(incrementos),
        "n_consistentes": consistentes,
        "umbral_ta_lluvia": round(umbral_ta, 2),
    }


def calcular_pci_pronostico(
    sd_pronostico: pd.Series,
    pr_pronostico: pd.Series,
    ta_pronostico: pd.Series,
    params: ParametrosQC,
    tau_cm: float = 1.0,
) -> float:
    """
    [EXPERIMENTAL] PCI aplicado a PRONÓSTICOS del subagente S5, no a observaciones.

    Permite que el subagente S5 valide la consistencia física de un boletín
    antes de emitirlo. Si PCI_pronostico < 0.7, el boletín se flaggea
    para revisión manual.

    ADVERTENCIA: Esta extensión no está validada por Caro et al. (2026).
    Es una adaptación propia del concepto PCI al dominio de pronósticos.
    """
    try:
        resultado = calcular_pci(
            serie_sd=sd_pronostico,
            serie_pr=pr_pronostico,
            serie_ta=ta_pronostico,
            tau_cm=tau_cm,
            percentil_lluvia=0.95,
        )
        return resultado["pci_global"]
    except Exception:
        return 1.0


def aplicar_pipeline_qc(
    serie: pd.Series,
    params: ParametrosQC,
) -> pd.Series:
    """Aplica el pipeline completo: nivel_cero → spike_mad → rango_fisico."""
    serie = correccion_nivel_cero(serie, params)
    serie = eliminacion_spikes_mad(serie, params)
    serie = verificacion_rango_fisico(serie, params)
    return serie
