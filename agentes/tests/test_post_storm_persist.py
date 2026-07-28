"""
Tests de FIX-POST-STORM-PERSIST v25.18: el piso post-tormenta se ancla al nivel
RAW del evento (la nevada real) y no al nivel publicado de ayer, que podía ser
él mismo un piso y encadenar la persistencia más allá de las 48h.

Caso de referencia: Valle Nevado, 25-28 jul 2026.
    25-jul  raw 5  → publicado 5   (tormenta real)
    26-jul  raw 2  → publicado 4   (evento hace 1 día: 5-1)
    27-jul  raw 2  → publicado 3   (evento hace 2 días: 5-2)
    28-jul  raw 4  → publicado 4   (fuera de ventana: manda la física)
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    _obtener_evento_post_tormenta,
)


def _historial(*boletines):
    """Historial BQ (orden DESC por fecha) como lo devuelve ConsultorBigQuery."""
    return {"disponible": True, "boletines": list(boletines), "n_boletines": len(boletines)}


def _boletin(fecha, publicado, raw=None):
    return {
        "fecha": fecha,
        "nivel_eaws_24h": publicado,
        "nivel_eaws_24h_raw": raw if raw is not None else publicado,
        "factor_meteorologico": "NEVADA_RECIENTE",
        "confianza": "Alta",
    }


def _evento(hist, hoy="2026-07-27"):
    """
    Ejecuta la búsqueda de evento con historial y fecha de hoy simulados.

    Se parchea el módulo real en vez de sustituirlo en sys.modules: la función
    hace `from agentes.datos import consultor_bigquery`, que resuelve por
    atributo del paquete cuando otro test ya lo importó, y entonces un parche
    sobre sys.modules pasa desapercibido.
    """
    consultor = MagicMock()
    consultor.obtener_historial_boletines.return_value = hist
    with patch(
        "agentes.datos.consultor_bigquery.ConsultorBigQuery", return_value=consultor
    ), patch(
        "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
        return_value=datetime.fromisoformat(f"{hoy}T12:00:00+00:00"),
    ):
        return _obtener_evento_post_tormenta("Valle Nevado")


class TestEventoPostTormenta:
    def test_tormenta_ayer(self):
        """26-jul: la tormenta del 25 (raw 5) está a un día."""
        assert _evento(
            _historial(_boletin("2026-07-25", 5)), hoy="2026-07-26"
        ) == (5, 1)

    def test_tormenta_anteayer_no_se_encadena(self):
        """27-jul: el ancla es el raw 5 del 25, no el 4 publicado del 26."""
        assert _evento(
            _historial(_boletin("2026-07-26", 4, raw=2), _boletin("2026-07-25", 5)),
            hoy="2026-07-27",
        ) == (5, 2)

    def test_fuera_de_ventana_48h(self):
        """28-jul: la tormenta quedó a 3 días — sin piso, manda la física."""
        assert _evento(
            _historial(_boletin("2026-07-27", 3, raw=2), _boletin("2026-07-26", 4, raw=2)),
            hoy="2026-07-28",
        ) is None

    def test_piso_no_se_sostiene_solo(self):
        """Un nivel 4 publicado que era solo piso (raw 2) no funda otro piso."""
        assert _evento(
            _historial(_boletin("2026-07-26", 4, raw=2)), hoy="2026-07-27"
        ) is None

    def test_sin_historial(self):
        assert _evento(_historial(), hoy="2026-07-27") is None

    def test_niveles_bajos_no_son_evento(self):
        assert _evento(
            _historial(_boletin("2026-07-26", 3), _boletin("2026-07-25", 2)),
            hoy="2026-07-27",
        ) is None

    def test_evento_mas_reciente_manda(self):
        """Dos tormentas en la ventana: el piso lo fija la más reciente."""
        assert _evento(
            _historial(_boletin("2026-07-26", 4), _boletin("2026-07-25", 5)),
            hoy="2026-07-27",
        ) == (4, 1)

    def test_raw_ausente_cae_al_publicado(self):
        """Boletines viejos sin columna raw: el publicado es la mejor referencia."""
        hist = _historial({"fecha": "2026-07-26", "nivel_eaws_24h": 4, "nivel_eaws_24h_raw": None})
        assert _evento(hist, hoy="2026-07-27") == (4, 1)

    def test_fecha_invalida_se_ignora(self):
        hist = _historial({"fecha": "sin-fecha", "nivel_eaws_24h": 5, "nivel_eaws_24h_raw": 5})
        assert _evento(hist, hoy="2026-07-27") is None
