"""
Tool: analizar_tendencia_72h

Analiza la tendencia meteorológica de las últimas 24h y proyecta
las próximas 48h usando datos de condiciones_actuales y pronostico_horas.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from agentes.datos.consultor_bigquery import ConsultorBigQuery


TOOL_TENDENCIA_72H = {
    "name": "analizar_tendencia_72h",
    "description": (
        "Analiza la tendencia meteorológica combinando: "
        "(1) historial de las últimas 24h desde condiciones_actuales, "
        "(2) pronóstico horario desde pronostico_horas (si disponible). "
        "Identifica ciclos de temperatura, cambios de viento, "
        "patrones de precipitación y tendencias de fusión/congelación."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre_ubicacion": {
                "type": "string",
                "description": "Nombre exacto de la ubicación en BigQuery"
            }
        },
        "required": ["nombre_ubicacion"]
    }
}


def ejecutar_analizar_tendencia_72h(nombre_ubicacion: str) -> dict:
    """
    Analiza tendencia meteorológica de 72h (24h pasadas + 48h futuras).

    Args:
        nombre_ubicacion: nombre exacto de la ubicación

    Returns:
        dict con tendencia, ciclos y patrones de riesgo
    """
    consultor = ConsultorBigQuery()
    tendencia = consultor.obtener_tendencia_meteorologica(nombre_ubicacion)

    if "error" in tendencia:
        return tendencia

    if not tendencia.get("disponible"):
        return {
            "disponible": False,
            "ubicacion": nombre_ubicacion,
            "mensaje": tendencia.get("razon", "Sin datos de pronóstico horario")
        }

    # obtener_tendencia_meteorologica retorna estadísticas agregadas de pronostico_horas
    # (no filas individuales). Derivar análisis desde esas estadísticas.
    temp_min = tendencia.get("temp_min_72h")
    temp_max = tendencia.get("temp_max_72h")
    precip_total = tendencia.get("precip_total_acumulada_mm", 0) or 0
    viento_max = tendencia.get("viento_max_ms")
    horas_precip = tendencia.get("horas_con_precipitacion", 0) or 0
    tendencia_temp = tendencia.get("tendencia_temperatura", "estable")

    # Estadísticas desde datos agregados
    estadisticas = {
        "temp_min_C": temp_min,
        "temp_max_C": temp_max,
        "temp_promedio_C": round((temp_min + temp_max) / 2, 1) if temp_min is not None and temp_max is not None else None,
        "variacion_termica_C": round(abs(temp_max - temp_min), 1) if temp_min is not None and temp_max is not None else 0,
        "viento_max_ms": viento_max,
        "precipitacion_total_mm": round(precip_total, 1),
        "horas_con_datos": horas_precip
    }

    # Detectar ciclo fusión-congelación desde temp agregadas
    ciclo_fusion_congelacion = (
        temp_max is not None and temp_min is not None
        and temp_max > 0 and temp_min < 0
    )
    ciclos_temp = {
        "ciclo_detectado": ciclo_fusion_congelacion,
        "temp_max_C": temp_max,
        "temp_min_C": temp_min,
        "ciclo_fusion_congelacion": ciclo_fusion_congelacion,
        "alerta_ciclo": "CICLO_FUSION_CONGELACION_ACTIVO" if ciclo_fusion_congelacion else None
    }

    # Tendencia de viento desde estadísticas (no hay series temporales)
    tendencia_viento = {
        "disponible": viento_max is not None,
        "tendencia": "desconocida",
        "maximo_ms": viento_max,
        "alerta": "VIENTO_FUERTE_72H" if viento_max and viento_max > 15 else None
    }

    # Eventos de precipitación
    eventos = []
    if precip_total > 30:
        eventos.append("PRECIPITACION_ACUMULADA_ALTA")
    elif precip_total > 10:
        eventos.append("PRECIPITACION_ACUMULADA_MODERADA")
    if horas_precip > 6:
        eventos.append("PRECIPITACION_PERSISTENTE")
    eventos_precip = {
        "total_mm": round(precip_total, 1),
        "horas_con_precipitacion": horas_precip,
        "eventos": eventos
    }

    # Evaluar peligro de fusión-recongelación
    peligro_fusion_congelacion = _evaluar_peligro_fusion_congelacion(
        ciclos_temp=ciclos_temp,
        estadisticas=estadisticas
    )

    return {
        "disponible": True,
        "ubicacion": nombre_ubicacion,
        "tendencia_temperatura_72h": tendencia_temp,
        "estadisticas_72h": estadisticas,
        "ciclos_temperatura": ciclos_temp,
        "tendencia_viento": tendencia_viento,
        "eventos_precipitacion": eventos_precip,
        "peligro_fusion_congelacion": peligro_fusion_congelacion,
        "alertas": tendencia.get("alertas", []),
        "alertas_tendencia": _compilar_alertas_tendencia(
            estadisticas, ciclos_temp, tendencia_viento, eventos_precip, peligro_fusion_congelacion
        )
    }


def _evaluar_peligro_fusion_congelacion(
    ciclos_temp: dict,
    estadisticas: dict
) -> dict:
    """Evalúa el peligro específico de ciclos fusión-congelación."""
    peligro = "bajo"
    factores = []

    if ciclos_temp.get("ciclo_fusion_congelacion"):
        peligro = "alto"
        factores.append("CICLO_FUSION_CONGELACION")

    amplitud = ciclos_temp.get("amplitud_ciclo_C", 0)
    if amplitud and amplitud > 10:
        if peligro == "bajo":
            peligro = "moderado"
        factores.append("ALTA_AMPLITUD_TERMICA")

    variacion = estadisticas.get("variacion_termica_C", 0)
    if variacion and variacion > 15:
        factores.append("VARIACION_TERMICA_EXTREMA")

    return {
        "nivel_peligro": peligro,
        "factores": factores,
        "descripcion": _describir_peligro_fusion(peligro, factores)
    }


def _describir_peligro_fusion(peligro: str, factores: list) -> str:
    """Genera descripción del peligro de fusión-congelación."""
    if not factores:
        return "Sin ciclos de fusión-congelación detectados."
    return (
        f"Peligro {peligro} por ciclos fusión-congelación. "
        f"Factores: {', '.join(factores)}. "
        "Posible formación de capas débiles basales y nieve húmeda diurna."
    )


def _compilar_alertas_tendencia(
    estadisticas: dict,
    ciclos_temp: dict,
    tendencia_viento: dict,
    eventos_precip: dict,
    peligro_fusion: dict
) -> list:
    """Compila todas las alertas de tendencia."""
    alertas = []

    if ciclos_temp.get("alerta_ciclo"):
        alertas.append(ciclos_temp["alerta_ciclo"])

    if tendencia_viento.get("alerta"):
        alertas.append(tendencia_viento["alerta"])

    alertas.extend(eventos_precip.get("eventos", []))

    if peligro_fusion.get("nivel_peligro") in ("alto", "muy_alto"):
        alertas.extend(peligro_fusion.get("factores", []))

    viento_max = estadisticas.get("viento_max_ms")
    if viento_max and viento_max > 20:
        alertas.append("VIENTO_MAX_TEMPORAL_24H")

    return list(set(alertas))
