"""
Tests de tool_clasificar_problema_eaws: los 5 problemas típicos EAWS y la cota.

Caso de referencia — La Parva / Farellones, sábado 25-jul-2026: llovió con cota
de nieve alta (~3.000 m). El sistema publicó `new_snow` en los tres sectores
porque el tipo de precipitación se inferría de la temperatura del aire.

Datos reales de ese día (clima.pronostico_horas, deduplicados):
    Sector Bajo  (2.700 m): 11 h lluvia / 4,2 mm  +  7 h nieve / 8,2 mm
    Sector Alto  (3.600 m):  0 h lluvia          + 19 h nieve / 12,2 mm
    Lagunillas   (2.500 m): 22 h lluvia / 19,8 mm +  1 h nieve
    V. de las Arenas (2.500 m): 0 h lluvia       + 25 h nieve / 26,5 mm
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agentes.datos.precipitacion import MIN_HORAS_LLUVIA, MIN_MM_LLUVIA
from agentes.subagentes.subagente_integrador.tools.tool_clasificar_problema_eaws import (
    clasificar_problemas,
    interpolar_cota,
)


def _precip(horas_lluvia=0, mm_lluvia=0.0, horas_nieve=0, mm_nieve=0.0,
            bulbo_max=None, mm_total=None, tipo_observado=None):
    return {
        "disponible": True,
        "tipo_observado": (
            tipo_observado if tipo_observado is not None
            else bool(horas_lluvia or horas_nieve)
        ),
        "horas_lluvia": horas_lluvia,
        "horas_nieve": horas_nieve,
        "mm_lluvia": mm_lluvia,
        "mm_nieve": mm_nieve,
        "mm_total": mm_total if mm_total is not None else mm_lluvia + mm_nieve,
        "bulbo_humedo_max_c": bulbo_max,
        # Mismo criterio que precipitacion.resumir_horas: persistencia y monto
        "hay_lluvia_sobre_nieve": (
            horas_lluvia >= MIN_HORAS_LLUVIA and mm_lluvia >= MIN_MM_LLUVIA
        ),
    }


class TestCaso25Jul:
    def test_sector_bajo_es_nieve_humeda(self):
        """11 h de lluvia sobre el manto: el problema es nieve húmeda, no new_snow."""
        r = clasificar_problemas(
            precipitacion=_precip(horas_lluvia=11, mm_lluvia=4.2, horas_nieve=7, mm_nieve=8.2),
            wn2={"nieve_24h_p50": 12.0, "heavy_snow": True},
        )
        assert r["problema_dominante"] == "wet_snow"
        assert r["confianza"] == "alta"
        assert "new_snow" in r["problemas_secundarios"]

    def test_sector_alto_sigue_siendo_nieve_reciente(self):
        """Sin lluvia arriba: no debe haber regresión, el problema sigue siendo new_snow."""
        r = clasificar_problemas(
            precipitacion=_precip(horas_nieve=19, mm_nieve=12.2),
            wn2={"nieve_24h_p50": 14.0, "heavy_snow": True},
        )
        assert r["problema_dominante"] == "new_snow"
        assert "wet_snow" not in r["problemas_secundarios"]

    def test_sector_alto_no_cae_por_pico_de_bulbo_humedo(self):
        """
        Regresión: el 25-jul el Sector Alto tuvo 19 h de SNOW y un máximo de
        bulbo húmedo de 1,7 °C en otra hora del día. Ese pico no debe convertir
        la nevada en nieve húmeda: el tipo observado manda sobre la inferencia.
        """
        r = clasificar_problemas(
            precipitacion=_precip(horas_nieve=19, mm_nieve=12.2, bulbo_max=1.7),
            wn2={"nieve_24h_p50": 41.0, "heavy_snow": True},
        )
        assert r["problema_dominante"] == "new_snow"

    def test_lagunillas_lluvia_casi_pura(self):
        r = clasificar_problemas(
            precipitacion=_precip(horas_lluvia=22, mm_lluvia=19.8, horas_nieve=1, mm_nieve=0.2),
        )
        assert r["problema_dominante"] == "wet_snow"

    def test_valle_de_las_arenas_no_cambia(self):
        """Todo nieve y sin lluvia: no debe aparecer nieve húmeda."""
        r = clasificar_problemas(
            precipitacion=_precip(horas_nieve=25, mm_nieve=26.5),
            wn2={"nieve_24h_p50": 67.0, "heavy_snow": True},
        )
        assert r["problema_dominante"] == "new_snow"


class TestProblemasIndividuales:
    def test_nieve_venteada_por_viento_con_nieve(self):
        r = clasificar_problemas(
            precipitacion=_precip(horas_nieve=5, mm_nieve=4.0),
            wn2={"nieve_24h_p50": 8.0, "viento_100m_ms": 14.0},
            exposicion_zona="SE",
        )
        assert r["problema_dominante"] == "wind_slab"
        assert "sotavento" in " ".join(r["evidencia"])

    def test_viento_sin_nieve_no_forma_placa(self):
        r = clasificar_problemas(
            precipitacion=_precip(),
            wn2={"nieve_24h_p50": 0.0, "viento_100m_ms": 18.0},
        )
        assert r["problema_dominante"] == "no_distinct"

    def test_capa_debil_persistente_es_proxy_y_no_domina(self):
        """Compitiendo con una señal sólida, el proxy queda como secundario."""
        r = clasificar_problemas(
            precipitacion=_precip(horas_lluvia=4, mm_lluvia=3.0),
            wn2={"prob_problem": "persistent_weak_layer"},
        )
        assert r["problema_dominante"] == "wet_snow"
        assert "persistent_weak_layer" in r["problemas_secundarios"]

    def test_capa_debil_persistente_sola_domina_con_confianza_baja(self):
        r = clasificar_problemas(wn2={"prob_problem": "persistent_weak_layer"})
        assert r["problema_dominante"] == "persistent_weak_layer"
        assert r["confianza"] == "baja"

    def test_nieve_deslizante_requiere_manto_humedo_y_pendiente(self):
        r = clasificar_problemas(
            precipitacion=_precip(),
            manto={"humedad_activa": True, "sar_delta_baseline": -4.2, "manto_frio": False},
            topografia={"pendiente_media_inicio": 38.0},
            wn2={"nieve_24h_p50": 0.0},
        )
        assert "gliding_snow" in (
            [r["problema_dominante"]] + r["problemas_secundarios"]
        )

    def test_nieve_deslizante_no_aplica_con_nieve_nueva(self):
        """Con carga reciente el problema es la nieve nueva, no la reptación."""
        r = clasificar_problemas(
            precipitacion=_precip(horas_nieve=6, mm_nieve=9.0),
            manto={"humedad_activa": True, "manto_frio": False},
            topografia={"pendiente_media_inicio": 38.0},
            wn2={"nieve_24h_p50": 25.0},
        )
        assert r["problema_dominante"] == "new_snow"
        assert "gliding_snow" not in r["problemas_secundarios"]

    def test_nieve_humeda_por_fusion_sin_precipitacion(self):
        r = clasificar_problemas(
            precipitacion=_precip(),
            manto={"humedad_activa": True, "sar_delta_baseline": -5.0, "dias_lst_positivo": 3},
        )
        assert r["problema_dominante"] == "wet_snow"

    def test_llovizna_no_dispara_nieve_humeda(self):
        """
        5 h de lluvia sumando 1 mm no humedecen el manto. Sin este umbral, 96 de
        198 disparos del rango 24-28 jul quedaban por debajo de 3 mm.
        """
        r = clasificar_problemas(precipitacion=_precip(horas_lluvia=5, mm_lluvia=1.0))
        assert r["problema_dominante"] != "wet_snow"

    def test_sin_señales(self):
        r = clasificar_problemas()
        assert r["problema_dominante"] == "no_distinct"
        assert r["problemas_secundarios"] == []


class TestTransicionLluviaNieve:
    def test_bulbo_humedo_sobre_umbral_con_precipitacion(self):
        r = clasificar_problemas(precipitacion=_precip(bulbo_max=1.2, mm_total=3.0))
        assert r["problema_dominante"] == "wet_snow"
        assert r["confianza"] == "media"

    def test_bulbo_humedo_bajo_umbral(self):
        r = clasificar_problemas(precipitacion=_precip(bulbo_max=0.4, mm_total=3.0))
        assert r["problema_dominante"] != "wet_snow"

    def test_bulbo_humedo_alto_sin_precipitacion_no_es_problema(self):
        r = clasificar_problemas(precipitacion=_precip(bulbo_max=3.0, mm_total=0.0))
        assert r["problema_dominante"] == "no_distinct"


class TestCotaDeNieve:
    def test_caso_la_parva_25_jul(self):
        """Lluvia a 2.700 m y nieve a 3.000 m → cota entre ambos."""
        cota = interpolar_cota([(2700, True), (3000, False), (3600, False)])
        assert cota == 2850

    def test_lluvia_hasta_el_sector_mas_alto(self):
        assert interpolar_cota([(2700, True), (3600, True)]) == 3600

    def test_solo_nieve_no_hay_cota_que_reportar(self):
        """Nevó en todo el rango: la transición queda fuera del terreno observado."""
        assert interpolar_cota([(2700, False), (3600, False)]) is None

    def test_fallback_por_bulbo_humedo(self):
        """Sin sectores: proyecta desde el bulbo húmedo con lapse rate estándar."""
        # 3,5 °C a 2.500 m → la isoterma de 0,5 °C está ~460 m más arriba
        assert interpolar_cota([], bulbo_humedo_c=3.5, altitud_referencia_m=2500) == 2960

    def test_sin_datos(self):
        assert interpolar_cota([]) is None

    def test_zonas_sin_precipitacion_no_aportan(self):
        """interpolar_cota solo recibe sectores con precipitación; lista vacía → None."""
        assert interpolar_cota([], bulbo_humedo_c=None) is None
