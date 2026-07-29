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
from agentes.salidas.almacenador import (
    _consolidar_registros,
    _datos_satelitales_disponibles,
    _derivar_tendencia,
    _parsear_boletin_texto,
)


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

def _registro(ubicacion, n24, n48, n72, problema=None, secundarios=None):
    return {
        "ubicacion": ubicacion,
        "nivel_eaws": n24,
        "nivel_eaws_48h": n48,
        "nivel_eaws_72h": n72,
        "problema": problema,
        "problemas_secundarios": secundarios or [],
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

    def test_sector_representativo_manda_aunque_no_sea_el_peor(self):
        """La Parva se publica con su Sector Medio, no con el sector dominante."""
        boletines = _consolidar_registros([
            _registro("La Parva Sector Bajo", 3, 3, 3),
            _registro("La Parva Sector Medio", 2, 2, 1),
            _registro("La Parva Sector Alto", 4, 4, 4),
        ])
        assert len(boletines) == 1
        b = boletines[0]
        assert b["zona"] == "La Parva"
        assert (b["nivel_eaws"], b["nivel_eaws_48h"], b["nivel_eaws_72h"]) == (2, 2, 1)

    def test_problema_de_otro_sector_llega_como_secundario(self):
        """
        La Parva, 25-jul-2026: llovió en el Sector Bajo mientras el Medio —el
        representativo— nevaba. El dominante sigue siendo el del Medio, pero la
        nieve húmeda del Bajo no puede desaparecer de la ficha.
        """
        boletines = _consolidar_registros([
            _registro("La Parva Sector Bajo", 4, 5, 5, problema="wet_snow",
                      secundarios=["new_snow"]),
            _registro("La Parva Sector Medio", 4, 5, 4, problema="new_snow"),
            _registro("La Parva Sector Alto", 4, 5, 4, problema="new_snow"),
        ])
        assert len(boletines) == 1
        b = boletines[0]
        assert b["problema"] == "new_snow"
        assert b["problemas_secundarios"] == ["wet_snow"]

    def test_no_distinct_no_se_lista_como_secundario(self):
        boletines = _consolidar_registros([
            _registro("La Parva Sector Medio", 2, 2, 2, problema="new_snow"),
            _registro("La Parva Sector Bajo", 2, 2, 2, problema="no_distinct"),
        ])
        assert boletines[0]["problemas_secundarios"] == []

    def test_zona_sin_sectores_conserva_sus_secundarios(self):
        boletines = _consolidar_registros([
            _registro("Portillo", 3, 3, 2, problema="wet_snow",
                      secundarios=["new_snow"]),
        ])
        assert boletines[0]["problema"] == "wet_snow"
        assert boletines[0]["problemas_secundarios"] == ["new_snow"]

    def test_sin_sector_representativo_cae_al_peor(self):
        """Si la corrida no trajo el Sector Medio, vuelve el criterio conservador."""
        boletines = _consolidar_registros([
            _registro("La Parva Sector Bajo", 3, 3, 3),
            _registro("La Parva Sector Alto", 4, 4, 4),
        ])
        assert len(boletines) == 1
        assert boletines[0]["nivel_eaws"] == 4


# ── _datos_satelitales_disponibles ────────────────────────────────────────────

def _llamada(tool, **resultado):
    return {"tool": tool, "iteracion": 0, "resultado": resultado}


class TestDatosSatelitalesDisponibles:
    def test_lectura_optica_util(self):
        """Traza de una zona con imagen: NDSI y ViT con datos."""
        assert _datos_satelitales_disponibles([
            _llamada("consultar_estado_manto", disponible=True),
            _llamada("procesar_ndsi", disponible=True),
            _llamada("analizar_vit", disponible=True),
        ]) is True

    def test_ndsi_sin_lectura_y_sin_vit(self):
        """Nubosidad: procesar_ndsi retorna disponible=False y no se llama al ViT."""
        assert _datos_satelitales_disponibles([
            _llamada("consultar_estado_manto", disponible=True),
            _llamada("procesar_ndsi", disponible=False),
            _llamada("analizar_via_earth_ai", disponible=True),
        ]) is False

    def test_ndsi_sin_lectura_con_vit_sin_datos(self):
        """La otra variante observada: el ViT sí corre, pero sin serie que analizar."""
        assert _datos_satelitales_disponibles([
            _llamada("procesar_ndsi", disponible=False),
            _llamada("analizar_vit", disponible=False, estado_vit="sin_datos"),
        ]) is False

    def test_tools_derivadas_no_encienden_el_flag(self):
        """snowline y anomalías se derivan del NDSI: no son evidencia propia."""
        assert _datos_satelitales_disponibles([
            _llamada("procesar_ndsi", disponible=False),
            _llamada("detectar_anomalias_satelitales", alertas_satelitales=[]),
            _llamada("calcular_snowline", snowline_estimada_m=3000),
        ]) is False

    def test_sin_tools_satelitales(self):
        assert _datos_satelitales_disponibles([_llamada("analizar_dem", disponible=True)]) is False

    def test_resultado_ausente_o_no_dict(self):
        """Trazas viejas sin campo 'resultado' no deben contar como disponibles."""
        assert _datos_satelitales_disponibles([
            {"tool": "procesar_ndsi", "iteracion": 0},
            {"tool": "analizar_vit", "resultado": "texto plano"},
        ]) is False


# ── _parsear_boletin_texto (pronóstico 3d + precipitación) ────────────────────

_TEXTO_PRONOSTICO = """DATOS METEOROLÓGICOS
------------------------------
Condiciones actuales:
  Temperatura: -2.3°C | Viento: 5 km/h | Precipitación reciente: 109.6 mm
Pronóstico 3 días:
  2026-07-17 | T -1°C/-4°C | Precip 83 mm | Nieve ~131 cm | Viento 6 km/h | HEAVY_SNOW_STORM
  2026-07-18 | T -2°C/-5°C | Precip 60 mm | Viento 8 km/h | HEAVY_SNOW_STORM
"""


class TestParsearBoletinTexto:
    def test_pronostico_3d_con_campo_nieve_opcional(self):
        campos = _parsear_boletin_texto(_TEXTO_PRONOSTICO)
        assert len(campos["pronostico_3d"]) == 2
        d1, d2 = campos["pronostico_3d"]
        assert d1["precip_mm"] == 83.0 and d1["nieve_cm"] == 131.0
        assert d1["cielo"] == "HEAVY_SNOW_STORM"
        assert d2["nieve_cm"] is None and d2["viento_kmh"] == 8.0

    def test_precipitacion_acepta_ambas_etiquetas(self):
        assert _parsear_boletin_texto(_TEXTO_PRONOSTICO)["precip_24h_mm"] == 109.6
        viejo = _TEXTO_PRONOSTICO.replace("Precipitación reciente:", "Precipitación 24h:")
        assert _parsear_boletin_texto(viejo)["precip_24h_mm"] == 109.6
