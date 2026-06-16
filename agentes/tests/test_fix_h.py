"""
Tests para FIX-H (v7.0): default estabilidad_satelital por región cuando ViT retorna sin_datos.

En Andes Chile: el satélite ausente NO eleva el piso → se confía en el PINN topográfico
  (FIX-SAT-DEFAULT-NO-ELEVA v26.1; antes default 'fair', que inflaba good→fair y subía
  ~21 días calmos de nivel 1 a nivel 2 — el error GT=1→AI=2 dominante en H4).
En Alpes suizos: default 'poor' (ViT fuera de dominio → incertidumbre alta, conservador).
"""

import pytest

from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
    _determinar_estabilidad_dominante,
)


class TestFixH:
    def test_andes_sin_datos_respeta_topo_fair(self):
        """Andes sin satélite: la dominante sigue el PINN topográfico ('fair')."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="fair",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        # Sin señal satelital, idx_base = idx_topo → 'fair'
        assert estabilidad == "fair"

    def test_andes_good_sin_datos_no_eleva(self):
        """FIX-SAT-DEFAULT-NO-ELEVA: Andes con PINN ESTABLE (good) y satélite ausente
        debe quedar 'good' (no 'fair'). Es la causa raíz del error GT=1→AI=2 en H4."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        assert estabilidad == "good"

    def test_andes_good_sin_datos_calmo_da_nivel_1(self):
        """Día calmo en La Parva con PINN ESTABLE y sin satélite → nivel EAWS 1
        (antes nivel 2 por el piso 'fair' espurio)."""
        r = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            nombre_ubicacion="La Parva Sector Alto",
        )
        assert r["nivel_eaws_24h"] == 1

    def test_andes_good_con_factor_activo_sigue_elevando(self):
        """El fix no anula la sensibilidad: con un factor meteorológico activo el nivel
        sube aunque el PINN sea ESTABLE y no haya satélite."""
        r_calmo = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            nombre_ubicacion="La Parva Sector Alto",
        )
        r_activo = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="NEVADA_RECIENTE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        assert r_activo["nivel_eaws_24h"] >= r_calmo["nivel_eaws_24h"]

    def test_alpes_sin_datos_default_poor(self):
        """FIX-H: Interlaken sin estabilidad satelital → usa default 'poor' (Alpes)."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        # Con topo='good' e idx_sat='poor' (default Alpes), la dominante es 'poor'
        assert estabilidad == "poor"

    def test_alpes_con_datos_no_afectado(self):
        """FIX-H: con estabilidad satelital explícita, FIX-H no interfiere."""
        estabilidad = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital="good",
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        assert estabilidad == "good"

    def test_ubicacion_desconocida_default_andes(self):
        """FIX-H: sin nombre_ubicacion o no mapeada → default Andes ('fair')."""
        e_sin_nombre = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
        )
        e_no_mapeada = _determinar_estabilidad_dominante(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Portillo",
        )
        # ambos deben usar 'fair' como default (andes_chile)
        assert e_sin_nombre == e_no_mapeada

    def test_alpes_default_poor_eleva_nivel(self):
        """FIX-H: en Alpes, default 'poor' (en lugar de 'fair') eleva el nivel final."""
        r_alpes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="Interlaken",
        )
        r_andes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="good",
            estabilidad_satelital=None,
            factor_meteorologico="ESTABLE",
            nombre_ubicacion="La Parva Sector Alto",
        )
        # El nivel Alpes debe ser ≥ nivel Andes (default más conservador)
        assert r_alpes["nivel_eaws_24h"] >= r_andes["nivel_eaws_24h"]

    def test_h4_andes_sin_cambio_retrocompat(self):
        """FIX-H: la llamada sin nombre_ubicacion produce el mismo resultado que antes."""
        r_sin = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
        )
        r_andes = ejecutar_clasificar_riesgo_eaws_integrado(
            estabilidad_topografica="poor",
            estabilidad_satelital=None,
            factor_meteorologico="CICLO_DIURNO_NORMAL",
            nombre_ubicacion="La Parva Sector Alto",
        )
        assert r_sin["nivel_eaws_24h"] == r_andes["nivel_eaws_24h"]
