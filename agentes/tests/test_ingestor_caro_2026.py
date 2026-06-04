"""
Tests para datos/ingestores/ingestor_caro_2026.py

Dataset real: Southern_Andes_Snow_Depth_Dataset_v4.2.csv (formato wide) +
              stations_data.csv (metadata). Filtrado por basin, no por nombres.

No requiere GCP — BQ mockeado con MagicMock.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datos.ingestores.ingestor_caro_2026 import (
    BASIN_ELQUI,
    BASIN_MAIPO,
    FILTROS_ZONA,
    PAPER_REFERENCE,
    _construir_filas_bq,
    _inferir_andean_zone,
    _inferir_country,
    cargar_dataset_caro,
)

FIXTURES = Path(__file__).parent / "fixtures" / "caro_2026"
DATOS_REALES = Path(__file__).parent.parent.parent / "data" / "external" / "caro_2026"
TIENE_DATOS_REALES = (DATOS_REALES / "stations_data.csv").exists() and (
    DATOS_REALES / "Southern_Andes_Snow_Depth_Dataset_v4.2.csv"
).exists()


# ── Tests constantes y zonas ──────────────────────────────────────────────────

class TestConstantes:

    def test_filtros_zona_tiene_claves(self):
        assert "maipo" in FILTROS_ZONA
        assert "elqui" in FILTROS_ZONA
        assert "all" in FILTROS_ZONA
        assert FILTROS_ZONA["all"] is None

    def test_basin_maipo_correcto(self):
        assert BASIN_MAIPO == "Río Maipo"

    def test_basin_elqui_correcto(self):
        assert BASIN_ELQUI == "Río Elqui"

    def test_paper_reference_contiene_doi(self):
        assert "zenodo.20089265" in PAPER_REFERENCE


# ── Tests funciones de inferencia ─────────────────────────────────────────────

class TestInferencias:

    def test_andean_zone_arida(self):
        assert _inferir_andean_zone(-25.0) == "Arid"

    def test_andean_zone_mediterranea(self):
        assert _inferir_andean_zone(-33.35) == "Mediterranean"  # La Parva

    def test_andean_zone_humeda(self):
        assert _inferir_andean_zone(-40.0) == "Wet"

    def test_andean_zone_limite_mediterranea(self):
        assert _inferir_andean_zone(-27.0) == "Mediterranean"

    def test_country_ianigla_es_argentina(self):
        assert _inferir_country("IANIGLA") == "AR"

    def test_country_dga_es_chile(self):
        assert _inferir_country("DGA") == "CL"

    def test_country_ceaza_es_chile(self):
        assert _inferir_country("CEAZA") == "CL"

    def test_country_ciep_es_chile(self):
        assert _inferir_country("CIEP") == "CL"


# ── Tests construir_filas_bq ──────────────────────────────────────────────────

class TestConstruirFilasBQ:

    def _df_minimal(self) -> pd.DataFrame:
        return pd.DataFrame({
            "station_id": ["5721019"],
            "station_name": ["La Parva"],
            "basin": [BASIN_MAIPO],
            "andean_zone": ["Mediterranean"],
            "country": ["CL"],
            "lat": [-33.3306],
            "lon": [-70.2972],
            "elevation_m": [2703.0],
            "observation_date": [pd.Timestamp("2020-06-15")],
            "snow_depth_cm": [85.5],
            "data_source": ["DGA"],
            "qc_status": ["clean"],
        })

    def test_estructura_correcta(self):
        filas = _construir_filas_bq(self._df_minimal())
        assert len(filas) == 1
        fila = filas[0]
        assert fila["station_id"] == "5721019"
        assert fila["station_name"] == "La Parva"
        assert fila["qc_status"] == "clean"
        assert fila["paper_reference"] == PAPER_REFERENCE

    def test_snow_depth_null_se_maneja(self):
        import numpy as np
        df = self._df_minimal().copy()
        df["snow_depth_cm"] = [float("nan")]
        filas = _construir_filas_bq(df)
        assert filas[0]["snow_depth_cm"] is None

    def test_fecha_formateada_como_string(self):
        filas = _construir_filas_bq(self._df_minimal())
        assert filas[0]["observation_date"] == "2020-06-15"

    def test_campos_requeridos_presentes(self):
        filas = _construir_filas_bq(self._df_minimal())
        campos = [
            "station_id", "station_name", "basin", "andean_zone", "country",
            "latitude", "longitude", "elevation_m", "observation_date",
            "qc_status", "data_source", "ingestion_timestamp", "paper_reference",
        ]
        for campo in campos:
            assert campo in filas[0], f"Campo faltante: {campo}"


# ── Tests dry_run con datos reales ────────────────────────────────────────────

class TestDryRunConDatosReales:

    @pytest.mark.skipif(not TIENE_DATOS_REALES, reason="Datos Zenodo no descargados localmente")
    def test_dry_run_maipo_retorna_13_estaciones(self):
        resultado = cargar_dataset_caro(bq=None, zona="maipo", dry_run=True)
        assert resultado["dry_run"] is True
        assert resultado["n_estaciones"] == 13
        assert resultado["filas_procesadas"] > 50_000

    @pytest.mark.skipif(not TIENE_DATOS_REALES, reason="Datos Zenodo no descargados localmente")
    def test_dry_run_elqui_retorna_7_estaciones(self):
        resultado = cargar_dataset_caro(bq=None, zona="elqui", dry_run=True)
        assert resultado["dry_run"] is True
        assert resultado["n_estaciones"] == 7

    @pytest.mark.skipif(not TIENE_DATOS_REALES, reason="Datos Zenodo no descargados localmente")
    def test_dry_run_maipo_contiene_la_parva(self):
        resultado = cargar_dataset_caro(bq=None, zona="maipo", dry_run=True)
        assert "5721019" in resultado["estaciones"]  # code_internal de La Parva

    @pytest.mark.skipif(not TIENE_DATOS_REALES, reason="Datos Zenodo no descargados localmente")
    def test_dry_run_maipo_tiene_filas_con_dato(self):
        resultado = cargar_dataset_caro(bq=None, zona="maipo", dry_run=True)
        assert resultado["filas_con_dato"] > 20_000


# ── Tests transformación con datos mock ───────────────────────────────────────

class TestTransformacionMock:

    def _mock_stations(self) -> pd.DataFrame:
        return pd.DataFrame({
            "code_internal": ["5721019", "5720005"],
            "name": ["La Parva", "Farellones"],
            "lat": [-33.33, -33.35],
            "lon": [-70.30, -70.31],
            "elevation": [2703.0, 2452.0],
            "basin": [BASIN_MAIPO, BASIN_MAIPO],
            "source": ["DGA", "DGA"],
        })

    def _mock_wide_csv(self) -> pd.DataFrame:
        return pd.DataFrame({
            "date": pd.date_range("2020-06-01", periods=5, freq="D"),
            "5721019": [50.0, 55.0, None, 60.0, 58.0],
            "5720005": [40.0, None, 42.0, 45.0, 43.0],
        })

    @patch("datos.ingestores.ingestor_caro_2026._descargar_si_no_existe")
    @patch("pandas.read_csv")
    def test_melt_produce_formato_long(self, mock_read_csv, mock_descarga):
        import io
        mock_descarga.return_value = Path("/tmp/fake.csv")
        mock_read_csv.side_effect = [self._mock_stations(), self._mock_wide_csv()]

        from datos.ingestores.ingestor_caro_2026 import _cargar_y_transformar
        df = _cargar_y_transformar("maipo")

        assert "observation_date" in df.columns
        assert "snow_depth_cm" in df.columns
        assert "station_name" in df.columns
        assert "andean_zone" in df.columns
        assert "country" in df.columns
        assert len(df) == 10  # 5 fechas × 2 estaciones


# ── Test no-escritura en dry_run ──────────────────────────────────────────────

class TestDryRunSinBQ:

    @pytest.mark.skipif(not TIENE_DATOS_REALES, reason="Datos Zenodo no descargados localmente")
    def test_dry_run_no_usa_cliente_bq(self):
        """bq=None no debe producir AttributeError en dry_run."""
        resultado = cargar_dataset_caro(bq=None, zona="maipo", dry_run=True)
        assert resultado.get("dry_run") is True
