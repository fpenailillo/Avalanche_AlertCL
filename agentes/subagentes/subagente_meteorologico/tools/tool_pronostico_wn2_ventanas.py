"""
Tool: obtener_pronostico_wn2_ventanas

Pronóstico WeatherNext 2 en 4 ventanas de 6h (madrugada/manana/tarde/noche)
más resumen diario. Enriquecimiento opcional sobre Open-Meteo/Google Weather.

Si USE_WEATHERNEXT2=false (default) → retorna disponible=False; S3 continúa
con el flujo meteorológico estándar sin interrupción.
"""

import logging
import os
from datetime import datetime, timezone

from agentes.datos.constantes_zonas import COORDENADAS_ZONAS

logger = logging.getLogger(__name__)

_USE_WEATHERNEXT2 = os.environ.get("USE_WEATHERNEXT2", "false").lower() == "true"


TOOL_PRONOSTICO_WN2_VENTANAS = {
    "name": "obtener_pronostico_wn2_ventanas",
    "description": (
        "Pronóstico WeatherNext 2 (ensemble 64 miembros DeepMind) en 4 ventanas de 6h "
        "(madrugada/manana/tarde/noche) más resumen diario. "
        "Entrega: percentiles P5/P50/P95 temperatura y precipitación, "
        "viento a 100m con clasificación EAWS (calma/leve/moderado/fuerte/temporal), "
        "probabilidades de tipo de precipitación (nieve_seca/nieve_húmeda/lluvia/wind_slab), "
        "4 alertas booleanas (heavy_snow/storm_slab/wet_snow/wind_strong), "
        "probable_avalanche_problem (8 categorías EAWS) y confianza_pronostico. "
        "CUÁNDO USARLA: como enriquecimiento OPCIONAL antes de obtener_pronostico_dias — "
        "(a) para cuantificar incertidumbre del pronóstico, "
        "(b) para detectar el problema EAWS probable con base ensemble, "
        "(c) cuando necesites granularidad 6h para timing de tormenta. "
        "Si retorna disponible=false, ignorar y continuar con el flujo estándar."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre_ubicacion": {
                "type": "string",
                "description": "Nombre exacto de la ubicación (debe existir en COORDENADAS_ZONAS)"
            },
            "fecha_objetivo": {
                "type": "string",
                "description": (
                    "Fecha ISO (YYYY-MM-DD) del día a consultar. "
                    "Default: hoy en UTC. Para retroactivos, proveer la fecha exacta."
                )
            }
        },
        "required": ["nombre_ubicacion"]
    }
}


def ejecutar_obtener_pronostico_wn2_ventanas(
    nombre_ubicacion: str,
    fecha_objetivo: str | None = None,
) -> dict:
    """
    Obtiene pronóstico WN2 en ventanas 6h para la ubicación indicada.

    Args:
        nombre_ubicacion: Nombre exacto de la ubicación
        fecha_objetivo:   Fecha ISO YYYY-MM-DD. Default: hoy UTC.

    Returns:
        dict con 'disponible', 'ventanas' (list), 'diario' (dict)
        o {'disponible': False, 'mensaje': str} si WN2 inactivo.
    """
    if not _USE_WEATHERNEXT2:
        return {
            "disponible": False,
            "mensaje": (
                "WeatherNext 2 no activado (USE_WEATHERNEXT2=false). "
                "Continuar con obtener_pronostico_dias y obtener_condiciones_actuales_meteo."
            ),
        }

    coords = COORDENADAS_ZONAS.get(nombre_ubicacion)
    if coords is None:
        return {
            "disponible": False,
            "mensaje": (
                f"Ubicación '{nombre_ubicacion}' no encontrada en COORDENADAS_ZONAS. "
                "Verificar nombre exacto."
            ),
        }

    lat, lon = coords

    if fecha_objetivo is None:
        fecha_objetivo = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        from agentes.subagentes.subagente_meteorologico.fuentes.fuente_weathernext2 import (
            FuenteWeatherNext2,
        )

        fuente = FuenteWeatherNext2()
        resultado = fuente.obtener_ventanas_6h(
            zona=nombre_ubicacion,
            lat=lat,
            lon=lon,
            fecha_objetivo=fecha_objetivo,
        )

        if not resultado.get("disponible"):
            logger.warning(
                f"tool_wn2_ventanas: '{nombre_ubicacion}' — WN2 no disponible: "
                f"{resultado.get('error')}"
            )
            return {
                "disponible": False,
                "mensaje": resultado.get("error", "Sin datos WN2"),
            }

        logger.info(
            f"tool_wn2_ventanas: '{nombre_ubicacion}' fecha={fecha_objetivo} "
            f"— {len(resultado.get('ventanas', []))} ventanas OK"
        )
        return resultado

    except Exception as exc:
        logger.error(f"tool_wn2_ventanas: '{nombre_ubicacion}' — {exc}")
        return {
            "disponible": False,
            "mensaje": f"Error consultando WeatherNext 2: {exc}",
        }
