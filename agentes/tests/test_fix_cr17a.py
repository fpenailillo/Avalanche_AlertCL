"""
Tests para FIX-CR17A-ATENUACION (v7.0) y separación CICLO_DIURNO_NORMAL/ESTABLE.

FIX-CR17A-ATENUACION (v7.0): sustituye cap duro de v17.0 por atenuación de 1 paso.
  Antes (v17.0): cualquier poor/very_poor en Andes sin trigger → forzado a 'fair' (techo nivel 2).
  Ahora (v7.0):
    - very_poor → poor (siempre, 1 paso)
    - poor → fair solo con ESTABLE + dias_consecutivos_nivel_bajo >= 3
    - poor + CICLO_DIURNO_NORMAL → mantener poor (habilita nivel ≥ 3 vía matriz)

FIX-CR17A-ATENUACION Fix #3: CICLO_DIURNO_NORMAL separado de ESTABLE en calma sostenida.
  Antes: ambos factores activaban cap en 'fair' con dias_bajo >= 4.
  Ahora: solo ESTABLE/"" activa calma sostenida — ciclo térmico activo no es calma real.
"""

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

_LA_PARVA = "La Parva Sector Alto"
_LA_PARVA_MEDIO = "La Parva Sector Medio"


class TestCR17AAtenuacionVeryPoor:
    def test_very_poor_atenua_a_poor_no_a_fair(self):
        """FIX-CR17A-ATENUACION: very_poor en Andes calmo → poor (1 paso), NO fair."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="very_poor",
            estabilidad_satelital="very_poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=0,
        )
        assert r["factores_eaws"]["estabilidad"] == "poor", (
            "very_poor en Andes sin trigger debe atenuar a poor, no a fair"
        )

    def test_very_poor_ciclo_diurno_atenua_a_poor(self):
        """FIX-CR17A-ATENUACION: very_poor + CICLO_DIURNO_NORMAL → poor."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="very_poor",
            estabilidad_satelital="very_poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=2,
        )
        assert r["factores_eaws"]["estabilidad"] == "poor"


class TestCR17AAtenuacionPoor:
    def test_poor_ciclo_diurno_mantiene_poor(self):
        """FIX-CR17A-ATENUACION: poor + CICLO_DIURNO_NORMAL en Andes → mantener poor.
        Antes: cap duro a fair → nivel ≤ 2. Ahora: poor permite nivel ≥ 3 vía matriz."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=0,
        )
        assert r["factores_eaws"]["estabilidad"] == "poor", (
            "poor + CICLO_DIURNO_NORMAL no debe ser capado a fair"
        )

    def test_poor_estable_sin_calma_suficiente_mantiene_poor(self):
        """poor + ESTABLE con dias_bajo=2 < 3 → mantener poor (calma insuficiente)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=2,
        )
        assert r["factores_eaws"]["estabilidad"] == "poor", (
            "poor + ESTABLE con solo 2 días no debe atenuar a fair (umbral es 3)"
        )

    def test_poor_estable_calma_confirmada_atenua_a_fair(self):
        """poor + ESTABLE + dias_bajo >= 3 → atenuar a fair (calma sostenida confirmada)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=3,
        )
        assert r["factores_eaws"]["estabilidad"] == "fair", (
            "poor + ESTABLE + 3 días debe atenuar a fair"
        )


class TestNivel3Habilitado:
    def test_poor_some_tamano3_ciclo_diurno_produce_nivel3(self):
        """Caso principal H4: poor × some × 3 + CICLO_DIURNO_NORMAL → nivel 3.
        Antes del fix: CR17A capaba poor a fair → matrix(fair×some×3) = nivel 2.
        Después: poor se mantiene → matrix(poor×some×3) = nivel 3."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            frecuencia_topografica="some",
            tamano_eaws="3",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=0,
        )
        assert r["nivel_eaws_24h_raw"] == 3, (
            f"poor×some×3 con CICLO_DIURNO_NORMAL debe producir nivel 3 "
            f"(obtenido: {r['nivel_eaws_24h_raw']}, estabilidad: {r['factores_eaws']['estabilidad']})"
        )

    def test_poor_some_tamano3_ciclo_diurno_dias_bajo4_produce_nivel3(self):
        """Fix #3: poor + CICLO_DIURNO_NORMAL + dias_bajo=4 → nivel 3.
        Antes: calma sostenida capaba a fair porque CICLO_DIURNO_NORMAL ∈ _FACTORES_NEUTROS.
        Después: calma sostenida solo activa con ESTABLE."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            frecuencia_topografica="some",
            tamano_eaws="3",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=4,
        )
        assert r["nivel_eaws_24h_raw"] == 3, (
            f"poor×some×3 con CICLO_DIURNO_NORMAL (dias_bajo=4) debe producir nivel 3 "
            f"(obtenido: {r['nivel_eaws_24h_raw']}, estabilidad: {r['factores_eaws']['estabilidad']})"
        )

    def test_poor_many_tamano2_ciclo_diurno_produce_nivel_minimo3(self):
        """poor × many × 2 + CICLO_DIURNO_NORMAL → nivel 3 (matrix: poor×many×2 = 3)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            frecuencia_topografica="many",
            tamano_eaws="2",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA_MEDIO,
            dias_consecutivos_nivel_bajo=1,
        )
        assert r["nivel_eaws_24h_raw"] >= 3, (
            f"poor×many×2 con CICLO_DIURNO_NORMAL debe producir nivel ≥ 3 "
            f"(obtenido: {r['nivel_eaws_24h_raw']})"
        )


class TestCalmaAbsolutaMantieneComportamientoAnterior:
    def test_estable_4dias_cap_a_fair(self):
        """Calma sostenida con ESTABLE ≥ 4 días sigue capeando a fair (sin regresión)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="ESTABLE",
            frecuencia_topografica="some",
            tamano_eaws="3",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=4,
        )
        assert r["factores_eaws"]["estabilidad"] == "fair", (
            "ESTABLE + 4 días consecutivos debe seguir capeando a fair"
        )

    def test_ciclo_diurno_4dias_no_capa(self):
        """Fix #3: CICLO_DIURNO_NORMAL + dias_bajo=4 NO aplica calma sostenida.
        Cambio de comportamiento vs v17.0 donde ambos factores neutros capaban."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            frecuencia_topografica="some",
            tamano_eaws="3",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
            dias_consecutivos_nivel_bajo=4,
        )
        assert r["factores_eaws"]["estabilidad"] != "fair", (
            "CICLO_DIURNO_NORMAL con dias_bajo=4 NO debe activar calma sostenida"
        )


class TestAlpesSinCambio:
    def test_alpes_no_afectado_por_cr17a_atenuacion(self):
        """FIX-CR17A-ATENUACION solo aplica a Andes Chile — Alpes sin cambio."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            frecuencia_topografica="some",
            tamano_eaws="3",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion="Interlaken",
            dias_consecutivos_nivel_bajo=0,
        )
        # En Alpes, CR17A no aplica (guard de región). La estabilidad base no se modifica.
        assert r["factores_eaws"]["estabilidad"] == "poor"
        # La matriz poor×some×3 = 3; calibrador shift +0.7 → round(3.7)=4
        assert r["nivel_eaws_24h"] >= 3
