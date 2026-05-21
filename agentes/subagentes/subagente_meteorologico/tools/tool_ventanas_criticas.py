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
            },
            "nieve_nueva_cm_imis": {
                "type": "number",
                "description": "FIX-CR19: nieve nueva en cm medida por IMIS (HN24). Cuando está disponible en condiciones actuales, pasar este valor — sobrescribe la señal de precipitacion_actual_mm para la evaluación de carga nival. Solo disponible en estaciones suizas con backfill IMIS."
            },
            "wn2_heavy_snow": {
                "type": "boolean",
                "description": "FIX-WN2-TRIGGERS: WeatherNext 2 ensemble (64 miembros) indica precipitación nívea intensa. Pasar solo cuando obtener_pronostico_wn2_ventanas retorna disponible=true. Activa ventana NEVADA_WN2_CONFIRMADA cuando ERA5 no detectó nevada."
            },
            "wn2_storm_slab": {
                "type": "boolean",
                "description": "FIX-WN2-TRIGGERS: WeatherNext 2 ensemble indica problema de placa de viento (viento + nieve). Pasar solo cuando WN2 disponible. Activa PLACA_VIENTO_WN2."
            },
            "wn2_wind_strong": {
                "type": "boolean",
                "description": "FIX-WN2-TRIGGERS: WeatherNext 2 ensemble indica viento fuerte no captado por ERA5. Pasar solo cuando WN2 disponible. Activa VIENTO_WN2_FUERTE."
            },
            "wn2_probable_avalanche_problem": {
                "type": "string",
                "description": "FIX-WN2-TRIGGERS: problema avalancha dominante del ensemble WN2 ('new_snow', 'wind_slab', 'wet_snow', 'persistent_weak_layer' u otro). Informativo para el log."
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
    nieve_nueva_cm_imis: float = None,
    wn2_heavy_snow: bool = False,
    wn2_storm_slab: bool = False,
    wn2_wind_strong: bool = False,
    wn2_probable_avalanche_problem: str = None,
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

    # CR-10A: precipitación efectiva — usa precipitacion_72h_mm/3 cuando
    # precipitacion_actual es 0 (ERA5 instantáneo a 12:00 UTC, frecuentemente 0
    # incluso en días con precipitación real). Umbral ERA5 reducido para Alpes.
    # NOTA FIX-CR16A (revertido R11): restringir a Alpes empeoró sesgo +0.770→+1.023
    # porque S5 se apoya más en S1 (topográfico) cuando S3 entrega señal neutral.
    # La causa real del sesgo es v7.5/S1 + integración S5, no este fallback.
    _precip_diaria_72h = (precipitacion_72h_mm or 0) / 3
    precip_efectiva = precipitacion_actual_mm if precipitacion_actual_mm > 0 else _precip_diaria_72h
    if _precip_diaria_72h > precipitacion_actual_mm:
        logger.info(
            f"[VentanasCriticas] CR-10A: precip_efectiva={precip_efectiva:.1f}mm "
            f"(actual={precipitacion_actual_mm}mm, 72h/3={_precip_diaria_72h:.1f}mm, "
            f"region={_region})"
        )

    # FIX-HN24-PROMO (v20.0): promover HN24 (IMIS) a precip_efectiva cuando supere ERA5.
    # HN24 (medición directa) es más preciso que ERA5@9km en Alpes.
    # Guard _es_alpes: solo Alpes por ahora (Fase F extiende extracción, actualizar si se añade IMIS Andes).
    # 1 cm nieve fresca (densidad 100 kg/m³) ≈ 1 mm SWE.
    if _es_alpes and nieve_nueva_cm_imis is not None and nieve_nueva_cm_imis > 0:
        precip_hn24_mm = nieve_nueva_cm_imis * 1.0  # 100 kg/m³ / 100 = 1 mm/cm
        if precip_hn24_mm > precip_efectiva:
            logger.info(
                f"[VentanasCriticas] FIX-HN24-PROMO: precip_efectiva "
                f"{precip_efectiva:.1f}→{precip_hn24_mm:.1f}mm (HN24={nieve_nueva_cm_imis}cm)"
            )
            precip_efectiva = precip_hn24_mm

    _umbral_nevada     = 2.0  if _es_alpes else 5.0
    _umbral_lluvia     = 1.5  if _es_alpes else 3.0
    _umbral_carga_72h  = 5.0  if _es_alpes else 10.0

    # CR-10B recalibrado (FIX-WIND-UNITS): ERA5 velocidad_viento ahora en m/s reales.
    # Análisis de 30 pares validación Suiza 2018-2020: estaciones de valle (Interlaken
    # 1200m, St Moritz 1900m, Matterhorn 2600m), ratio IMIS/ERA5 ≈ 1.0 (no 1.4 de cresta).
    # Max ERA5 en dataset = 5.22 m/s → umbral 7 m/s apagaba toda señal de viento.
    # Umbral 3 m/s: activa 4/30 días, todos GT≥3 (100% precisión). Señal limpia.
    _umbral_viento_fuerte         = 3.0  if _es_alpes else 10.0
    _umbral_viento_redistribucion = 3.0  if _es_alpes else 15.0

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

    # ─── Ventana FIX-CR19: Carga de nieve profunda (IMIS HN24) ──────────────
    # nieve_nueva_cm_imis es la medición directa del pluviómetro IMIS (HN24).
    # ERA5@9km subestima la precipitación local; HN24≥25cm indica tormenta D3+
    # en terreno alpino → segunda ventana crítica → activa CH-2/CH-3.
    # Guard: solo Alpes (Andes no tiene backfill IMIS).
    if (
        _es_alpes
        and nieve_nueva_cm_imis is not None
        and nieve_nueva_cm_imis >= 25
        and temperatura_actual_C is not None
        and temperatura_actual_C <= 0
    ):
        logger.info(
            f"[VentanasCriticas] FIX-CR19: CARGA_NIEVE_PROFUNDA "
            f"(HN24={nieve_nueva_cm_imis:.1f}cm, T={temperatura_actual_C:.1f}°C)"
        )
        ventanas.append({
            "tipo": "CARGA_NIEVE_PROFUNDA",
            "severidad": "muy_alta",
            "descripcion": (
                f"Nieve nueva IMIS: {nieve_nueva_cm_imis:.0f}cm en 24h (HN24). "
                "Carga extrema sobre manto existente: riesgo de aludes de nieve reciente "
                "y placas de viento en terreno ≥ 30°."
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

    # ─── Ventana FIX-WN2-TRIGGERS (v20.0): señales WN2 ensemble ─────────────
    # WeatherNext 2 (64 miembros DeepMind) detecta tormentas con mayor resolución
    # que ERA5@9km. Cuando S3 obtuvo WN2 disponible=true, pasa alertas como params.
    # Guard implícito: solo se activan cuando los bools son True — S3 solo los pasa
    # cuando wn2.disponible=true. Sin parámetros (default False) → sin efecto.
    # No se añaden ventanas duplicadas si ERA5 ya detectó el mismo evento.
    _tipos_actuales = {v["tipo"] for v in ventanas}

    if wn2_heavy_snow and "NEVADA_MAS_VIENTO" not in _tipos_actuales and "CARGA_NIEVE_PROFUNDA" not in _tipos_actuales:
        logger.info(
            f"[VentanasCriticas] FIX-WN2-TRIGGERS: nevada confirmada por WN2 ensemble "
            f"(heavy_snow=True, prob_problem={wn2_probable_avalanche_problem})"
        )
        ventanas.append({
            "tipo": "NEVADA_WN2_CONFIRMADA",
            "severidad": "muy_alta",
            "descripcion": (
                "WeatherNext 2 ensemble (64 miembros) confirma precipitación nívea intensa "
                "no captada por ERA5 — probable acumulación de nieve nueva y formación de placas."
            ),
            "tiempo": "próximo"
        })

    if wn2_storm_slab and "NEVADA_MAS_VIENTO" not in _tipos_actuales and "PLACA_VIENTO_WN2" not in _tipos_actuales:
        logger.info(
            f"[VentanasCriticas] FIX-WN2-TRIGGERS: placa de viento confirmada por WN2 ensemble "
            f"(storm_slab=True)"
        )
        ventanas.append({
            "tipo": "PLACA_VIENTO_WN2",
            "severidad": "muy_alta",
            "descripcion": (
                "WeatherNext 2 ensemble confirma problema de placa de viento — "
                "viento + nieve activos o inminentes subestimados por ERA5."
            ),
            "tiempo": "próximo"
        })

    if wn2_wind_strong and "VIENTO_FUERTE_REDISTRIBUCION" not in _tipos_actuales and not viento_fuerte:
        logger.info(
            f"[VentanasCriticas] FIX-WN2-TRIGGERS: viento fuerte confirmado por WN2 ensemble "
            f"(wind_strong=True)"
        )
        ventanas.append({
            "tipo": "VIENTO_WN2_FUERTE",
            "severidad": "alta",
            "descripcion": (
                "WeatherNext 2 ensemble confirma viento fuerte subestimado por ERA5 — "
                "transporte eólico activo o inminente con riesgo de formación de placas."
            ),
            "tiempo": "próximo"
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

    # FIX-WN2-TRIGGERS: tipos WN2 promovidos a factores EAWS cuando ERA5 no los detectó
    if "NEVADA_WN2_CONFIRMADA" in tipos_ventanas:
        if "NEVADA_RECIENTE" not in factores and "PRECIPITACION_CRITICA" not in factores:
            factores.append("NEVADA_RECIENTE")
    if "PLACA_VIENTO_WN2" in tipos_ventanas:
        if "VIENTO_FUERTE" not in factores:
            factores.append("VIENTO_FUERTE")

    return "+".join(factores) if factores else "ESTABLE"
