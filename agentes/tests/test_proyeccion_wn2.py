"""
Tests de FIX-WN2-PROYECCION-3D (niveles 48/72h desde pronóstico WN2 D+1/D+2),
_derivar_tendencia y la consolidación multi-sector coherente.
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    _delta_dia_wn2,
    _proyectar_niveles_wn2,
)
from agentes.salidas.almacenador import _consolidar_registros, _derivar_tendencia


def _features(**kwargs) -> dict:
    base = dict(
        disponible=True,
        nieve_24h_p50=0.0,
        nieve_24h_p95=0.0,
        heavy_snow=False,
        storm_slab=False,
        wind_strong=False,
        wet_snow=False,
    )
    base.update(kwargs)
    return base


# ── _delta_dia_wn2 ────────────────────────────────────────────────────────────

class TestDeltaDiaWN2:
    def test_heavy_snow_sube(self):
        assert _delta_dia_wn2(_features(heavy_snow=True)) == 1

    def test_storm_slab_sube(self):
        assert _delta_dia_wn2(_features(storm_slab=True)) == 1

    def test_nevada_fuerte_p50_sube(self):
        assert _delta_dia_wn2(_features(nieve_24h_p50=20.0)) == 1

    def test_viento_con_nieve_sube(self):
        assert _delta_dia_wn2(_features(wind_strong=True, nieve_24h_p50=10.0)) == 1

    def test_viento_sin_nieve_mantiene(self):
        assert _delta_dia_wn2(_features(wind_strong=True)) == 0

    def test_nieve_humeda_mantiene(self):
        assert _delta_dia_wn2(_features(wet_snow=True)) == 0

    def test_nevada_menor_mantiene(self):
        assert _delta_dia_wn2(_features(nieve_24h_p50=5.0)) == 0

    def test_dia_tranquilo_baja(self):
        assert _delta_dia_wn2(_features()) == -1


# ── _proyectar_niveles_wn2 ────────────────────────────────────────────────────

_MOD_WN2 = "agentes.datos.wn2_features.obtener_features_wn2"
_MOD_FREF = "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global"
_FREF = datetime(2026, 7, 17, tzinfo=timezone.utc)


class TestProyectarNivelesWN2:
    def test_flag_off_retorna_none(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "false")
        assert _proyectar_niveles_wn2(3, "Portillo") is None

    def test_sin_ubicacion_retorna_none(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        assert _proyectar_niveles_wn2(3, None) is None

    def test_wn2_no_disponible_retorna_none(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        with patch(_MOD_FREF, return_value=_FREF), \
             patch(_MOD_WN2, return_value=_features(disponible=False)):
            assert _proyectar_niveles_wn2(3, "Portillo") is None

    def test_tormenta_d1_calma_d2(self, monkeypatch):
        """D+1 nevada fuerte (+1), D+2 calma (-1) → 48h sube, 72h vuelve."""
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        dias = [_features(heavy_snow=True, nieve_24h_p50=30.0), _features()]
        with patch(_MOD_FREF, return_value=_FREF), \
             patch(_MOD_WN2, side_effect=dias):
            assert _proyectar_niveles_wn2(3, "Portillo") == (4, 3)

    def test_clip_superior_en_5(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        dias = [_features(heavy_snow=True), _features(heavy_snow=True)]
        with patch(_MOD_FREF, return_value=_FREF), \
             patch(_MOD_WN2, side_effect=dias):
            assert _proyectar_niveles_wn2(5, "Portillo") == (5, 5)

    def test_descenso_maximo_un_escalon_por_dia(self, monkeypatch):
        """Dos días de calma: 72h no puede caer más de 1 bajo el 48h."""
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        dias = [_features(), _features()]
        with patch(_MOD_FREF, return_value=_FREF), \
             patch(_MOD_WN2, side_effect=dias):
            n48, n72 = _proyectar_niveles_wn2(4, "Portillo")
            assert (n48, n72) == (3, 2)
            assert n72 >= n48 - 1

    def test_piso_inferior_en_1(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        dias = [_features(), _features()]
        with patch(_MOD_FREF, return_value=_FREF), \
             patch(_MOD_WN2, side_effect=dias):
            assert _proyectar_niveles_wn2(1, "Portillo") == (1, 1)

    def test_excepcion_retorna_none(self, monkeypatch):
        monkeypatch.setenv("USE_WEATHERNEXT2", "true")
        with patch(_MOD_FREF, side_effect=RuntimeError("BQ caído")):
            assert _proyectar_niveles_wn2(3, "Portillo") is None


# ── _derivar_tendencia ────────────────────────────────────────────────────────

class TestDerivarTendencia:
    def test_en_aumento(self):
        assert _derivar_tendencia(3, 4) == "en aumento"

    def test_en_descenso(self):
        assert _derivar_tendencia(4, 3) == "en descenso"

    def test_estable(self):
        assert _derivar_tendencia(3, 3) == "estable"

    def test_sin_niveles_usa_fallback(self):
        assert _derivar_tendencia(3, None, "estable") == "estable"
        assert _derivar_tendencia(None, None) is None


# ── _consolidar_registros ─────────────────────────────────────────────────────

def _registro(ubicacion, n24, n48, n72):
    return {
        "ubicacion": ubicacion,
        "nivel_eaws": n24,
        "nivel_eaws_48h": n48,
        "nivel_eaws_72h": n72,
    }


class TestConsolidarRegistros:
    def test_trio_integro_del_sector_dominante(self):
        """El 48/72h del sector no dominante NO debe mezclarse con el dominante."""
        boletines = _consolidar_registros([
            _registro("La Parva Sector Bajo", 3, 5, 5),
            _registro("La Parva Sector Alto", 4, 4, 3),
        ])
        assert len(boletines) == 1
        b = boletines[0]
        assert b["zona"] == "La Parva"
        assert (b["nivel_eaws"], b["nivel_eaws_48h"], b["nivel_eaws_72h"]) == (4, 4, 3)

    def test_orden_de_llegada_no_afecta(self):
        a = _consolidar_registros([
            _registro("La Parva Sector Alto", 4, 4, 3),
            _registro("La Parva Sector Bajo", 3, 5, 5),
        ])
        b = _consolidar_registros([
            _registro("La Parva Sector Bajo", 3, 5, 5),
            _registro("La Parva Sector Alto", 4, 4, 3),
        ])
        assert a == b

    def test_zona_fuera_de_lista_descartada(self):
        boletines = _consolidar_registros([
            _registro("El Colorado", 5, 5, 5),
            _registro("Portillo", 3, 3, 2),
        ])
        assert [b["zona"] for b in boletines] == ["Portillo"]

    def test_registros_none_ignorados(self):
        boletines = _consolidar_registros([None, _registro("Portillo", 2, 2, 1)])
        assert len(boletines) == 1
