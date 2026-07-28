"""
Tests de agentes/datos/precipitacion.py — tipo de precipitación observado.

Caso de referencia: La Parva Sector Bajo, 25-jul-2026. Google Weather reportó
RAIN_AND_SNOW y LIGHT_RAIN con temperatura del aire de 0,8-0,9 °C; el sistema
publicó `new_snow` porque el tipo se inferría por temperatura (>2 °C = lluvia).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agentes.datos.precipitacion import (
    es_lluvia,
    es_nieve,
    hay_fase_liquida,
    resumir_horas,
)


def _hora(tipo, mm=1.0, temp=0.9, bh=0.3):
    return {"tipo": tipo, "precipitacion_mm": mm, "temperatura_c": temp, "bulbo_humedo_c": bh}


class TestClasificacionTipo:
    def test_lluvia_en_sus_variantes(self):
        for tipo in ("RAIN", "LIGHT_RAIN", "HEAVY_RAIN", "FREEZING_RAIN"):
            assert es_lluvia(tipo), tipo

    def test_mixto_cuenta_como_lluvia_no_como_nieve(self):
        """RAIN_AND_SNOW moja el manto: para el problema EAWS es fase líquida."""
        assert es_lluvia("RAIN_AND_SNOW")
        assert not es_nieve("RAIN_AND_SNOW")

    def test_nieve(self):
        assert es_nieve("SNOW")
        assert not es_lluvia("SNOW")

    def test_none_y_vacios(self):
        for valor in ("NONE", None, "", "   "):
            assert not es_lluvia(valor)
            assert not es_nieve(valor)

    def test_case_y_espacios(self):
        assert es_lluvia(" rain ")
        assert es_nieve("snow")


class TestFaseLiquida:
    def test_tipo_observado_manda_sobre_bulbo_humedo(self):
        """El proveedor dice SNOW aunque el bulbo húmedo esté alto: gana el dato."""
        assert not hay_fase_liquida("SNOW", bulbo_humedo_c=2.0)

    def test_caso_25_jul_lluvia_con_bulbo_humedo_bajo(self):
        """0,3 °C de bulbo húmedo, pero el tipo observado es mixto: es lluvia."""
        assert hay_fase_liquida("RAIN_AND_SNOW", bulbo_humedo_c=0.3)

    def test_sin_tipo_decide_el_bulbo_humedo(self):
        assert hay_fase_liquida(None, bulbo_humedo_c=1.2)
        assert not hay_fase_liquida(None, bulbo_humedo_c=0.4)

    def test_sin_tipo_ni_bulbo_humedo(self):
        assert not hay_fase_liquida(None, None)


class TestResumirHoras:
    def test_caso_la_parva_sector_bajo_25_jul(self):
        """11 h de lluvia sobre 7 h de nieve — evento de lluvia sobre nieve."""
        horas = [_hora("RAIN_AND_SNOW", 0.2)] * 3 + [_hora("LIGHT_RAIN", 0.5)] * 8
        horas += [_hora("SNOW", 1.0, temp=-1.0, bh=-1.2)] * 7
        r = resumir_horas(horas)
        assert r["horas_lluvia"] == 11
        assert r["horas_nieve"] == 7
        assert r["mm_lluvia"] == 4.6
        assert r["hay_lluvia_sobre_nieve"] is True
        assert r["temperatura_max_c"] == 0.9

    def test_caso_sector_alto_solo_nieve(self):
        r = resumir_horas([_hora("SNOW", 0.8, temp=0.5, bh=0.2)] * 19)
        assert r["horas_lluvia"] == 0
        assert r["hay_lluvia_sobre_nieve"] is False

    def test_chubasco_aislado_no_es_lluvia_sobre_nieve(self):
        """Una sola hora de lluvia no basta: se exige persistencia."""
        r = resumir_horas([_hora("RAIN", 0.3)] + [_hora("SNOW", 1.0)] * 10)
        assert r["horas_lluvia"] == 1
        assert r["hay_lluvia_sobre_nieve"] is False

    def test_tipo_lluvia_sin_milimetros_no_cuenta(self):
        """RAIN con 0 mm es pronóstico de tipo, no lluvia caída sobre el manto."""
        r = resumir_horas([_hora("RAIN", 0.0)] * 6)
        assert r["horas_lluvia"] == 6
        assert r["mm_lluvia"] == 0.0
        assert r["hay_lluvia_sobre_nieve"] is False

    def test_llovizna_bajo_el_umbral_no_humedece(self):
        """5 h de lluvia sumando 1 mm: persistente pero sin monto para percolar."""
        r = resumir_horas([_hora("RAIN", 0.2)] * 5)
        assert r["horas_lluvia"] == 5
        assert r["mm_lluvia"] == 1.0
        assert r["hay_lluvia_sobre_nieve"] is False

    def test_umbral_exacto_de_3mm_cuenta(self):
        r = resumir_horas([_hora("RAIN", 1.5)] * 2)
        assert r["mm_lluvia"] == 3.0
        assert r["hay_lluvia_sobre_nieve"] is True

    def test_sin_horas(self):
        r = resumir_horas([])
        assert r["horas_lluvia"] == 0
        assert r["mm_total"] == 0.0
        assert r["temperatura_max_c"] is None
        assert r["hay_lluvia_sobre_nieve"] is False

    def test_campos_ausentes_no_rompen(self):
        r = resumir_horas([{"tipo": "SNOW"}, {}])
        assert r["mm_total"] == 0.0
        assert r["bulbo_humedo_max_c"] is None
