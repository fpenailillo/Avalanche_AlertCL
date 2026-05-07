"""
Tests para FIX-S1-SEMANTICA (v7.0): distinción riesgo potencial vs activo + EAWS Paso 1.

EAWS 2025 Tabla 6 Paso 1: si no hay problema de avalancha activo → nivel 1 directo.
"""

import json
import os

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "salidas", "schema_boletines.json"
)


class TestFixS1Semantica:
    def test_problema_false_emite_nivel1_directo(self):
        """FIX-S1: problema_avalancha_presente=False → nivel 1 aunque las condiciones darían 3."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            estabilidad_satelital="poor",
            ventanas_criticas_detectadas=2,
            problema_avalancha_presente=False,
        )
        assert r["nivel_eaws_24h"] == 1
        assert r["nivel_eaws_48h"] == 1
        assert r["nivel_eaws_72h"] == 1
        assert r["tipo_problema_eaws"] == "no_distinct_avalanche_problem"
        assert r["problema_avalancha_presente"] is False

    def test_problema_false_fuente_tamano_indica_eaws_paso1(self):
        """FIX-S1: el campo fuente_tamano debe indicar que se activó EAWS Paso 1."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            problema_avalancha_presente=False,
        )
        assert r["factores_eaws"]["fuente_tamano"] == "eaws_paso1_no_problema"

    def test_problema_true_consulta_matriz(self):
        """FIX-S1: problema_avalancha_presente=True → la matriz EAWS se consulta normalmente."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            estabilidad_satelital="poor",
            ventanas_criticas_detectadas=2,
            problema_avalancha_presente=True,
            tipo_problema_eaws="new_snow",
        )
        assert r["nivel_eaws_24h"] >= 2
        assert r["tipo_problema_eaws"] == "new_snow"

    def test_problema_none_retrocompatibilidad(self):
        """FIX-S1: sin pasar problema_avalancha_presente (None) → comportamiento pre-v7.0."""
        r_nuevo = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            problema_avalancha_presente=None,
        )
        r_legacy = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
        )
        assert r_nuevo["nivel_eaws_24h"] == r_legacy["nivel_eaws_24h"]
        assert r_nuevo["nivel_eaws_24h"] >= 2

    def test_problema_false_preserva_factor_meteorologico(self):
        """FIX-S1: cuando EAWS Paso 1 activo, factor_meteorologico se preserva para trazabilidad."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            problema_avalancha_presente=False,
        )
        assert r["factor_meteorologico"] == "CICLO_DIURNO_NORMAL"

    def test_schema_boletines_incluye_campos_nuevos(self):
        """FIX-S1: schema_boletines.json debe incluir los dos campos nuevos con tipos correctos."""
        with open(_SCHEMA_PATH) as f:
            schema = json.load(f)
        nombres = {c["name"]: c for c in schema}
        assert "problema_avalancha_presente" in nombres, "campo problema_avalancha_presente ausente"
        assert "tipo_problema_eaws" in nombres, "campo tipo_problema_eaws ausente"
        assert nombres["problema_avalancha_presente"]["type"] == "BOOL"
        assert nombres["tipo_problema_eaws"]["type"] == "STRING"

    def test_output_incluye_campos_nuevos_en_path_normal(self):
        """FIX-S1: path normal (problema_avalancha_presente=True) retorna los dos campos."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="fair",
            factor_meteorologico="ESTABLE",
            problema_avalancha_presente=True,
            tipo_problema_eaws="wind_slab",
        )
        assert "problema_avalancha_presente" in r
        assert "tipo_problema_eaws" in r
        assert r["tipo_problema_eaws"] == "wind_slab"

    def test_output_incluye_campos_nuevos_en_path_legacy(self):
        """FIX-S1: path legacy (sin pasar campo) también retorna los claves (valor None)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="fair",
            factor_meteorologico="ESTABLE",
        )
        assert "problema_avalancha_presente" in r
        assert "tipo_problema_eaws" in r
        assert r["problema_avalancha_presente"] is None
