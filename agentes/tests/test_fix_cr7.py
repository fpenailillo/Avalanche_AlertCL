"""
Tests para los fixes CR-7 (v8.0) y FIX-CR7A-REFACTOR (v20.0).

CR-7a → FIX-CR7A-REFACTOR (v20.0): compuerta condicional en Andes Chile.
  Antes (v9.0): bloqueo absoluto condiciones_meteo_disponibles → False.
  Ahora (v20.0): gate basado en señales de calma (factor neutro + vc=0 +
  p72h<5mm + viento<30 km/h + dias_consecutivos_nivel_bajo>=2).
  Sin calma confirmada → mismo comportamiento que el bloqueo absoluto.
  Con calma confirmada → EAWS Paso 1 habilitado (habilita nivel 1 en Andes).
CR-7b: vc inflado (dias_alto_riesgo) ya no bloquea FIX-GEO cap gracias a FIX-CR7C.
CR-7c: tamano explícito > 3 capado en Andes Chile con factor neutro,
       independiente de ventanas_criticas.
"""

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

_LA_PARVA = "La Parva Sector Alto"
_INTERLAKEN = "Interlaken"


class TestCR7a:
    def test_false_no_activa_eaws_paso1(self):
        """condiciones_meteo_disponibles=False no activa EAWS Paso 1 — va por la matriz.
        Con FIX-CR17A la matriz puede devolver nivel 1 en condiciones calmas; lo que
        importa es que el path sea la matriz, no el Paso 1."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["fuente_tamano"] != "eaws_paso1_sin_problema_confirmado", (
            "Con condiciones_meteo_disponibles=False, EAWS Paso 1 no debe activarse"
        )

    def test_cr14_bloquea_eaws_paso1_alpes(self):
        """CR-14 (v14.0): condiciones_meteo_disponibles=True en Alpes NO activa EAWS Paso 1.
        Sin Sclass2/pwl_100 no se puede confirmar nivel 1 → matriz estándar → nivel >= 2."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            nombre_ubicacion=_INTERLAKEN,
        )
        assert r["nivel_eaws_24h"] >= 2, (
            "CR-14: Alpes sin datos de manto nival no puede emitir nivel 1 via EAWS Paso 1"
        )
        assert r["factores_eaws"]["fuente_tamano"] != "eaws_paso1_sin_problema_confirmado"

    def test_true_bloqueado_en_andes_sin_calma(self):
        """FIX-CR7A-REFACTOR (v20.0): condiciones_meteo_disponibles=True en Andes Chile
        sin calma confirmada (dias_bajo=0) → gate bloquea → EAWS Paso 1 no activa."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            dias_consecutivos_nivel_bajo=0,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["fuente_tamano"] != "eaws_paso1_sin_problema_confirmado", (
            "Andes sin calma confirmada debe bloquear EAWS Paso 1"
        )

    def test_true_habilita_paso1_con_calma_confirmada(self):
        """FIX-CR7A-REFACTOR (v20.0): con calma confirmada en Andes Chile,
        condiciones_meteo_disponibles=True habilita EAWS Paso 1 → nivel 1."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            precipitacion_72h_corregida_mm=1.0,
            viento_kmh=20.0,
            dias_consecutivos_nivel_bajo=3,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["nivel_eaws_24h"] == 1, "Andes con calma confirmada → EAWS Paso 1 → nivel 1"
        assert r["factores_eaws"]["fuente_tamano"] == "eaws_paso1_sin_problema_confirmado"

    def test_none_no_activa_eaws_paso1(self):
        """Compatibilidad retroactiva: condiciones_meteo_disponibles=None (default)
        nunca activa EAWS Paso 1 — va por la matriz."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=None,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["fuente_tamano"] != "eaws_paso1_sin_problema_confirmado"


class TestCR7b:
    def test_vc0_cap_fijgeo_aplica(self):
        """CR-7b fix: con vc=0 (num_ventanas_criticas correcto) y tamano explícito=5
        en Andes Chile con factor neutro, FIX-GEO cap aplica → tamano=3."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            tamano_eaws="5",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["tamano"] == 3
        assert "cap" in r["factores_eaws"]["fuente_tamano"]

    def test_vc4_cr7c_bloquea_bypass(self):
        """CR-7b bug scenario: vc=4 (dias_alto_riesgo mal extraído) bloquea FIX-GEO
        normal (condición vc<2 falla), pero FIX-CR7C aún capa tamano explícito."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            tamano_eaws="5",
            ventanas_criticas_detectadas=4,  # bug: dias_alto_riesgo
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["tamano"] == 3, (
            "FIX-CR7C debe capear tamano explícito en Andes aunque vc=4"
        )
        assert "cr7c" in r["factores_eaws"]["fuente_tamano"]


class TestCR7c:
    def test_explicito_capado_andes_factor_estable(self):
        """CR-7c: tamano explícito=4 con factor ESTABLE en Andes Chile → cap a 3,
        independiente de ventanas_criticas."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            tamano_eaws="4",
            ventanas_criticas_detectadas=3,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion="La Parva Sector Bajo",
        )
        assert r["factores_eaws"]["tamano"] == 3
        assert r["factores_eaws"]["fuente_tamano"] == "explicito→cap_cr7c"

    def test_explicito_capado_andes_factor_ciclo_diurno(self):
        """CR-7c: CICLO_DIURNO_NORMAL también es factor neutro → cap aplica."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="fair",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            tamano_eaws="5",
            ventanas_criticas_detectadas=5,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["tamano"] == 3
        assert "cr7c" in r["factores_eaws"]["fuente_tamano"]

    def test_explicito_no_capado_alpes(self):
        """CR-7c: mismo escenario en Alpes (Interlaken) → sin cap, tamano=4."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            tamano_eaws="4",
            ventanas_criticas_detectadas=3,
            condiciones_meteo_disponibles=False,
            nombre_ubicacion=_INTERLAKEN,
        )
        assert r["factores_eaws"]["tamano"] == 4
        assert "cr7c" not in r["factores_eaws"]["fuente_tamano"]

    def test_factor_activo_no_capa(self):
        """CR-7c no aplica cuando factor meteorológico es activo (NEVADA_RECIENTE).
        El tamano explícito alto es válido con precipitación real."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            tamano_eaws="4",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["tamano"] == 4
        assert "cr7c" not in r["factores_eaws"]["fuente_tamano"]


class TestCR14:
    def test_alpes_paso1_bloqueado_estable(self):
        """CR-14: factor=ESTABLE + datos_meteo=True en Alpes → matriz, nivel >= 2."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            nombre_ubicacion=_INTERLAKEN,
        )
        assert r["nivel_eaws_24h"] >= 2, "CR-14 bloquea EAWS Paso 1 en Alpes sin datos de manto"

    def test_alpes_paso1_bloqueado_ciclo_diurno(self):
        """CR-14: factor=CICLO_DIURNO_NORMAL en Alpes también bloqueado → nivel >= 2."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            nombre_ubicacion="Matterhorn Zermatt",
        )
        assert r["nivel_eaws_24h"] >= 2

    def test_andes_paso1_no_afectado_por_cr14(self):
        """CR-14 solo aplica a Alpes suizos — La Parva usa FIX-CR7A-REFACTOR (v20.0).
        Sin calma confirmada (dias_bajo=0), el gate bloquea EAWS Paso 1 igualmente."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="ESTABLE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            dias_consecutivos_nivel_bajo=0,
            nombre_ubicacion=_LA_PARVA,
        )
        assert r["factores_eaws"]["fuente_tamano"] != "eaws_paso1_sin_problema_confirmado"

    def test_alpes_factor_activo_no_afectado(self):
        """CR-14 solo bloquea el Paso 1 — factor activo en Alpes usa la matriz normalmente."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            factor_meteorologico="NEVADA_RECIENTE",
            ventanas_criticas_detectadas=0,
            condiciones_meteo_disponibles=True,
            nombre_ubicacion=_INTERLAKEN,
        )
        assert "nivel_eaws_24h" in r  # no crashea, sigue la ruta de matriz normal
