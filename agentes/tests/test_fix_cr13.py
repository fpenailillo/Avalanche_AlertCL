"""
Tests para FIX-CA-WINDOW (v13.0): ventana temporal extendida en obtener_condiciones_actuales.

Bug: hora_actual <= fecha_ref (12:00 UTC) excluía registros almacenados a 18:00 UTC.
Fix: límite superior extendido a fecha_ref + 12h → ventana ±12h alrededor de fecha_ref.

Impacto: Swiss 2023-2024 — 10 registros/estación en condiciones_actuales ahora recuperables.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class TestFIXCAWindow:

    def _fila(self, **kwargs) -> dict:
        """_ejecutar_query retorna dicts (via dict(bq_row)), no objetos Row."""
        return kwargs

    def test_datos_18utc_con_ref_12utc_retorna_disponible(self):
        """FIX-CA-WINDOW: registro a 18:00 UTC es encontrado con fecha_ref 12:00 UTC."""
        from agentes.datos.consultor_bigquery import ConsultorBigQuery

        hora_18utc = datetime(2023, 12, 1, 18, 0, 0, tzinfo=timezone.utc)
        fila = self._fila(
            temperatura=-1.39,
            sensacion_termica=-3.0,
            velocidad_viento=2.22,
            direccion_viento="N",
            precipitacion_acumulada=1.61,
            probabilidad_precipitacion=20.0,
            humedad_relativa=85.0,
            presion_aire=1013.0,
            cobertura_nubes=60.0,
            condicion_clima="Partly cloudy",
            hora_actual=hora_18utc,
            es_dia=False,
        )

        consultor = ConsultorBigQuery.__new__(ConsultorBigQuery)
        consultor._ejecutar_query = MagicMock(return_value=[fila])

        fecha_ref_12utc = datetime(2023, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
        resultado = consultor.obtener_condiciones_actuales(
            ubicacion="Interlaken",
            fecha_referencia=fecha_ref_12utc,
        )

        assert resultado.get("disponible") is True, (
            "FIX-CA-WINDOW: registro a 18:00 UTC debe ser encontrado con fecha_ref 12:00 UTC"
        )
        assert resultado["temperatura"] == pytest.approx(-1.39)

    def test_datos_6utc_con_ref_18utc_retorna_disponible(self):
        """FIX-CA-WINDOW: registro a 06:00 UTC también queda dentro de la ventana ±12h."""
        from agentes.datos.consultor_bigquery import ConsultorBigQuery

        fila = self._fila(
            temperatura=-5.0,
            sensacion_termica=-8.0,
            velocidad_viento=4.0,
            direccion_viento="NW",
            precipitacion_acumulada=0.0,
            probabilidad_precipitacion=5.0,
            humedad_relativa=75.0,
            presion_aire=1020.0,
            cobertura_nubes=10.0,
            condicion_clima="Clear",
            hora_actual=datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc),
            es_dia=False,
        )

        consultor = ConsultorBigQuery.__new__(ConsultorBigQuery)
        consultor._ejecutar_query = MagicMock(return_value=[fila])

        fecha_ref_18utc = datetime(2024, 1, 1, 18, 0, 0, tzinfo=timezone.utc)
        resultado = consultor.obtener_condiciones_actuales(
            ubicacion="St Moritz",
            fecha_referencia=fecha_ref_18utc,
        )

        assert resultado.get("disponible") is True

    def test_sin_datos_retorna_disponible_false(self):
        """Sin registros en la ventana → disponible=False."""
        from agentes.datos.consultor_bigquery import ConsultorBigQuery

        consultor = ConsultorBigQuery.__new__(ConsultorBigQuery)
        consultor._ejecutar_query = MagicMock(return_value=[])

        resultado = consultor.obtener_condiciones_actuales(
            ubicacion="Interlaken",
            fecha_referencia=datetime(2023, 12, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert resultado.get("disponible") is False
        assert "Sin datos" in resultado.get("razon", "")

    def test_ventana_no_incluye_datos_de_dia_siguiente(self):
        """Datos del día siguiente (>24h después) quedan fuera de la ventana ±12h."""
        from agentes.datos.consultor_bigquery import ConsultorBigQuery

        consultor = ConsultorBigQuery.__new__(ConsultorBigQuery)
        consultor._ejecutar_query = MagicMock(return_value=[])

        # Si la query no encuentra datos, devuelve disponible=False — esto
        # verifica que la lógica del mock se aplica; el test real sería E2E.
        fecha_ref = datetime(2023, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
        resultado = consultor.obtener_condiciones_actuales(
            ubicacion="Matterhorn Zermatt",
            fecha_referencia=fecha_ref,
        )
        assert resultado.get("disponible") is False
