"""
Tests para los fixes CR-10 (v10.1): calibración ERA5 regional.

CR-10A: precipitacion_efectiva usa precipitacion_72h_mm/3 cuando precip_actual=0.
CR-10B: umbral viento reducido a 7 m/s en Alpes (ERA5 subestima vientos de cresta).
CR-10C: revertido en v10.1 (sobreimpulso: sube nivel 2→3 en casos con factor activo+S2 poor).
"""

import pytest

from agentes.subagentes.subagente_meteorologico.tools.tool_ventanas_criticas import (
    ejecutar_detectar_ventanas_criticas,
)
from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

_INTERLAKEN  = "Interlaken"
_LA_PARVA    = "La Parva Sector Alto"


# ─── CR-10A: precipitación efectiva via 72h ──────────────────────────────────

class TestCR10A:
    def test_precip_actual_cero_usa_72h_alpes(self):
        """CR-10A: precip_actual=0 pero precip_72h=30mm en Alpes →
        precip_efectiva=10mm > umbral 2mm → NEVADA_MAS_VIENTO activa."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-2.0,
            velocidad_viento_actual_ms=12.0,
            precipitacion_actual_mm=0.0,
            precipitacion_72h_mm=30.0,
            nombre_ubicacion=_INTERLAKEN,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert "NEVADA_MAS_VIENTO" in tipos, (
            "Con precip_72h=30mm en Alpes, precip_efectiva=10mm > 2mm → NEVADA_MAS_VIENTO debe activar"
        )

    def test_precip_actual_cero_usa_72h_andes(self):
        """CR-10A: mismo escenario en Andes — precip_72h=30mm → daily=10mm > 5mm → activa."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-2.0,
            velocidad_viento_actual_ms=12.0,
            precipitacion_actual_mm=0.0,
            precipitacion_72h_mm=30.0,
            nombre_ubicacion=_LA_PARVA,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert "NEVADA_MAS_VIENTO" in tipos

    def test_precip_72h_baja_no_activa_andes(self):
        """CR-10A: precip_72h=9mm en Andes → daily=3mm < 5mm → sin nevada en Andes."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-3.0,
            velocidad_viento_actual_ms=12.0,
            precipitacion_actual_mm=0.0,
            precipitacion_72h_mm=9.0,
            nombre_ubicacion=_LA_PARVA,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert "NEVADA_MAS_VIENTO" not in tipos

    def test_precip_72h_baja_activa_alpes(self):
        """CR-10A: precip_72h=9mm en Alpes → daily=3mm > 2mm → NEVADA activa en Alpes."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-3.0,
            velocidad_viento_actual_ms=12.0,
            precipitacion_actual_mm=0.0,
            precipitacion_72h_mm=9.0,
            nombre_ubicacion=_INTERLAKEN,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert "NEVADA_MAS_VIENTO" in tipos

    def test_fusion_activa_con_carga_alpes_umbral_reducido(self):
        """CR-10A: ciclo_fusion + precip_72h=6mm en Alpes → hay_carga=True (umbral 5mm) →
        FUSION_ACTIVA_CON_CARGA en factor meteorológico."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=3.0,
            velocidad_viento_actual_ms=2.0,
            precipitacion_actual_mm=0.0,
            ciclo_fusion_congelacion=True,
            precipitacion_72h_mm=6.0,
            nombre_ubicacion=_INTERLAKEN,
        )
        assert "FUSION_ACTIVA_CON_CARGA" in r["factor_meteorologico_eaws"]

    def test_fusion_con_carga_andes_umbral_10(self):
        """CR-10A: ciclo_fusion + precip_72h=6mm en Andes → hay_carga=False (umbral 10mm) →
        CICLO_DIURNO_NORMAL (sin carga suficiente)."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=3.0,
            velocidad_viento_actual_ms=2.0,
            precipitacion_actual_mm=0.0,
            ciclo_fusion_congelacion=True,
            precipitacion_72h_mm=6.0,
            nombre_ubicacion=_LA_PARVA,
        )
        assert "CICLO_DIURNO_NORMAL" in r["factor_meteorologico_eaws"]
        assert "FUSION_ACTIVA_CON_CARGA" not in r["factor_meteorologico_eaws"]


# ─── CR-10B: umbral viento reducido en Alpes ─────────────────────────────────

class TestCR10B:
    def test_viento_9ms_activa_redistribucion_alpes(self):
        """CR-10B/FIX-BUG009: 9 m/s en Alpes (>8 m/s umbral redistribución) → VIENTO_FUERTE_REDISTRIBUCION activa."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-5.0,
            velocidad_viento_actual_ms=9.0,
            precipitacion_actual_mm=0.0,
            nombre_ubicacion=_INTERLAKEN,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert any("VIENTO" in t for t in tipos), (
            "9 m/s en Alpes debe activar VIENTO_FUERTE_REDISTRIBUCION (umbral BUG009: 8 m/s)"
        )

    def test_viento_8ms_no_activa_andes(self):
        """CR-10B: 8 m/s en Andes (< 10 m/s umbral) → sin ventana de viento."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-5.0,
            velocidad_viento_actual_ms=8.0,
            precipitacion_actual_mm=0.0,
            nombre_ubicacion=_LA_PARVA,
        )
        tipos = [v["tipo"] for v in r["ventanas_criticas"]]
        assert not any("VIENTO" in t for t in tipos)

    def test_viento_9ms_alpes_genera_ventana_critica(self):
        """CR-10B: Matterhorn 2024-04-01 simulado — 9 m/s en Alpes → viento activa →
        num_ventanas_criticas ≥ 1 (antes era 0 con umbral 10 m/s)."""
        r = ejecutar_detectar_ventanas_criticas(
            temperatura_actual_C=-6.0,
            velocidad_viento_actual_ms=9.0,
            precipitacion_actual_mm=0.0,
            precipitacion_72h_mm=0.0,
            ciclo_fusion_congelacion=True,
            nombre_ubicacion="Matterhorn Zermatt",
        )
        assert r["num_ventanas_criticas"] >= 1, (
            "9 m/s en Alpes debe generar ≥1 ventana crítica (umbral CR-10B = 7 m/s)"
        )

