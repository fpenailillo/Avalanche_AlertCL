"""
Tests para EAWS Paso 1 v7.5 — gate basado en datos meteorológicos reales.

Principio: "sin datos meteo" ≠ "sin trigger". EAWS Paso 1 solo se activa
cuando S3 tenía datos reales que confirman ausencia de trigger.
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


class TestEAWSPaso1V75:
    def test_paso1_activa_con_datos_y_factor_neutro(self):
        """EAWS Paso 1 se activa cuando S3 tiene datos y factor es neutro y ventanas=0."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
        )
        assert r["nivel_eaws_24h"] == 1
        assert r["nivel_eaws_48h"] == 1
        assert r["nivel_eaws_72h"] == 1
        assert r["problema_avalancha_presente"] is False
        assert "paso1" in r["factores_eaws"]["fuente_tamano"]

    def test_paso1_activa_con_ciclo_diurno_normal(self):
        """EAWS Paso 1 también aplica con CICLO_DIURNO_NORMAL (factor neutro)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
        )
        assert r["nivel_eaws_24h"] == 1
        assert r["problema_avalancha_presente"] is False

    def test_paso1_no_activa_sin_datos_meteo(self):
        """EAWS Paso 1 NO se activa cuando condiciones_meteo_disponibles=False."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
        )
        assert r["nivel_eaws_24h"] >= 2
        assert r["problema_avalancha_presente"] is None

    def test_paso1_no_activa_sin_parametro(self):
        """EAWS Paso 1 NO se activa cuando condiciones_meteo_disponibles se omite (None)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
        )
        assert r["nivel_eaws_24h"] >= 2
        assert r["problema_avalancha_presente"] is None

    def test_paso1_no_activa_con_factor_activo(self):
        """EAWS Paso 1 NO se activa si factor_meteorologico es activo aunque datos=True."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
        )
        assert r["nivel_eaws_24h"] >= 2
        assert r["problema_avalancha_presente"] is None

    def test_paso1_no_activa_con_ventanas_criticas(self):
        """EAWS Paso 1 NO se activa si ventanas_criticas_detectadas > 0 aunque datos=True."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="fair",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=1,
            condiciones_meteo_disponibles=True,
        )
        assert r["nivel_eaws_24h"] >= 1
        assert r["problema_avalancha_presente"] is None

    def test_paso1_preserva_factor_meteorologico(self):
        """Cuando EAWS Paso 1 activa, factor_meteorologico se preserva para trazabilidad."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
        )
        assert r["factor_meteorologico"] == "CICLO_DIURNO_NORMAL"

    def test_paso1_no_activa_retroactivo_simula_sin_datos(self):
        """Simula un run retroactivo: S3 sin datos → camino conservador, no nivel 1."""
        r_retro = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
        )
        r_normal = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
        )
        assert r_retro["nivel_eaws_24h"] == r_normal["nivel_eaws_24h"]
        assert r_retro["nivel_eaws_24h"] >= 2

    def test_schema_boletines_incluye_campos(self):
        """schema_boletines.json debe conservar los dos campos BQ con tipos correctos."""
        with open(_SCHEMA_PATH) as f:
            schema = json.load(f)
        nombres = {c["name"]: c for c in schema}
        assert "problema_avalancha_presente" in nombres
        assert "tipo_problema_eaws" in nombres
        assert nombres["problema_avalancha_presente"]["type"] == "BOOL"
        assert nombres["tipo_problema_eaws"]["type"] == "STRING"
