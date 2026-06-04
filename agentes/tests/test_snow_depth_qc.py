"""
Tests para datos/qc/snow_depth_qc.py

Cubre: correccion_nivel_cero, eliminacion_spikes_mad, verificacion_rango_fisico,
calcular_pci, calcular_pci_pronostico, aplicar_pipeline_qc.

No requiere GCP ni credenciales — todos los tests usan datos sintéticos o fixtures locales.
"""

import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datos.qc.snow_depth_qc import (
    PARAMETROS_POR_ZONA,
    ParametrosQC,
    aplicar_pipeline_qc,
    calcular_pci,
    calcular_pci_pronostico,
    correccion_nivel_cero,
    eliminacion_spikes_mad,
    verificacion_rango_fisico,
)

FIXTURES = Path(__file__).parent / "fixtures" / "caro_2026"


# ── Fixtures base ──────────────────────────────────────────────────────────────

def _serie_estacional(n: int = 30, base_cm: float = 50.0) -> pd.Series:
    """Serie estacional estable sin outliers."""
    indice = pd.date_range("2020-06-01", periods=n, freq="D")
    valores = base_cm + np.random.default_rng(42).normal(0, 2, n)
    valores = np.clip(valores, 5, 300)
    return pd.Series(valores, index=indice)


def _serie_verano_sin_nieve(n: int = 10, offset_cm: float = 0.4) -> pd.Series:
    """Serie de verano donde SD debería ser 0 pero hay un pequeño offset (drift sensor)."""
    indice = pd.date_range("2020-01-10", periods=n, freq="D")
    valores = [offset_cm] * n
    return pd.Series(valores, index=indice)


# ── Tests correccion_nivel_cero ────────────────────────────────────────────────

class TestCorreccionNivelCero:

    def test_drift_menor_tolerancia_se_corrige(self):
        params = ParametrosQC(
            ventana_nivel_cero_dias=5,
            tolerancia_drift_cm=0.5,
            umbral_nieve_cm=5.0,
        )
        serie = _serie_verano_sin_nieve(n=10, offset_cm=0.3)
        resultado = correccion_nivel_cero(serie, params)
        assert (resultado == 0.0).all()

    def test_nieve_real_no_se_corrige(self):
        params = ParametrosQC(umbral_nieve_cm=5.0)
        indice = pd.date_range("2020-06-01", periods=5, freq="D")
        serie = pd.Series([40.0, 42.0, 43.0, 44.0, 45.0], index=indice)
        resultado = correccion_nivel_cero(serie, params)
        assert all(resultado > 0)

    def test_resultado_misma_longitud(self):
        params = ParametrosQC()
        serie = _serie_estacional(20)
        resultado = correccion_nivel_cero(serie, params)
        assert len(resultado) == len(serie)

    def test_nans_no_causan_error(self):
        params = ParametrosQC()
        indice = pd.date_range("2020-06-01", periods=5, freq="D")
        serie = pd.Series([np.nan, 0.3, 0.2, np.nan, 0.1], index=indice)
        resultado = correccion_nivel_cero(serie, params)
        assert len(resultado) == 5


# ── Tests eliminacion_spikes_mad ───────────────────────────────────────────────

class TestEliminacionSpikesMad:

    def test_spike_aislado_eliminado(self):
        params = ParametrosQC(
            ventana_spike_dias=9,
            factor_k_mad=4.0,
            umbral_absoluto_spike_cm=100.0,
        )
        n = 20
        indice = pd.date_range("2020-06-01", periods=n, freq="D")
        valores = [50.0] * n
        valores[10] = 350.0  # spike evidente
        serie = pd.Series(valores, index=indice)
        resultado = eliminacion_spikes_mad(serie, params)
        assert math.isnan(resultado.iloc[10])
        assert not math.isnan(resultado.iloc[9])
        assert not math.isnan(resultado.iloc[11])

    def test_serie_estable_no_elimina_nada(self):
        """Una serie estable sin outliers no debe perder ningún punto."""
        params = ParametrosQC(
            ventana_spike_dias=9,
            factor_k_mad=4.0,
            umbral_absoluto_spike_cm=100.0,
        )
        n = 20
        indice = pd.date_range("2020-06-01", periods=n, freq="D")
        # Serie de acumulación gradual y suave (ningún punto es outlier)
        valores = [50.0 + i * 0.5 for i in range(n)]
        serie = pd.Series(valores, index=indice)
        resultado = eliminacion_spikes_mad(serie, params)
        # Los extremos se excluyen del análisis; los internos deben preservarse
        assert resultado.iloc[2:-2].notna().all()

    def test_serie_sin_spikes_no_cambia(self):
        params = ParametrosQC()
        serie = _serie_estacional(20, base_cm=50.0)
        resultado = eliminacion_spikes_mad(serie, params)
        n_nans = resultado.isna().sum()
        assert n_nans <= 2  # tolerancia mínima por borde

    def test_resultado_misma_longitud(self):
        params = ParametrosQC()
        serie = _serie_estacional(30)
        resultado = eliminacion_spikes_mad(serie, params)
        assert len(resultado) == len(serie)


# ── Tests verificacion_rango_fisico ───────────────────────────────────────────

class TestVerificacionRangoFisico:

    def test_valor_negativo_se_elimina(self):
        params = ParametrosQC(minimo_fisico_cm=2.0, maximo_fisico_cm=360.0)
        indice = pd.date_range("2020-06-01", periods=3, freq="D")
        serie = pd.Series([-5.0, 50.0, 100.0], index=indice)
        resultado = verificacion_rango_fisico(serie, params)
        assert math.isnan(resultado.iloc[0])

    def test_valor_extremo_se_elimina(self):
        params = ParametrosQC(minimo_fisico_cm=2.0, maximo_fisico_cm=360.0)
        indice = pd.date_range("2020-06-01", periods=3, freq="D")
        serie = pd.Series([50.0, 500.0, 100.0], index=indice)
        resultado = verificacion_rango_fisico(serie, params)
        assert math.isnan(resultado.iloc[1])

    def test_valores_validos_no_se_tocan(self):
        params = ParametrosQC(minimo_fisico_cm=2.0, maximo_fisico_cm=360.0)
        indice = pd.date_range("2020-06-01", periods=3, freq="D")
        serie = pd.Series([10.0, 150.0, 300.0], index=indice)
        resultado = verificacion_rango_fisico(serie, params)
        assert resultado.isna().sum() == 0


# ── Tests calcular_pci ────────────────────────────────────────────────────────

class TestCalcularPCI:

    def _series_consistentes(self, n: int = 20):
        """SD sube con precipitación; temperatura incluye días cálidos para definir umbral lluvia."""
        rng = np.random.default_rng(0)
        indice = pd.date_range("2020-07-01", periods=n, freq="D")
        sd = pd.Series([50.0 + i * 5 for i in range(n)], index=indice)
        pr = pd.Series([10.0] * n, index=indice)  # precipitación siempre > tau
        # Temperatura: 18 días fríos (-5°C) + 2 días cálidos (+15°C)
        # → percentil 0.95 será ~+15°C, condición ta < umbral se cumple para días fríos
        ta_vals = [-5.0] * (n - 2) + [15.0, 15.0]
        ta = pd.Series(ta_vals, index=indice)
        return sd, pr, ta

    def _series_inconsistentes(self, n: int = 20):
        """SD sube sin precipitación y temperatura positiva."""
        indice = pd.date_range("2020-07-01", periods=n, freq="D")
        sd = pd.Series([50.0 + i * 5 for i in range(n)], index=indice)
        pr = pd.Series([0.0] * n, index=indice)   # sin lluvia
        ta = pd.Series([15.0] * n, index=indice)  # temperatura positiva
        return sd, pr, ta

    def test_caso_consistente_pci_alto(self):
        sd, pr, ta = self._series_consistentes()
        resultado = calcular_pci(sd, pr, ta, tau_cm=1.0)
        assert resultado["pci_global"] >= 0.8, f"PCI esperado ≥0.8, obtenido {resultado['pci_global']}"

    def test_caso_inconsistente_pci_bajo(self):
        sd, pr, ta = self._series_inconsistentes()
        resultado = calcular_pci(sd, pr, ta, tau_cm=1.0)
        assert resultado["pci_global"] <= 0.3, f"PCI esperado ≤0.3, obtenido {resultado['pci_global']}"

    def test_sin_incrementos_retorna_pci_1(self):
        indice = pd.date_range("2020-07-01", periods=10, freq="D")
        sd = pd.Series([50.0] * 10, index=indice)
        pr = pd.Series([0.0] * 10, index=indice)
        ta = pd.Series([5.0] * 10, index=indice)
        resultado = calcular_pci(sd, pr, ta, tau_cm=1.0)
        assert resultado["pci_global"] == 1.0
        assert resultado["sin_datos"] is True

    def test_estructura_retorno(self):
        sd, pr, ta = self._series_consistentes()
        resultado = calcular_pci(sd, pr, ta)
        assert "pci_global" in resultado
        assert "n_incrementos" in resultado
        assert "n_consistentes" in resultado
        assert 0.0 <= resultado["pci_global"] <= 1.0


# ── Tests calcular_pci_pronostico ─────────────────────────────────────────────

class TestCalcularPciPronostico:

    def test_retorna_float(self):
        indice = pd.date_range("2020-07-01", periods=5, freq="D")
        sd = pd.Series([50, 60, 70, 80, 90], index=indice, dtype=float)
        pr = pd.Series([5, 5, 5, 5, 5], index=indice, dtype=float)
        ta = pd.Series([-3, -4, -2, -5, -3], index=indice, dtype=float)
        params = ParametrosQC()
        resultado = calcular_pci_pronostico(sd, pr, ta, params)
        assert isinstance(resultado, float)
        assert 0.0 <= resultado <= 1.0

    def test_pronostico_vacio_no_lanza_excepcion(self):
        indice = pd.date_range("2020-07-01", periods=3, freq="D")
        sd = pd.Series([50.0, 50.0, 50.0], index=indice)
        pr = pd.Series([0.0, 0.0, 0.0], index=indice)
        ta = pd.Series([10.0, 10.0, 10.0], index=indice)
        resultado = calcular_pci_pronostico(sd, pr, ta, ParametrosQC())
        assert isinstance(resultado, float)


# ── Tests parametros por zona ─────────────────────────────────────────────────

class TestParametrosPorZona:

    def test_zonas_disponibles(self):
        assert "arida" in PARAMETROS_POR_ZONA
        assert "mediterranea" in PARAMETROS_POR_ZONA
        assert "humeda" in PARAMETROS_POR_ZONA

    def test_zona_arida_ventana_correcta(self):
        assert PARAMETROS_POR_ZONA["arida"].ventana_spike_dias == 3
        assert PARAMETROS_POR_ZONA["arida"].factor_k_mad == 4.0
        assert PARAMETROS_POR_ZONA["arida"].umbral_absoluto_spike_cm == 75.0

    def test_zona_mediterranea_ventana_correcta(self):
        assert PARAMETROS_POR_ZONA["mediterranea"].ventana_spike_dias == 9
        assert PARAMETROS_POR_ZONA["mediterranea"].factor_k_mad == 4.0

    def test_zona_humeda_ventana_correcta(self):
        assert PARAMETROS_POR_ZONA["humeda"].ventana_spike_dias == 6
        assert PARAMETROS_POR_ZONA["humeda"].factor_k_mad == 6.0
        assert PARAMETROS_POR_ZONA["humeda"].umbral_absoluto_spike_cm == 140.0


# ── Test aplicar_pipeline_qc ──────────────────────────────────────────────────

class TestAplicarPipelineQC:

    def test_pipeline_completo_retorna_serie(self):
        params = ParametrosQC()
        serie = _serie_estacional(20)
        resultado = aplicar_pipeline_qc(serie, params)
        assert isinstance(resultado, pd.Series)
        assert len(resultado) == len(serie)

    def test_pipeline_elimina_spike_evidente(self):
        params = PARAMETROS_POR_ZONA["mediterranea"]
        n = 25
        indice = pd.date_range("2020-06-01", periods=n, freq="D")
        valores = [50.0] * n
        valores[12] = 450.0  # fuera de rango físico (>360)
        serie = pd.Series(valores, index=indice)
        resultado = aplicar_pipeline_qc(serie, params)
        assert math.isnan(resultado.iloc[12])


# ── Test de regresión contra fixtures Caro 2026 ───────────────────────────────

class TestRegresionCaro2026:

    @pytest.mark.skipif(
        not (FIXTURES / "raw_sample.csv").exists(),
        reason="Fixtures de Caro 2026 no disponibles",
    )
    def test_pipeline_qc_vs_clean_sample(self):
        """
        Aplica el pipeline QC al subset raw y compara contra clean.
        Criterios: MAE ≤ 2 cm, diferencia en conteo NaN ≤ 5%.
        """
        df_raw = pd.read_csv(FIXTURES / "raw_sample.csv", parse_dates=["observation_date"])
        df_clean = pd.read_csv(FIXTURES / "clean_sample.csv", parse_dates=["observation_date"])
        params = PARAMETROS_POR_ZONA["mediterranea"]

        mae_total = []
        for station_id in df_raw["station_id"].unique():
            raw_estacion = (
                df_raw[df_raw["station_id"] == station_id]
                .set_index("observation_date")["snow_depth_cm"]
                .astype(float)
            )
            clean_estacion = (
                df_clean[df_clean["station_id"] == station_id]
                .set_index("observation_date")["snow_depth_cm"]
                .astype(float)
            )
            resultado_qc = aplicar_pipeline_qc(raw_estacion, params)

            comun = resultado_qc.index.intersection(clean_estacion.index)
            res_comun = resultado_qc.loc[comun]
            clean_comun = clean_estacion.loc[comun]

            ambos_nan = res_comun.isna() & clean_comun.isna()
            ninguno_nan = ~res_comun.isna() & ~clean_comun.isna()

            if ninguno_nan.any():
                mae = (res_comun[ninguno_nan] - clean_comun[ninguno_nan]).abs().mean()
                mae_total.append(mae)

            # % diferencia en NaN no debe superar 5%
            n_nans_qc = res_comun.isna().sum()
            n_nans_clean = clean_comun.isna().sum()
            total = len(comun)
            if total > 0:
                diff_pct = abs(n_nans_qc - n_nans_clean) / total * 100
                assert diff_pct <= 5.0, (
                    f"{station_id}: diferencia en NaN = {diff_pct:.1f}% (máx 5%)"
                )

        if mae_total:
            mae_promedio = sum(mae_total) / len(mae_total)
            assert mae_promedio <= 2.0, f"MAE promedio = {mae_promedio:.2f} cm (máx 2.0 cm)"
