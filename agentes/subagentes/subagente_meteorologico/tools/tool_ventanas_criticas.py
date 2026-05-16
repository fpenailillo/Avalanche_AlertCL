"""
Tool: detectar_ventanas_criticas

Detecta ventanas de tiempo con condiciones meteorológicas críticas
para el riesgo de avalanchas: combinaciones de nevada + viento,
ciclos fusión-congelación, y períodos de lluvia sobre nieve.
"""

import logging
import os
import sys

_ROOT = os.path.join(os.path.dirname(__file__), '../../../..')
try:
    from agentes.datos.constantes_zonas import obtener_region as _obtener_region
except ImportError:
    try:
        sys.path.insert(0, os.path.join(_ROOT, 'agentes'))
        from datos.constantes_zonas import obtener_region as _obtener_region
    except ImportError:
        def _obtener_region(zona: str) -> str:  # type: ignore[misc]
            return "andes_chile"

logger = logging.getLogger(__name__)

TOOL_VENTANAS_CRITICAS = {
    "name": "detectar_ventanas_criticas",
    "description": (
        "Detecta ventanas de tiempo críticas para avalanchas combinando "
        "las condiciones actuales, la tendencia 72h y el pronóstico de días. "
        "Identifica: (1) nevada + viento simultáneos, (2) ciclos "
        "fusión-congelación, (3) lluvia sobre nieve, (4) precipitación "
        "intensa sobre manto existente. Produce un calendario de riesgo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "temperatura_actual_C": {
                "type": "number",
                "description": "Temperatura actual en °C"
            },
            "velocidad_viento_actual_ms": {
                "type": "number",
                "description": "Velocidad de viento actual en m/s"
            },
            "precipitacion_actual_mm": {
                "type": "number",
                "description": "Precipitación acumulada actual en mm"
            },
            "alertas_tendencia": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alertas detectadas en el análisis de tendencia 72h"
            },
            "dias_alto_riesgo": {
                "type": "integer",
                "description": "Número de días de alto riesgo en el pronóstico"
            },
            "dia_mayor_riesgo_fecha": {
                "type": "string",
                "description": "Fecha del día de mayor riesgo pronosticado"
            },
            "dia_mayor_riesgo_nivel": {
                "type": "string",
                "description": "Nivel de riesgo del día más peligroso pronosticado"
            },
            "ciclo_fusion_congelacion": {
                "type": "boolean",
                "description": "¿Hay ciclo activo de fusión-congelación?"
            },
            "precipitacion_72h_mm": {
                "type": "number",
                "description": "Precipitación acumulada en las últimas 72h en mm (desde analizar_tendencia_72h)"
            },
            "nombre_ubicacion": {
                "type": "string",
                "description": "Nombre de la ubicación (e.g. 'Interlaken', 'La Parva Sector Alto'). Usado para calibrar umbrales ERA5 por región."
            }
        },
        "required": [
            "temperatura_actual_C",
            "velocidad_viento_actual_ms",
            "precipitacion_actual_mm"
        ]
    }
}


def ejecutar_detectar_ventanas_criticas(
    temperatura_actual_C: float,
    velocidad_viento_actual_ms: float,
    precipitacion_actual_mm: float,
    alertas_tendencia: list = None,
    dias_alto_riesgo: int = 0,
    dia_mayor_riesgo_fecha: str = None,
    dia_mayor_riesgo_nivel: str = None,
    ciclo_fusion_congelacion: bool = False,
    precipitacion_72h_mm: float = 0,
    nombre_ubicacion: str = None,
) -> dict:
    """
    Detecta ventanas críticas de riesgo meteorológico.

    Args:
        temperatura_actual_C: temperatura actual
        velocidad_viento_actual_ms: velocidad de viento actual
        precipitacion_actual_mm: precipitación acumulada
        alertas_tendencia: alertas de la tendencia 72h
        dias_alto_riesgo: días de alto riesgo en pronóstico
        dia_mayor_riesgo_fecha: fecha del día de mayor riesgo
        dia_mayor_riesgo_nivel: nivel de riesgo del día más peligroso
        ciclo_fusion_congelacion: ¿ciclo activo?
        precipitacion_72h_mm: precipitación acumulada 72h desde analizar_tendencia_72h
        nombre_ubicacion: nombre de la ubicación para calibración regional ERA5

    Returns:
        dict con ventanas críticas, periodo de mayor riesgo y recomendaciones
    """
    alertas_tendencia = alertas_tendencia or []
    ventanas = []

    # ─── Umbrales calibrados por región (CR-10A + CR-10B, v10.0) ─────────────
    # ERA5 a 9km promedia espacialmente: en Alpes, el valor puntual de estaciones
    # IMIS es ~2-3× el valor ERA5. En Andes, la subestimación es menor pero
    # también presente (precipitación convectiva verano austral).
    # Viento: ERA5 subestima velocidades de cresta en terreno alpino por factor ~1.4
    # (pendientes complejas no resueltas a 9km). Umbral reducido a 7 m/s para Alpes.
    _region = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    _es_alpes = _region == "alpes_swiss"

    # CR-10A: precipitación efectiva — usa precipitacion_72h_mm/3 SOLO en Alpes.
    # ERA5 instantáneo a 12:00 UTC subestima precipitación real ~2-3× en terreno
    # alpino complejo. En Andes Chile la subestimación es menor y el fallback global
    # generaba FUSION_ACTIVA_CON_CARGA falsos en La Parva (FIX-CR16A).
    _precip_diaria_72h = (precipitacion_72h_mm or 0) / 3
    if _es_alpes and precipitacion_actual_mm == 0 and _precip_diaria_72h > 0:
        precip_efectiva = _precip_diaria_72h
        logger.info(
            f"[VentanasCriticas] CR-10A (Alpes only): precip_efectiva={precip_efectiva:.1f}mm "
            f"desde 72h/3 (actual=0, region={_region})"
        )
    else:
        precip_efectiva = precipitacion_actual_mm

    _umbral_nevada     = 2.0  if _es_alpes else 5.0
    _umbral_lluvia     = 1.5  if _es_alpes else 3.0
    _umbral_carga_72h  = 5.0  if _es_alpes else 10.0

    # CR-10B: umbral viento reducido en Alpes (ERA5 subestima vientos de cresta)
    _umbral_viento_fuerte         = 7.0  if _es_alpes else 10.0
    # Redistribución: en Alpes coincide con el umbral base (cualquier viento fuerte
    # redistribuye nieve en terreno alpino complejo). En Andes requiere umbral mayor.
    _umbral_viento_redistribucion = 7.0  if _es_alpes else 15.0

    # ─── Ventana 1: Nevada + Viento simultáneos ──────────────────────────────
    nevada_activa = (
        precip_efectiva > _umbral_nevada
        and temperatura_actual_C is not None
        and temperatura_actual_C <= 0
    )
    viento_fuerte = velocidad_viento_actual_ms > _umbral_viento_fuerte

    if nevada_activa and viento_fuerte:
        ventanas.append({
            "tipo": "NEVADA_MAS_VIENTO",
            "severidad": "muy_alta",
            "descripcion": (
                f"Nevada activa ({precipitacion_actual_mm:.0f}mm) con "
                f"viento fuerte ({velocidad_viento_actual_ms:.0f}m/s): "
                "transporte y acumulación de placas de nieve"
            ),
            "tiempo": "actual"
        })

    # ─── Ventana 2: Lluvia sobre nieve ───────────────────────────────────────
    lluvia_sobre_nieve = (
        precip_efectiva > _umbral_lluvia
        and temperatura_actual_C is not None
        and temperatura_actual_C > 2
    )
    if lluvia_sobre_nieve:
        ventanas.append({
            "tipo": "LLUVIA_SOBRE_NIEVE",
            "severidad": "muy_alta",
            "descripcion": (
                f"Lluvia ({precipitacion_actual_mm:.0f}mm) sobre manto nival "
                f"a {temperatura_actual_C:.0f}°C: saturación y deslizamiento húmedo"
            ),
            "tiempo": "actual"
        })

    # ─── Ventana 3: Ciclo fusión-congelación ─────────────────────────────────
    if ciclo_fusion_congelacion:
        ventanas.append({
            "tipo": "CICLO_FUSION_CONGELACION",
            "severidad": "alta",
            "descripcion": (
                "Ciclo diurno con fusión y recongelación: "
                "formación de costras de hielo y capas débiles basales. "
                "Mayor riesgo en horas de mayor insolación."
            ),
            "tiempo": "en_curso"
        })

    # ─── Ventana 4: Viento fuerte sin nevada (transporte de nieve vieja) ─────
    if viento_fuerte and not nevada_activa and velocidad_viento_actual_ms > _umbral_viento_redistribucion:
        ventanas.append({
            "tipo": "VIENTO_FUERTE_REDISTRIBUCION",
            "severidad": "alta",
            "descripcion": (
                f"Viento fuerte ({velocidad_viento_actual_ms:.0f}m/s) "
                "redistribuye nieve existente: formación de placas en sotavento"
            ),
            "tiempo": "actual"
        })

    # ─── Ventana 5: Pronóstico de días de alto riesgo ─────────────────────────
    if dias_alto_riesgo > 0 and dia_mayor_riesgo_fecha:
        ventanas.append({
            "tipo": "DIA_ALTO_RIESGO_PRONOSTICADO",
            "severidad": "alta" if dia_mayor_riesgo_nivel == "alto" else "muy_alta",
            "descripcion": (
                f"Día de mayor riesgo pronosticado: {dia_mayor_riesgo_fecha} "
                f"(nivel {dia_mayor_riesgo_nivel}). "
                f"Total: {dias_alto_riesgo} días de alto riesgo en período."
            ),
            "tiempo": dia_mayor_riesgo_fecha
        })

    # ─── Ventana 6: Alertas de tendencia 72h ─────────────────────────────────
    alertas_criticas_72h = [
        a for a in alertas_tendencia
        if any(k in a for k in ["PRECIPITACION_ALTA", "FUSION_CONGELACION", "TEMPORAL"])
    ]
    if alertas_criticas_72h:
        ventanas.append({
            "tipo": "ALERTAS_TENDENCIA_72H",
            "severidad": "moderada",
            "descripcion": f"Alertas en tendencia: {', '.join(alertas_criticas_72h)}",
            "tiempo": "próximas_72h"
        })

    # ─── Período de mayor riesgo ──────────────────────────────────────────────
    periodo_mayor_riesgo = _determinar_periodo_mayor_riesgo(
        ventanas=ventanas,
        temperatura=temperatura_actual_C,
        dia_mayor_riesgo_fecha=dia_mayor_riesgo_fecha
    )

    # ─── Clasificación meteorológica para EAWS ────────────────────────────────
    factor_meteorologico_eaws = _clasificar_factor_meteorologico(
        ventanas=ventanas,
        alertas_tendencia=alertas_tendencia,
        precipitacion=precip_efectiva,
        precipitacion_72h=precipitacion_72h_mm,
        viento=velocidad_viento_actual_ms,
        temperatura=temperatura_actual_C,
        umbral_carga_72h=_umbral_carga_72h,
        umbral_nevada=_umbral_nevada,
        umbral_viento_fuerte=_umbral_viento_fuerte,
    )

    # FIX-V: DIA_ALTO_RIESGO_PRONOSTICADO refleja ciclos térmicos normales del pronóstico
    # (siempre presentes en Andes verano). Excluirlo del conteo usado para el bump de
    # frecuencia en la matriz EAWS evita inflar el nivel en días sin evento activo.
    _TIPOS_SOLO_PRONOSTICO = {"DIA_ALTO_RIESGO_PRONOSTICADO"}
    num_ventanas_eaws = sum(1 for v in ventanas if v["tipo"] not in _TIPOS_SOLO_PRONOSTICO)

    return {
        "ventanas_criticas": ventanas,
        "num_ventanas_criticas": num_ventanas_eaws,
        "num_ventanas_totales": len(ventanas),
        "periodo_mayor_riesgo": periodo_mayor_riesgo,
        "factor_meteorologico_eaws": factor_meteorologico_eaws,
        "condiciones_actuales_resumen": {
            "temperatura_C": temperatura_actual_C,
            "viento_ms": velocidad_viento_actual_ms,
            "precipitacion_mm": precipitacion_actual_mm,
            "nevada_activa": nevada_activa,
            "lluvia_sobre_nieve": lluvia_sobre_nieve
        }
    }


def _determinar_periodo_mayor_riesgo(
    ventanas: list,
    temperatura: float,
    dia_mayor_riesgo_fecha: str
) -> dict:
    """Determina el período de mayor riesgo consolidado."""
    if not ventanas:
        return {"periodo": "sin_ventanas_criticas", "cuando": "no_identificado"}

    # Verificar si hay riesgo actual
    ventanas_actuales = [v for v in ventanas if v.get("tiempo") in ("actual", "en_curso")]

    if ventanas_actuales:
        if temperatura is not None and temperatura > 0:
            cuando = "horas_diurnas_de_mayor_insolacion"
        else:
            cuando = "inmediato_condiciones_actuales"
    elif dia_mayor_riesgo_fecha:
        cuando = dia_mayor_riesgo_fecha
    else:
        cuando = "próximas_48_72h"

    severidades = [v.get("severidad", "baja") for v in ventanas]
    severidad_max = (
        "muy_alta" if "muy_alta" in severidades
        else "alta" if "alta" in severidades
        else "moderada"
    )

    return {
        "periodo": "activo" if ventanas_actuales else "próximo",
        "cuando": cuando,
        "severidad_maxima": severidad_max,
        "num_factores_activos": len(ventanas_actuales)
    }


def _clasificar_factor_meteorologico(
    ventanas: list,
    alertas_tendencia: list,
    precipitacion: float,
    precipitacion_72h: float,
    viento: float,
    temperatura: float,
    umbral_carga_72h: float = 10.0,
    umbral_nevada: float = 5.0,
    umbral_viento_fuerte: float = 10.0,
) -> str:
    """
    Clasifica el factor meteorológico para EAWS.

    Returns:
        "PRECIPITACION_CRITICA", "NEVADA_RECIENTE", "VIENTO_FUERTE",
        "FUSION_ACTIVA_CON_CARGA", "CICLO_FUSION_CONGELACION",
        "CICLO_DIURNO_NORMAL", "LLUVIA_SOBRE_NIEVE", "ESTABLE" o combinaciones.

    REQ-06: distingue CICLO_DIURNO_NORMAL (fenómeno geográfico esperable en
    Andes centrales, >95% de días de verano) de FUSION_ACTIVA_CON_CARGA
    (ciclo térmico + manto cargado = riesgo real). El ciclo diurno sin
    precipitación reciente NO contribuye al nivel EAWS.

    Umbrales (Müller et al. 2025 / EAWS operational guidelines):
    - VIENTO_FUERTE: >10 m/s (36 km/h) — placas forman desde ~25-36 km/h.
    - FUSION_ACTIVA_CON_CARGA: ciclo térmico + precipitación_72h ≥ 10mm.
    - CICLO_DIURNO_NORMAL: ciclo térmico SIN carga reciente (precipitación < 10mm).
    """
    factores = []
    tipos_ventanas = [v.get("tipo", "") for v in ventanas]

    if precipitacion > 30:
        factores.append("PRECIPITACION_CRITICA")
    elif precipitacion > umbral_nevada:
        factores.append("NEVADA_RECIENTE")

    if viento > umbral_viento_fuerte:
        factores.append("VIENTO_FUERTE")

    # REQ-06: diferenciar ciclo diurno normal de fusión con manto cargado.
    # Un ciclo térmico (T_max > 0 / T_min < 0) ocurre casi todos los días
    # en climas continentales de alta montaña (Andes centrales, 33°S).
    # Solo es señal de inestabilidad cuando el manto lleva carga reciente.
    hay_ciclo = "CICLO_FUSION_CONGELACION" in tipos_ventanas
    hay_carga = precipitacion_72h >= umbral_carga_72h or precipitacion > 3

    if hay_ciclo or (temperatura is not None and temperatura > 2):
        if hay_carga:
            factores.append("FUSION_ACTIVA_CON_CARGA")
        else:
            factores.append("CICLO_DIURNO_NORMAL")

    if "LLUVIA_SOBRE_NIEVE" in tipos_ventanas:
        factores.append("LLUVIA_SOBRE_NIEVE")

    return "+".join(factores) if factores else "ESTABLE"
