"""
Tests para FIX-H (v7.0): default estabilidad_satelital por región cuando ViT retorna sin_datos.

En Andes Chile: default 'fair' (ViT entrenado aquí, sin_datos es raro → incertidumbre baja).
En Alpes suizos: default 'poor' (ViT fuera de dominio → incertidumbre alta, conservador).
"""

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
    _determinar_estabilidad_dominante,
)


class TestFixH:
    def test_andes_sin_datos_default_fair(self):
        """FIX-H: La Parva sin estabilidad satelital → usa default 'fair' (Andes)."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="fair",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        # Con topo='fair' e idx_sat='fair' (default Andes), la dominante es 'fair'
        assert estabilidad == "fair"

    def test_alpes_sin_datos_default_poor(self):
        """FIX-H: Interlaken sin estabilidad satelital → usa default 'poor' (Alpes)."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        # Con topo='good' e idx_sat='poor' (default Alpes), la dominante es 'poor'
        assert estabilidad == "poor"

    def test_alpes_con_datos_no_afectado(self):
        """FIX-H: con estabilidad satelital explícita, FIX-H no interfiere."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital="good",
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        assert estabilidad == "good"

    def test_ubicacion_desconocida_default_andes(self):
        """FIX-H: sin nombre_ubicacion o no mapeada → default Andes ('fair')."""
        e_sin_nombre = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
        )
        e_no_mapeada = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Portillo",
        )
        # ambos deben usar 'fair' como default (andes_chile)
        assert e_sin_nombre == e_no_mapeada

    def test_alpes_default_poor_eleva_nivel(self):
        """FIX-H: en Alpes, default 'poor' (en lugar de 'fair') eleva el nivel final."""
        r_alpes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        r_andes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        # El nivel Alpes debe ser ≥ nivel Andes (default más conservador)
        assert r_alpes["nivel_eaws_24h"] >= r_andes["nivel_eaws_24h"]

    def test_h4_andes_sin_cambio_retrocompat(self):
        """FIX-H: la llamada sin nombre_ubicacion produce el mismo resultado que antes."""
        r_sin = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
        )
        r_andes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            nombre_ubicacion="La Parva Sector Alto",
        )
        assert r_sin["nivel_eaws_24h"] == r_andes["nivel_eaws_24h"]
