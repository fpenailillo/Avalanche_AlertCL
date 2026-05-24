"""
Tests FIX-PINN-WN2 (v25.2) — Fallback determinista WN2 → PINN.

Verifica que:
1. ejecutar_calcular_pinn con nieve_nueva_cm explícito reduce FS correctamente.
2. Sin nieve_nueva_cm (None) y USE_WEATHERNEXT2=true + nombre_ubicacion → el fallback
   consulta FuenteWeatherNext2.obtener_ventanas_6h y pasa el valor al Mohr-Coulomb.
3. Sin WN2 disponible (disponible=False) → el PINN continúa con FS estático.
4. SubagenteTopografico registra obtener_pronostico_wn2_ventanas en sus tools.
5. S1 registra la tool en _cargar_tools() y en _cargar_ejecutores().
"""

import os
import pytest
from unittest.mock import MagicMock, patch


# ─── Parámetros físicos representativos de La Parva Sector Alto ───────────────
PINN_BASE_KWARGS = {
    "gradiente_termico_C_100m": -0.6,
    "densidad_kg_m3": 280.0,
    "indice_metamorfismo": 0.55,
    "energia_fusion_J_kg": 95000.0,
    "pendiente_grados": 36.0,
}


class TestPINNSurcharge:
    """El parámetro nieve_nueva_cm reduce FS respecto al baseline estático."""

    def test_sin_nieve_nueva_fs_baseline(self):
        from agentes.subagentes.subagente_topografico.tools.tool_calcular_pinn import (
            ejecutar_calcular_pinn,
        )
        res = ejecutar_calcular_pinn(**PINN_BASE_KWARGS)
        fs = res["factor_seguridad_mohr_coulomb"]
        # Sin surcharge → FS ≈ 1.83 (constante histórico LP-Alto)
        assert fs > 1.5, f"FS esperado >1.5 sin surcharge, got {fs}"
        assert res["estado_manto"] == "ESTABLE"
        assert res["metricas_fisicas"]["nieve_nueva_cm"] is None

    def test_con_nieve_40cm_estado_inestable(self):
        from agentes.subagentes.subagente_topografico.tools.tool_calcular_pinn import (
            ejecutar_calcular_pinn,
        )
        res = ejecutar_calcular_pinn(**PINN_BASE_KWARGS, nieve_nueva_cm=40.0)
        # El FS numérico baja respecto al baseline estático (surcharge efectivo)
        res_base = ejecutar_calcular_pinn(**PINN_BASE_KWARGS)
        assert res["factor_seguridad_mohr_coulomb"] < res_base["factor_seguridad_mohr_coulomb"], (
            "FS con surcharge debe ser menor que sin surcharge"
        )
        # El estado del manto cambia a INESTABLE por el escalado de riesgo (SURCHARGE_NIEVE_EXTREMA)
        assert res["estado_manto"] != "ESTABLE", (
            f"estado_manto debe ser MARGINAL/INESTABLE/CRITICO con 40 cm, got {res['estado_manto']}"
        )
        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 40.0
        assert res["metricas_fisicas"]["peso_surcharge_N_m2"] > 0
        assert any("SURCHARGE" in a for a in res["alertas_pinn"])

    def test_surcharge_menor_que_sin_surcharge(self):
        from agentes.subagentes.subagente_topografico.tools.tool_calcular_pinn import (
            ejecutar_calcular_pinn,
        )
        fs_base = ejecutar_calcular_pinn(**PINN_BASE_KWARGS)["factor_seguridad_mohr_coulomb"]
        fs_30cm = ejecutar_calcular_pinn(**PINN_BASE_KWARGS, nieve_nueva_cm=30.0)["factor_seguridad_mohr_coulomb"]
        assert fs_30cm < fs_base, (
            f"FS con surcharge ({fs_30cm}) debe ser menor que sin surcharge ({fs_base})"
        )


class TestFallbackWN2Determinista:
    """Si nieve_nueva_cm no viene del LLM, el PINN consulta WN2 directamente."""

    def _wn2_result_con_nieve(self, nieve_cm: float = 35.0, via_p95: bool = False) -> dict:
        return {
            "disponible": True,
            "diario": {
                "nieve_24h_cm_p50_corr": 0.0 if via_p95 else nieve_cm,
                "nieve_24h_cm_p95_corr": nieve_cm,
                "nieve_3d_cm_p95_corr": None,
                "temp_p50_c": -8.0,
            },
            "ventanas": [],
        }

    def _wn2_result_solo_3d(self, nieve_3d_cm: float = 35.0) -> dict:
        """p50=0, p95=0 (sin precipitación el día del boletín), pero 3d tiene señal (post-tormenta)."""
        return {
            "disponible": True,
            "diario": {
                "nieve_24h_cm_p50_corr": 0.0,
                "nieve_24h_cm_p95_corr": 0.0,
                "nieve_3d_cm_p95_corr": nieve_3d_cm,
                "temp_p50_c": -8.0,
            },
            "ventanas": [],
        }

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_activa_surcharge(self):
        """Con USE_WEATHERNEXT2=true y nombre_ubicacion, el PINN consulta WN2 y usa el resultado."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = self._wn2_result_con_nieve(35.0)
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 35.0, (
            f"nieve_nueva_cm esperado 35.0, got {res['metricas_fisicas']['nieve_nueva_cm']}"
        )
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] in (
            "wn2_fallback_determinista_p50",
            "wn2_fallback_determinista_p95",
            "wn2_fallback_determinista_p95_3d",
        ), f"fuente inesperada: {res['metricas_fisicas']['fuente_nieve_nueva']}"
        assert res["estado_manto"] != "ESTABLE", (
            f"estado_manto debe ser != ESTABLE con 35 cm WN2, got {res['estado_manto']}"
        )

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_p50_cero_usa_p95(self):
        """Si p50=0 pero p95=35 (tormenta con ensemble disperso), el PINN usa p95."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = self._wn2_result_con_nieve(35.0, via_p95=True)
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 35.0, (
            f"Con p50=0 y p95=35, esperado 35.0, got {res['metricas_fisicas']['nieve_nueva_cm']}"
        )
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] == "wn2_fallback_determinista_p95"
        assert res["estado_manto"] != "ESTABLE"

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_sin_datos_mantiene_estatico(self):
        """Si WN2 retorna disponible=False, el PINN sigue con FS estático sin error."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = {"disponible": False}
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        assert res["metricas_fisicas"]["nieve_nueva_cm"] is None
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] is None
        assert res["estado_manto"] == "ESTABLE"

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_post_tormenta_usa_p95_3d(self):
        """FIX-WN2-3D: si p50=0 y p95=0 pero p95_3d=35 (tormenta 1-3 días antes), usa ventana 3d."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = self._wn2_result_solo_3d(35.0)
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 35.0, (
            f"Con p50=p95=0 y p95_3d=35, esperado 35.0, got {res['metricas_fisicas']['nieve_nueva_cm']}"
        )
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] == "wn2_fallback_determinista_p95_3d"
        assert res["estado_manto"] != "ESTABLE", (
            f"Post-tormenta con 35cm HN3d debe ser != ESTABLE, got {res['estado_manto']}"
        )

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_p50_ruido_usa_p95_3d(self):
        """FIX-WN2-THRESHOLD: p50=0.13 cm (ruido WN2 en día despejado) no bloquea el 3d."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        # Replica exacta de lo que devuelve WN2 para La Parva 2024-06-15:
        # día despejado post-tormenta — p50/p95 24h son ruido numérico del ensemble
        mock_wn2 = {
            "disponible": True,
            "diario": {
                "nieve_24h_cm_p50_corr": 0.13,   # ruido — no una señal de tormenta
                "nieve_24h_cm_p95_corr": 2.42,   # pequeño, < umbral 5 cm
                "nieve_3d_cm_p95_corr":  173.6,  # tormenta Jun 12-14 → señal real
                "temp_p50_c": -5.0,
            },
            "ventanas": [],
        }
        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = mock_wn2
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        # El umbral 5 cm filtra el ruido p50=0.13 y p95=2.42 → usa el 3d real
        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 173.6, (
            f"Umbral 5cm debe filtrar ruido p50=0.13 y usar 3d=173.6, got {res['metricas_fisicas']['nieve_nueva_cm']}"
        )
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] == "wn2_fallback_determinista_p95_3d"
        assert res["estado_manto"] != "ESTABLE", (
            f"Post-tormenta GT=5 (Jun 15 2024) debe ser != ESTABLE, got {res['estado_manto']}"
        )

    @patch.dict(os.environ, {"USE_WEATHERNEXT2": "true"})
    def test_fallback_wn2_llm_valor_pequeno_usa_p95_3d(self):
        """FIX-WN2-THRESHOLD: LLM pasa nieve_nueva_cm=4.3 (p95_24h extraído de WN2),
        el fallback lo detecta como < 5cm y lo sobreescribe con p95_3d=173.6."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        mock_wn2 = {
            "disponible": True,
            "diario": {
                "nieve_24h_cm_p50_corr": 0.13,
                "nieve_24h_cm_p95_corr": 2.42,
                "nieve_3d_cm_p95_corr":  173.6,
                "temp_p50_c": -5.0,
            },
            "ventanas": [],
        }
        mock_instancia = MagicMock()
        mock_instancia.obtener_ventanas_6h.return_value = mock_wn2
        mock_clase = MagicMock(return_value=mock_instancia)

        with patch.object(modulo, "_USE_WEATHERNEXT2", True), \
             patch(
                 "agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2.FuenteWeatherNext2",
                 mock_clase,
             ), \
             patch(
                 "agentes.datos.constantes_zonas.COORDENADAS_ZONAS",
                 {"La Parva Sector Alto": (-33.55, -70.29)},
             ), \
             patch(
                 "agentes.datos.constantes_zonas.obtener_elevacion_referencia",
                 return_value=3200,
             ), \
             patch(
                 "agentes.datos.consultor_bigquery.obtener_fecha_referencia_global",
                 return_value=None,
             ):
            # El LLM extrajo p95_24h y lo pasó como nieve_nueva_cm=4.3
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nieve_nueva_cm=4.3,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        # 4.3 < 5 → fallback activa; 3d=173.6 >= 5 → sobreescribe
        assert res["metricas_fisicas"]["nieve_nueva_cm"] == 173.6, (
            f"LLM pasó 4.3 (<5 cm umbral), fallback debe sobreescribir con 3d=173.6, "
            f"got {res['metricas_fisicas']['nieve_nueva_cm']}"
        )
        assert res["metricas_fisicas"]["fuente_nieve_nueva"] == "wn2_fallback_determinista_p95_3d"
        assert res["estado_manto"] != "ESTABLE"

    def test_fallback_sin_wn2_env_no_consulta(self):
        """Con USE_WEATHERNEXT2=false, el fallback NO llega a instanciar FuenteWeatherNext2."""
        from agentes.subagentes.subagente_topografico.tools import tool_calcular_pinn as modulo

        with patch.object(modulo, "_USE_WEATHERNEXT2", False):
            res = modulo.ejecutar_calcular_pinn(
                **PINN_BASE_KWARGS,
                nombre_ubicacion="La Parva Sector Alto",
                fecha_objetivo="2024-06-15",
            )

        assert res["metricas_fisicas"]["nieve_nueva_cm"] is None
        assert res["estado_manto"] == "ESTABLE"


class TestRegistroToolsS1:
    """S1 debe registrar obtener_pronostico_wn2_ventanas en tools y ejecutores."""

    def test_tool_wn2_en_lista_tools(self):
        from agentes.subagentes.subagente_topografico.agente import SubagenteTopografico
        s1 = SubagenteTopografico()
        nombres_tools = [t["name"] for t in s1._tools_definicion]
        assert "obtener_pronostico_wn2_ventanas" in nombres_tools, (
            f"TOOL_PRONOSTICO_WN2_VENTANAS no registrada en S1. Tools actuales: {nombres_tools}"
        )

    def test_ejecutor_wn2_en_ejecutores(self):
        from agentes.subagentes.subagente_topografico.agente import SubagenteTopografico
        s1 = SubagenteTopografico()
        assert "obtener_pronostico_wn2_ventanas" in s1._tools_ejecutores, (
            "ejecutar_obtener_pronostico_wn2_ventanas no registrado en _cargar_ejecutores() de S1"
        )

    def test_calcular_pinn_acepta_nombre_ubicacion(self):
        """El schema de calcular_pinn incluye nombre_ubicacion y fecha_objetivo."""
        from agentes.subagentes.subagente_topografico.tools.tool_calcular_pinn import TOOL_CALCULAR_PINN
        props = TOOL_CALCULAR_PINN["input_schema"]["properties"]
        assert "nombre_ubicacion" in props
        assert "fecha_objetivo" in props
