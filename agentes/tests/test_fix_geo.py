"""
Tests para FIX-GEO (v7.0): cap tamano≤3 condicional por región geográfica.

El cap FIX-T de v6.2 se aplica solo en Andes Chile; en Alpes suizos no aplica.
"""

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

_TOPO_GRANDE = {
    "desnivel_inicio_deposito_m": 900.0,
    "zona_inicio_ha": 60.0,
    "pendiente_max_grados": 42.0,
    "ventanas_criticas_detectadas": 0,
    "factor_meteorologico": "ESTABLE",
    "estabilidad_topografica": "poor",
}


class TestFixGeo:
    def test_cap_aplica_en_andes(self):
        """FIX-GEO: La Parva con topografía grande → tamano capado a 3."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="La Parva Sector Alto",
            **_TOPO_GRANDE,
        )
        assert r["factores_eaws"]["tamano"] == 3
        assert "cap_calmo" in r["factores_eaws"]["fuente_tamano"]

    def test_cap_no_aplica_en_alpes(self):
        """FIX-GEO: Interlaken con la misma topografía → sin cap (tamano≥4)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="Interlaken",
            **_TOPO_GRANDE,
        )
        assert r["factores_eaws"]["tamano"] >= 4
        assert "cap_calmo" not in r["factores_eaws"]["fuente_tamano"]

    def test_cap_no_aplica_en_alpes_matterhorn(self):
        """FIX-GEO: Matterhorn Zermatt → sin cap."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="Matterhorn Zermatt",
            **_TOPO_GRANDE,
        )
        assert "cap_calmo" not in r["factores_eaws"]["fuente_tamano"]

    def test_alpes_factor_activo_no_modifica_comportamiento(self):
        """FIX-GEO: con factor activo, el cap de todos modos no aplica (condición pre-existente)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="St Moritz",
            desnivel_inicio_deposito_m=900.0,
            zona_inicio_ha=60.0,
            pendiente_max_grados=42.0,
            ventanas_criticas_detectadas=0,
            factor_meteorologico="NEVADA_RECIENTE",
            estabilidad_topografica="poor",
        )
        assert "cap_calmo" not in r["factores_eaws"]["fuente_tamano"]

    def test_andes_factor_activo_no_aplica_cap(self):
        """FIX-GEO: en Andes con factor activo (nevada), el cap tampoco aplica."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="La Parva Sector Alto",
            desnivel_inicio_deposito_m=900.0,
            zona_inicio_ha=60.0,
            pendiente_max_grados=42.0,
            ventanas_criticas_detectadas=0,
            factor_meteorologico="NEVADA_RECIENTE",
            estabilidad_topografica="poor",
        )
        assert "cap_calmo" not in r["factores_eaws"]["fuente_tamano"]

    def test_ubicacion_desconocida_default_andes(self):
        """FIX-GEO: ubicación no mapeada → default andes_chile → cap aplicado."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="Portillo",
            **_TOPO_GRANDE,
        )
        assert r["factores_eaws"]["tamano"] == 3
        assert "cap_calmo" in r["factores_eaws"]["fuente_tamano"]

    def test_sin_nombre_ubicacion_default_andes(self):
        """FIX-GEO: sin nombre_ubicacion → default andes_chile (retrocompatibilidad)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(**_TOPO_GRANDE)
        assert r["factores_eaws"]["tamano"] == 3
        assert "cap_calmo" in r["factores_eaws"]["fuente_tamano"]

    def test_h4_la_parva_sin_cambio(self):
        """FIX-GEO: métricas H4 La Parva no deben cambiar — cap sigue activo."""
        r_alto = ejecutar_clasificar_riesgo_eaws_integrado(
            nombre_ubicacion="La Parva Sector Alto",
            **_TOPO_GRANDE,
        )
        r_sin_nombre = ejecutar_clasificar_riesgo_eaws_integrado(**_TOPO_GRANDE)
        assert r_alto["factores_eaws"]["tamano"] == r_sin_nombre["factores_eaws"]["tamano"] == 3
