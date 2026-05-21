"""
Tool: obtener_condiciones_actuales_meteo

Obtiene las condiciones meteorológicas actuales desde BigQuery
(tabla condiciones_actuales) para la ubicación especificada.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from agentes.datos.consultor_bigquery import ConsultorBigQuery


TOOL_CONDICIONES_ACTUALES_METEO = {
    "name": "obtener_condiciones_actuales_meteo",
    "description": (
        "Obtiene las condiciones meteorológicas actuales de una ubicación "
        "desde BigQuery (tabla condiciones_actuales): temperatura, viento, "
        "precipitación, humedad, presión, cobertura nubosa y condición clima. "
        "Es la primera fuente de datos para el análisis meteorológico."
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


def ejecutar_obtener_condiciones_actuales_meteo(nombre_ubicacion: str) -> dict:
    """
    Obtiene condiciones actuales y evalúa factores de riesgo inmediatos.

    Args:
        nombre_ubicacion: nombre exacto de la ubicación

    Returns:
        dict con condiciones actuales + evaluación de riesgo meteorológico
    """
    consultor = ConsultorBigQuery()
    condiciones = consultor.obtener_condiciones_actuales(nombre_ubicacion)

    if "error" in condiciones:
        return condiciones

    if not condiciones.get("disponible"):
        return {
            "disponible": False,
            "ubicacion": nombre_ubicacion,
            "mensaje": "Sin condiciones actuales en BigQuery"
        }

    # Extraer variables clave
    temperatura = condiciones.get("temperatura")
    velocidad_viento = condiciones.get("velocidad_viento", 0) or 0
    precipitacion = condiciones.get("precipitacion_acumulada", 0) or 0
    prob_precip = condiciones.get("probabilidad_precipitacion", 0) or 0
    humedad = condiciones.get("humedad_relativa", 0) or 0
    condicion_clima = condiciones.get("condicion_clima", "")
    sensacion_termica = condiciones.get("sensacion_termica")
    # FIX-CR19: nieve nueva en cm desde IMIS HN24 (datos_json_crudo)
    nieve_nueva_cm = condiciones.get("nieve_nueva_cm")

    # Evaluar factores de riesgo meteorológico inmediato
    alertas_meteo = _evaluar_alertas_meteo(
        velocidad_viento=velocidad_viento,
        precipitacion=precipitacion,
        temperatura=temperatura,
        prob_precip=prob_precip,
        nieve_nueva_cm=nieve_nueva_cm,
    )

    # Clasificación de viento para transporte de nieve
    clasificacion_viento = _clasificar_viento(velocidad_viento)

    # Riesgo de precipitación nival
    riesgo_precipitacion = _evaluar_riesgo_precipitacion(
        precipitacion=precipitacion,
        prob_precip=prob_precip,
        temperatura=temperatura,
        nieve_nueva_cm=nieve_nueva_cm,
    )

    resultado = {
        "disponible": True,
        "ubicacion": nombre_ubicacion,
        "condiciones": {
            "temperatura_C": temperatura,
            "sensacion_termica_C": sensacion_termica,
            "velocidad_viento_ms": velocidad_viento,
            "direccion_viento": condiciones.get("direccion_viento"),
            "precipitacion_mm": precipitacion,
            "probabilidad_precipitacion_pct": prob_precip,
            "humedad_relativa_pct": humedad,
            "presion_hPa": condiciones.get("presion_aire"),
            "cobertura_nubes_pct": condiciones.get("cobertura_nubes"),
            "condicion_clima": condicion_clima,
            "es_dia": condiciones.get("es_dia")
        },
        "alertas_meteo": alertas_meteo,
        "clasificacion_viento": clasificacion_viento,
        "riesgo_precipitacion": riesgo_precipitacion,
        "hora_registro": condiciones.get("hora_actual")
    }
    # FIX-CR19: exponer nieve_nueva_cm explícitamente cuando disponible (IMIS HN24)
    if nieve_nueva_cm is not None:
        resultado["nieve_nueva_cm"] = nieve_nueva_cm
    return resultado


def _evaluar_alertas_meteo(
    velocidad_viento: float,
    precipitacion: float,
    temperatura,
    prob_precip: float,
    nieve_nueva_cm: float = None,
) -> list:
    """Evalúa alertas meteorológicas para riesgo de avalancha."""
    alertas = []

    if velocidad_viento > 20:
        alertas.append("VIENTO_TEMPORAL_FUERTE")
    elif velocidad_viento > 15:
        alertas.append("VIENTO_FUERTE_TRANSPORTE_NIEVE")

    if precipitacion > 30:
        alertas.append("PRECIPITACION_CRITICA_30MM")
    elif precipitacion > 10:
        alertas.append("PRECIPITACION_SIGNIFICATIVA")

    # FIX-CR19: alerta por carga de nieve nueva (IMIS HN24)
    if nieve_nueva_cm is not None:
        if nieve_nueva_cm >= 30:
            alertas.append("CARGA_NIEVE_EXTREMA_30CM")
        elif nieve_nueva_cm >= 15:
            alertas.append("NEVADA_SIGNIFICATIVA_15CM")

    if temperatura is not None:
        if temperatura > 5:
            alertas.append("TEMPERATURA_SOBRE_PUNTO_FUSION")
        elif temperatura > 0:
            alertas.append("TEMPERATURA_CERCA_PUNTO_FUSION")
        elif temperatura < -15:
            alertas.append("TEMPERATURA_EXTREMADAMENTE_FRIA")

    if prob_precip > 80:
        alertas.append("ALTA_PROBABILIDAD_PRECIPITACION")

    return alertas


def _clasificar_viento(velocidad_ms: float) -> dict:
    """Clasifica el viento según su capacidad de transporte de nieve."""
    if velocidad_ms > 20:
        categoria = "temporal"
        transporte_nieve = "muy_alto"
        descripcion = "Temporal: transporte masivo de nieve"
    elif velocidad_ms > 15:
        categoria = "fuerte"
        transporte_nieve = "alto"
        descripcion = "Viento fuerte: transporte activo de nieve"
    elif velocidad_ms > 8:
        categoria = "moderado"
        transporte_nieve = "moderado"
        descripcion = "Viento moderado: transporte posible de nieve seca"
    elif velocidad_ms > 3:
        categoria = "suave"
        transporte_nieve = "bajo"
        descripcion = "Viento suave: transporte mínimo"
    else:
        categoria = "calmo"
        transporte_nieve = "ninguno"
        descripcion = "Calma: sin transporte de nieve"

    return {
        "velocidad_ms": velocidad_ms,
        "categoria": categoria,
        "transporte_nieve": transporte_nieve,
        "descripcion": descripcion
    }


def _evaluar_riesgo_precipitacion(
    precipitacion: float,
    prob_precip: float,
    temperatura,
    nieve_nueva_cm: float = None,
) -> dict:
    """Evalúa el riesgo de precipitación nival para avalanchas."""
    # Determinar si precipita como nieve o lluvia
    if temperatura is None:
        tipo_precipitacion = "desconocido"
    elif temperatura <= -2:
        tipo_precipitacion = "nieve"
    elif temperatura <= 2:
        tipo_precipitacion = "nieve_o_aguanieve"
    elif temperatura <= 5:
        tipo_precipitacion = "lluvia_posible_nieve_altura"
    else:
        tipo_precipitacion = "lluvia"

    # FIX-CR19: nivel de riesgo usa nieve_nueva_cm (IMIS) cuando disponible
    if nieve_nueva_cm is not None and "nieve" in tipo_precipitacion:
        if nieve_nueva_cm >= 30:
            nivel = "muy_alto"
        elif nieve_nueva_cm >= 15:
            nivel = "alto"
        elif nieve_nueva_cm >= 5:
            nivel = "moderado"
        else:
            nivel = "bajo"
    elif precipitacion > 30 and tipo_precipitacion in ("nieve", "nieve_o_aguanieve"):
        nivel = "muy_alto"
    elif precipitacion > 15 and "nieve" in tipo_precipitacion:
        nivel = "alto"
    elif precipitacion > 5 and "nieve" in tipo_precipitacion:
        nivel = "moderado"
    elif prob_precip > 60:
        nivel = "moderado"
    else:
        nivel = "bajo"

    resultado = {
        "precipitacion_mm": precipitacion,
        "tipo": tipo_precipitacion,
        "nivel_riesgo": nivel,
        "probabilidad_pct": prob_precip,
    }
    if nieve_nueva_cm is not None:
        resultado["nieve_nueva_cm"] = nieve_nueva_cm
    return resultado
