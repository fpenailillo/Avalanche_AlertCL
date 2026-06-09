"""
WN2 Features Extractor — fuente única y centralizada de features diarias WeatherNext 2.

Provee un helper cacheado que normaliza el acceso a WN2 y evita consultas BQ
redundantes cuando varios tools del mismo sector/fecha lo necesitan.

Todos los consumidores (PINN, clasificador EAWS, ventanas críticas) DEBEN
importar desde aquí en lugar de instanciar FuenteWeatherNext2 directamente.
"""

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=256)
def obtener_features_wn2(nombre_ubicacion: str, fecha: str) -> dict:
    """Fuente única de features diarias WN2 para una zona/fecha dadas.

    El resultado se cachea por (nombre_ubicacion, fecha) durante la vida del
    proceso, de modo que PINN, clasificador y ventanas_criticas comparten la
    misma llamada BQ y no abren tres conexiones por sector.

    Args:
        nombre_ubicacion: nombre exacto de la zona (clave en COORDENADAS_ZONAS).
        fecha: ISO YYYY-MM-DD — fecha objetivo para el pronóstico WN2.

    Returns:
        dict con las siguientes claves:
        - disponible  (bool)   — False si WN2 inactivo, sin coords o error
        - nieve_24h_p50 (float) — nieve nueva 24h cm percentil 50 (corregido)
        - nieve_24h_p95 (float) — nieve nueva 24h cm percentil 95 (corregido)
        - nieve_3d_p95  (float) — acumulado 72h cm p95 (0.0 si no disponible)
        - heavy_snow   (bool)  — alerta heavy_snow del ensemble
        - storm_slab   (bool)  — alerta storm_slab del ensemble
        - wind_strong  (bool)  — alerta wind_strong del ensemble
        - wet_snow     (bool)  — alerta wet_snow del ensemble
        - prob_problem (str)   — problema avalancha dominante ('' si no disponible)
        - confianza    (str)   — confianza diaria del ensemble ('' si no disponible)
    """
    _vacio = dict(
        disponible=False,
        nieve_24h_p50=0.0,
        nieve_24h_p95=0.0,
        nieve_3d_p95=0.0,
        heavy_snow=False,
        storm_slab=False,
        wind_strong=False,
        wet_snow=False,
        prob_problem="",
        confianza="",
    )

    if os.environ.get("USE_WEATHERNEXT2", "false").lower() != "true":
        return _vacio
    if not nombre_ubicacion or not fecha:
        return _vacio

    try:
        from agentes.datos.constantes_zonas import COORDENADAS_ZONAS, obtener_elevacion_referencia
        from agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2 import FuenteWeatherNext2

        coords = COORDENADAS_ZONAS.get(nombre_ubicacion)
        if not coords:
            logger.debug(
                f"[WN2Features] sin coordenadas para '{nombre_ubicacion}' — saltado"
            )
            return _vacio

        lat, lon = coords
        elev = obtener_elevacion_referencia(nombre_ubicacion)
        res = FuenteWeatherNext2().obtener_ventanas_6h(
            zona=nombre_ubicacion,
            lat=lat,
            lon=lon,
            fecha_objetivo=fecha,
            elevacion_m=elev,
        )

        if not res.get("disponible"):
            return _vacio

        d      = res.get("diario") or {}
        alerts = d.get("alerts_dia") or {}

        feat = dict(
            disponible   = True,
            nieve_24h_p50= float(d.get("nieve_24h_cm_p50_corr") or 0.0),
            nieve_24h_p95= float(d.get("nieve_24h_cm_p95_corr") or 0.0),
            nieve_3d_p95 = float(d.get("nieve_3d_cm_p95_corr")  or 0.0),
            heavy_snow   = bool(alerts.get("heavy_snow",  False)),
            storm_slab   = bool(alerts.get("storm_slab",  False)),
            wind_strong  = bool(alerts.get("wind_strong", False)),
            wet_snow     = bool(alerts.get("wet_snow",    False)),
            prob_problem = str(d.get("problema_dominante") or ""),
            confianza    = str(d.get("confianza_dia")      or ""),
        )
        logger.debug(
            f"[WN2Features] '{nombre_ubicacion}' {fecha}: "
            f"p50={feat['nieve_24h_p50']:.1f} p95={feat['nieve_24h_p95']:.1f} "
            f"heavy={feat['heavy_snow']} storm={feat['storm_slab']}"
        )
        return feat

    except Exception as exc:
        logger.warning(
            f"[WN2Features] error obteniendo features "
            f"para '{nombre_ubicacion}' {fecha}: {exc}"
        )
        return _vacio


def invalidar_cache_wn2() -> None:
    """Limpia el cache LRU — útil en tests o al cambiar la fecha de referencia."""
    obtener_features_wn2.cache_clear()
    logger.debug("[WN2Features] cache LRU limpiado")
