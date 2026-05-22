"""
Tests v15.0 — Integración WeatherNext 2: obtener_ventanas_6h + tool_pronostico_wn2_ventanas.

Cubre:
- FuenteWeatherNext2.obtener_ventanas_6h: estructura de salida con mock BQ
- tool_pronostico_wn2_ventanas: flag off → disponible=False, sin error
- tool_pronostico_wn2_ventanas: ubicación desconocida → disponible=False
- tool_pronostico_wn2_ventanas: flag on con BQ mockeado → estructura correcta
- Regresión: S3 registra la nueva tool y su ejecutor
- Almacenador: extrae campos wn2_* correctamente desde tools_llamadas
"""

import os
import pytest
from datetime import date
from unittest.mock import MagicMock, patch


# ── FuenteWeatherNext2.obtener_ventanas_6h ────────────────────────────────────

class TestObtenerVentanas6h:
    def _filas_mock(self):
        """Simula las 5 filas que devolvería la SQL v6 (4 ventanas + 1 diario)."""
        base_ventana = {
            "nivel": "ventana",
            "fecha_local": date(2026, 5, 15),
            "eaws_horizon": "H24",
            "init_time": None,
            "forecast_lead_hours": 12,
            "n_members": 64,
            "temp_mean_c": -4.2,
            "temp_p05_c": -6.1,
            "temp_p50_c": -4.0,
            "temp_p95_c": -2.5,
            "temp_std_c": 1.2,
            "temp_delta_mean_c": 0.8,
            "precip_p50_mm": 1.5,
            "precip_p95_mm": 4.8,
            "est_nieve_6h_cm_p50_raw": 10.1,
            "est_nieve_6h_cm_p50_corr": 1.01,
            "est_nieve_6h_cm_p95_corr": 3.22,
            "mslp_mean_hpa": 690.5,
            "wind_10m_mean_ms": 3.2,
            "wind_100m_mean_ms": 8.5,
            "wind_100m_max_ms": 12.1,
            "wind_100m_p95_ms": 11.0,
            "wdir_100m_mean_deg": 270.0,
            "wdir_100m_cardinal": "W",
            "wind_class_es": "moderado",
            "prob_snow_pct": 65.0,
            "prob_wet_snow_pct": 5.0,
            "prob_dry_snow_pct": 60.0,
            "prob_storm_slab_pct": 30.0,
            "prob_melt_freeze_pct": 10.0,
            "prob_rain_pct": 5.0,
            "snow_type_dominant": "dry_snow",
            "cota_0c_p05_m": 2800.0,
            "cota_0c_p50_m": 3100.0,
            "cota_0c_p95_m": 3400.0,
            "cota_0c_std_m": 150.0,
            "probable_avalanche_problem": "new_snow",
            "alert_heavy_snow": False,
            "alert_storm_slab": False,
            "alert_wet_snow": False,
            "alert_wind_strong": False,
            "confianza_pronostico": "media",
            "nieve_24h_cm_p50_corr": None,
            "nieve_24h_cm_p95_corr": None,
            "problema_dominante": None,
            "confianza_dia": None,
        }
        ventanas = []
        for i, nombre in enumerate(["manana", "tarde", "noche", "madrugada"]):
            v = dict(base_ventana)
            v["ventana"] = nombre
            v["ventana_orden"] = i + 1
            ventanas.append(v)

        diario = {
            "nivel": "diario",
            "fecha_local": date(2026, 5, 15),
            "ventana": "--- TOTAL DÍA ---",
            "ventana_orden": 9,
            "eaws_horizon": None,
            "init_time": None,
            "forecast_lead_hours": None,
            "n_members": None,
            "temp_mean_c": None,
            "temp_p05_c": -6.1,
            "temp_p50_c": None,
            "temp_p95_c": -1.0,
            "temp_std_c": None,
            "temp_delta_mean_c": None,
            "precip_p50_mm": 6.0,
            "precip_p95_mm": 19.2,
            "est_nieve_6h_cm_p50_raw": None,
            "est_nieve_6h_cm_p50_corr": 4.04,
            "est_nieve_6h_cm_p95_corr": 12.88,
            "mslp_mean_hpa": None,
            "wind_10m_mean_ms": None,
            "wind_100m_mean_ms": None,
            "wind_100m_max_ms": None,
            "wind_100m_p95_ms": None,
            "wdir_100m_mean_deg": None,
            "wdir_100m_cardinal": None,
            "wind_class_es": None,
            "prob_snow_pct": None,
            "prob_wet_snow_pct": None,
            "prob_dry_snow_pct": None,
            "prob_storm_slab_pct": None,
            "prob_melt_freeze_pct": None,
            "prob_rain_pct": None,
            "snow_type_dominant": None,
            "cota_0c_p05_m": None,
            "cota_0c_p50_m": None,
            "cota_0c_p95_m": None,
            "cota_0c_std_m": None,
            "cota_0c_min_dia_m": 2900.0,
            "cota_0c_media_dia_m": 3100.0,
            "cota_0c_max_dia_m": 3300.0,
            "snow_type_dia": "dry_snow",
            "probable_avalanche_problem": "new_snow",
            "alert_heavy_snow": False,
            "alert_storm_slab": False,
            "alert_wet_snow": False,
            "alert_wind_strong": False,
            "confianza_pronostico": "media",
            "nieve_24h_cm_p50_corr": 4.04,
            "nieve_24h_cm_p95_corr": 12.88,
            "problema_dominante": "new_snow",
            "confianza_dia": "media",
        }
        return ventanas + [diario]

    def test_ventanas_6h_estructura_correcta(self):
        """obtener_ventanas_6h retorna 4 ventanas + diario con todas las claves esperadas."""
        from agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2 import FuenteWeatherNext2

        filas = self._filas_mock()
        f = FuenteWeatherNext2()

        resultado = f._formatear_ventanas(filas, "La Parva Sector Alto", "2026-05-15")

        assert resultado["disponible"] is True
        assert resultado["zona"] == "La Parva Sector Alto"
        assert len(resultado["ventanas"]) == 4

        # Verificar claves esperadas en cada ventana
        claves_ventana = {
            "ventana", "fecha_local", "eaws_horizon",
            "temp_p50_c", "precip_p50_mm", "precip_p95_mm",
            "wind_100m_mean_ms", "wind_100m_p95_ms", "wind_class_es",
            "wdir_100m_cardinal", "prob_snow_pct", "probable_avalanche_problem",
            "alerts", "confianza",
        }
        for v in resultado["ventanas"]:
            for clave in claves_ventana:
                assert clave in v, f"Clave '{clave}' ausente en ventana"
            assert set(v["alerts"].keys()) == {"heavy_snow", "storm_slab", "wet_snow", "wind_strong"}

        # Verificar diario
        assert "diario" in resultado
        d = resultado["diario"]
        assert d["problema_dominante"] == "new_snow"
        assert d["confianza_dia"] == "media"
        assert "alerts_dia" in d

    def test_sin_filas_retorna_no_disponible(self):
        """Sin filas BQ → disponible=False con mensaje de error."""
        from agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2 import FuenteWeatherNext2

        f = FuenteWeatherNext2()
        resultado = f._formatear_ventanas([], "La Parva Sector Alto", "2020-01-01")

        assert resultado["disponible"] is False
        assert "error" in resultado

    def test_obtener_ventanas_6h_flag_off(self):
        """Con USE_WEATHERNEXT2=false, retorna disponible=False sin llamar BQ."""
        from agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2 import FuenteWeatherNext2

        f = FuenteWeatherNext2()
        # En tests USE_WEATHERNEXT2=false por defecto
        resultado = f.obtener_ventanas_6h("La Parva Sector Alto", -33.344, -70.280)

        assert resultado["disponible"] is False
        assert "error" in resultado


# ── Tool obtener_pronostico_wn2_ventanas ──────────────────────────────────────

class TestToolWN2Ventanas:
    def test_flag_off_retorna_disponible_false_sin_error(self):
        """Con USE_WEATHERNEXT2=false, tool retorna disponible=False + mensaje útil."""
        from agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas import (
            ejecutar_obtener_pronostico_wn2_ventanas,
        )

        with patch(
            "agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas._USE_WEATHERNEXT2",
            False,
        ):
            resultado = ejecutar_obtener_pronostico_wn2_ventanas("La Parva Sector Alto")

        assert resultado["disponible"] is False
        assert "mensaje" in resultado
        assert "USE_WEATHERNEXT2" in resultado["mensaje"]

    def test_ubicacion_desconocida_retorna_disponible_false(self):
        """Ubicación no registrada en COORDENADAS_ZONAS → disponible=False."""
        from agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas import (
            ejecutar_obtener_pronostico_wn2_ventanas,
        )

        with patch(
            "agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas._USE_WEATHERNEXT2",
            True,
        ):
            resultado = ejecutar_obtener_pronostico_wn2_ventanas("Ubicacion Inexistente XYZ")

        assert resultado["disponible"] is False
        assert "COORDENADAS_ZONAS" in resultado.get("mensaje", "")

    def test_flag_on_con_mock_bq_estructura_correcta(self):
        """Con WN2 activo y BQ mockeado, retorna estructura completa."""
        from agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas import (
            ejecutar_obtener_pronostico_wn2_ventanas,
        )

        salida_mock = {
            "disponible": True,
            "zona": "La Parva Sector Alto",
            "fecha_objetivo": "2026-05-15",
            "ventanas": [
                {
                    "ventana": "manana", "fecha_local": "2026-05-15",
                    "eaws_horizon": "H24", "temp_p50_c": -4.0,
                    "precip_p50_mm": 1.5, "precip_p95_mm": 4.8,
                    "wind_100m_mean_ms": 8.5, "wind_100m_p95_ms": 11.0,
                    "wdir_100m_cardinal": "W", "wind_class_es": "moderado",
                    "prob_snow_pct": 65.0, "probable_avalanche_problem": "new_snow",
                    "alerts": {"heavy_snow": False, "storm_slab": False,
                               "wet_snow": False, "wind_strong": False},
                    "confianza": "media",
                }
            ],
            "diario": {
                "fecha_local": "2026-05-15",
                "precip_24h_p50_mm": 6.0,
                "precip_24h_p95_mm": 19.2,
                "problema_dominante": "new_snow",
                "confianza_dia": "media",
                "alerts_dia": {"heavy_snow": False, "storm_slab": False,
                                "wet_snow": False, "wind_strong": False},
            },
        }

        with patch(
            "agentes.subagentes.subagente_meteorologico.tools.tool_pronostico_wn2_ventanas._USE_WEATHERNEXT2",
            True,
        ), patch(
            "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2.obtener_ventanas_6h",
            return_value=salida_mock,
        ), patch(
            "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2.disponible",
            new_callable=lambda: property(lambda self: True),
        ):
            resultado = ejecutar_obtener_pronostico_wn2_ventanas(
                "La Parva Sector Alto", "2026-05-15"
            )

        assert resultado["disponible"] is True
        assert "ventanas" in resultado
        assert "diario" in resultado
        assert resultado["diario"]["problema_dominante"] == "new_snow"


# ── Regresión S3 ──────────────────────────────────────────────────────────────

class TestRegresionS3WN2:
    def test_s3_registra_nueva_tool_y_ejecutor(self):
        """SubagenteMeteorologico registra obtener_pronostico_wn2_ventanas."""
        from agentes.subagentes.subagente_meteorologico.agente import SubagenteMeteorologico

        s = SubagenteMeteorologico()
        tools = {t["name"] for t in s._cargar_tools()}
        ejecutores = s._cargar_ejecutores()

        assert "obtener_pronostico_wn2_ventanas" in tools
        assert "obtener_pronostico_wn2_ventanas" in ejecutores
        assert callable(ejecutores["obtener_pronostico_wn2_ventanas"])

    def test_tools_originales_sin_regresion(self):
        """Las 4 tools originales de S3 siguen presentes y registradas."""
        from agentes.subagentes.subagente_meteorologico.agente import SubagenteMeteorologico

        s = SubagenteMeteorologico()
        tools = {t["name"] for t in s._cargar_tools()}
        ejecutores = s._cargar_ejecutores()

        originales = {
            "obtener_condiciones_actuales_meteo",
            "analizar_tendencia_72h",
            "obtener_pronostico_dias",
            "detectar_ventanas_criticas",
        }
        for tool in originales:
            assert tool in tools, f"Tool original '{tool}' desapareció"
            assert tool in ejecutores, f"Ejecutor original '{tool}' desapareció"


# ── Almacenador: extracción campos WN2 ───────────────────────────────────────

class TestAlmacenadorWN2:
    def _tools_llamadas_con_wn2(self, disponible: bool, problema: str = "new_snow"):
        """Simula tools_llamadas que incluye una llamada a WN2 exitosa."""
        if not disponible:
            return [{"tool": "obtener_pronostico_wn2_ventanas", "resultado": {"disponible": False, "mensaje": "WN2 off"}}]
        return [
            {
                "tool": "obtener_pronostico_wn2_ventanas",
                "resultado": {
                    "disponible": True,
                    "zona": "La Parva Sector Alto",
                    "ventanas": [],
                    "diario": {
                        "problema_dominante": problema,
                        "confianza_dia": "media",
                        "alerts_dia": {
                            "heavy_snow": False,
                            "storm_slab": True,
                            "wet_snow": False,
                            "wind_strong": True,
                        },
                    },
                },
            }
        ]

    def test_extrae_campos_wn2_cuando_disponible(self):
        from agentes.salidas.almacenador import _construir_campos_subagentes

        tools_llamadas = self._tools_llamadas_con_wn2(True, "storm_slab")
        campos = _construir_campos_subagentes(tools_llamadas, {})

        assert campos["wn2_avalanche_problem"] == "storm_slab"
        assert campos["wn2_confianza"] == "media"
        assert campos["wn2_alert_storm_slab"] is True
        assert campos["wn2_alert_wind_strong"] is True
        assert campos["wn2_alert_heavy_snow"] is False
        assert campos["wn2_alert_wet_snow"] is False

    def test_campos_wn2_null_cuando_no_disponible(self):
        from agentes.salidas.almacenador import _construir_campos_subagentes

        tools_llamadas = self._tools_llamadas_con_wn2(False)
        campos = _construir_campos_subagentes(tools_llamadas, {})

        assert campos["wn2_avalanche_problem"] is None
        assert campos["wn2_confianza"] is None
        assert campos["wn2_alert_heavy_snow"] is None
        assert campos["wn2_alert_storm_slab"] is None

    def test_campos_wn2_null_sin_tool_llamada(self):
        """Si S3 no llamó la tool WN2, todos los campos quedan NULL."""
        from agentes.salidas.almacenador import _construir_campos_subagentes

        campos = _construir_campos_subagentes([], {})

        assert campos["wn2_avalanche_problem"] is None
        assert campos["wn2_confianza"] is None
