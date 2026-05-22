"""
Tool: clasificar_riesgo_eaws_integrado

Clasifica el riesgo EAWS final integrando los análisis de los tres
subagentes anteriores (topográfico, satelital, meteorológico) y
aplicando la matriz EAWS oficial.
"""

import sys
import os

_ROOT = os.path.join(os.path.dirname(__file__), '../../../..')  # → snow_alert/
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'datos'))  # → snow_alert/datos/ (dev local)

import logging

from analizador_avalanchas.eaws_constantes import (
    consultar_matriz_eaws,
    estimar_tamano_potencial,
    CLASES_ESTABILIDAD,
    CLASES_FRECUENCIA,
    CLASES_TAMANO,
    NIVELES_PELIGRO
)

# FIX-GEO / FIX-H (v7.0): región por ubicación para caps condicionales
try:
    from agentes.datos.constantes_zonas import obtener_region as _obtener_region
except ImportError:
    try:
        sys.path.insert(0, os.path.join(_ROOT, 'agentes'))
        from datos.constantes_zonas import obtener_region as _obtener_region
    except ImportError:
        def _obtener_region(zona: str) -> str:  # type: ignore[misc]
            return "andes_chile"

# FIX-CALIB-REG (Fase D, v21.0): calibración estadística post-LLM
try:
    from agentes.validacion.calibrador import aplicar_calibracion_regional as _calibrar_nivel
except ImportError:
    try:
        from validacion.calibrador import aplicar_calibracion_regional as _calibrar_nivel
    except ImportError:
        def _calibrar_nivel(nivel: int, region: str) -> int:  # type: ignore[misc]
            return nivel

logger = logging.getLogger(__name__)


TOOL_CLASIFICAR_EAWS_INTEGRADO = {
    "name": "clasificar_riesgo_eaws_integrado",
    "description": (
        "Clasifica el riesgo EAWS final (niveles 1-5) integrando los "
        "análisis topográfico (PINN), satelital (ViT) y meteorológico. "
        "Determina los 3 factores EAWS (estabilidad, frecuencia, tamaño) "
        "a partir del contexto acumulado y consulta la matriz EAWS oficial. "
        "Produce clasificaciones para 24h, 48h y 72h."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "estabilidad_topografica": {
                "type": "string",
                "description": "Estabilidad EAWS del subagente topográfico: very_poor, poor, fair, good"
            },
            "estabilidad_satelital": {
                "type": "string",
                "description": "Estabilidad EAWS del subagente satelital: very_poor, poor, fair, good"
            },
            "factor_meteorologico": {
                "type": "string",
                "description": "Factor meteorológico EAWS: PRECIPITACION_CRITICA, NEVADA_RECIENTE, VIENTO_FUERTE, FUSION_ACTIVA_CON_CARGA, CICLO_DIURNO_NORMAL (neutro), ESTABLE o combinación"
            },
            "frecuencia_topografica": {
                "type": "string",
                "description": "Frecuencia EAWS ajustada del subagente topográfico: many, some, a_few, nearly_none"
            },
            "tamano_eaws": {
                "type": "string",
                "description": "Tamaño EAWS de la zona: 1, 2, 3, 4, 5"
            },
            "ventanas_criticas_detectadas": {
                "type": "integer",
                "description": "Número de ventanas críticas meteorológicas detectadas"
            },
            "viento_kmh": {
                "type": "number",
                "description": "Velocidad del viento en km/h (para ajuste de frecuencia)"
            },
            "desnivel_inicio_deposito_m": {
                "type": "number",
                "description": "Desnivel vertical entre zona inicio y depósito en metros (para cálculo dinámico de tamaño)"
            },
            "zona_inicio_ha": {
                "type": "number",
                "description": "Hectáreas de zona de inicio de avalanchas (para cálculo dinámico de tamaño)"
            },
            "pendiente_max_grados": {
                "type": "number",
                "description": "Pendiente máxima en grados (para cálculo dinámico de tamaño)"
            },
            "tendencia_pronostico": {
                "type": "string",
                "description": "Tendencia meteorológica del pronóstico 3 días: empeorando, estable, mejorando"
            },
            "dias_consecutivos_nivel_bajo": {
                "type": "integer",
                "description": "Días consecutivos con nivel ≤ 2 (de obtener_historial_ubicacion). Si ≥ 4 y factor ESTABLE, confirma calma sostenida."
            },
            "nombre_ubicacion": {
                "type": "string",
                "description": "Nombre de la ubicación analizada (e.g. 'La Parva Sector Alto', 'Interlaken'). Usado para aplicar caps y defaults condicionales por región (FIX-GEO/FIX-H v7.0)."
            },
            "condiciones_meteo_disponibles": {
                "type": "boolean",
                "description": "v7.5: True si S3 reportó datos meteorológicos reales (temperatura, precipitación, viento medidos). False o ausente cuando S3 no tuvo datos (e.g. runs retroactivos sin condiciones_actuales). EAWS Paso 1 solo se activa con True."
            },
            "nieve_nueva_cm_imis": {
                "type": "number",
                "description": "v20.0 FIX-HN24-SIZE: nieve nueva en 24h según medición directa IMIS (HN24_cm). Solo disponible en Alpes suizos. Permite graduación de tamaño D3/D4/D5 según Techel 2022 Tabla 7 (25→D3, 40→D4, 60→D5). Pasar solo si S3 reportó nieve_nueva_cm con fuente IMIS."
            },
            "precipitacion_72h_corregida_mm": {
                "type": "number",
                "description": "v20.0 FIX-CR7A-REFACTOR: precipitación acumulada 72h con corrección orográfica aplicada (correccion_orografica.py). Usado para evaluar calma confirmada en Andes Chile (< 5mm es condición necesaria para habilitar EAWS Paso 1). Pasar si S3 lo reporta."
            },
            "nieve_nueva_cm_wn2": {
                "type": "number",
                "description": "v25.0 FIX-WN2-SIZE-ANDES: nieve nueva en 24h estimada por WeatherNext 2 (nieve_24h_cm_p50_corr). Análogo a nieve_nueva_cm_imis (IMIS/Alpes) pero para Andes Chile. Permite graduación de tamaño D3/D4/D5 (umbrales: 25→D3, 40→D4, 60→D5) cuando la tormenta está activa. Pasar cuando S1 usó nieve_nueva_cm en PINN."
            }
        },
        "required": [
            "estabilidad_topografica",
            "factor_meteorologico"
        ]
    }
}


# Mapa de factores meteorológicos a ajuste de estabilidad
_AJUSTE_METEOROLOGICO = {
    "PRECIPITACION_CRITICA": "very_poor",
    "LLUVIA_SOBRE_NIEVE":    "very_poor",
    "NEVADA_RECIENTE+FUSION_ACTIVA_CON_CARGA": "very_poor",
    "NEVADA_RECIENTE+VIENTO_FUERTE": "poor",
    "NEVADA_RECIENTE":           "poor",
    "VIENTO_FUERTE":             "poor",
    "FUSION_ACTIVA_CON_CARGA":   "poor",   # REQ-06: ciclo térmico + carga reciente
    "FUSION_ACTIVA":             "poor",   # compatibilidad retroactiva
    "CICLO_FUSION_CONGELACION":  "poor",   # compatibilidad retroactiva
    "CICLO_DIURNO_NORMAL":       None,     # REQ-06: fenómeno geográfico neutro, sin ajuste
    "ESTABLE":                   None,     # Sin ajuste
}

# Factores que NO son activos para la lógica de calma sostenida (REQ-06)
_FACTORES_NEUTROS = frozenset({"ESTABLE", "CICLO_DIURNO_NORMAL", ""})


def ejecutar_clasificar_riesgo_eaws_integrado(
    estabilidad_topografica: str,
    factor_meteorologico: str,
    estabilidad_satelital: str = None,
    frecuencia_topografica: str = None,
    tamano_eaws: str = None,
    ventanas_criticas_detectadas: int = 0,
    viento_kmh: float = None,
    desnivel_inicio_deposito_m: float = None,
    zona_inicio_ha: float = None,
    pendiente_max_grados: float = None,
    tendencia_pronostico: str = None,
    dias_consecutivos_nivel_bajo: int = 0,
    nombre_ubicacion: str = None,
    condiciones_meteo_disponibles: bool = None,
    nieve_nueva_cm_imis: float = None,
    precipitacion_72h_corregida_mm: float = None,
    nieve_nueva_cm_wn2: float = None,
) -> dict:
    """
    Clasifica el riesgo EAWS integrando los análisis de todos los subagentes.

    Args:
        estabilidad_topografica: clasificación EAWS del análisis topográfico
        factor_meteorologico: factor del análisis meteorológico
        estabilidad_satelital: clasificación EAWS del análisis satelital
        frecuencia_topografica: frecuencia EAWS del subagente topográfico
        tamano_eaws: tamaño EAWS explícito (1-5), se calcula dinámicamente si no se provee
        ventanas_criticas_detectadas: número de ventanas críticas
        viento_kmh: velocidad del viento en km/h (incrementa frecuencia si >40)
        desnivel_inicio_deposito_m: desnivel vertical para cálculo dinámico de tamaño
        zona_inicio_ha: hectáreas de zona de inicio para cálculo dinámico de tamaño
        pendiente_max_grados: pendiente máxima para cálculo dinámico de tamaño

    Returns:
        dict con nivel EAWS 24h/48h/72h, factores y recomendaciones
    """
    # ─── FIX-CR7A-REFACTOR (v20.0): compuerta condicional en Andes Chile ──────
    # Reemplaza el bloqueo absoluto de CR-7A (v9.0) por una compuerta basada en
    # señales positivas de calma. ERA5 retroactivo sigue rechazado salvo que tres
    # señales independientes (precip corregida, viento, calma sostenida) respalden.
    # Criterio: habilitar EAWS Paso 1 SOLO cuando todas las condiciones de calma se
    # satisfacen simultáneamente, evitando falsos negativos en días de tormenta.
    _region_meteo = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    if _region_meteo == "andes_chile" and condiciones_meteo_disponibles is True:
        _precip_ok = precipitacion_72h_corregida_mm is not None and precipitacion_72h_corregida_mm < 5
        _viento_ok = viento_kmh is not None and viento_kmh < 30
        senales_calma_confirmada = (
            factor_meteorologico in _FACTORES_NEUTROS
            and ventanas_criticas_detectadas == 0
            and _precip_ok
            and _viento_ok
            and dias_consecutivos_nivel_bajo >= 2
        )
        if not senales_calma_confirmada:
            logger.info(
                f"[ClasificarEAWS] FIX-CR7A-REFACTOR: Andes sin calma confirmada "
                f"→ condiciones_meteo_disponibles=False "
                f"(factor={factor_meteorologico}, p72h_corr={precipitacion_72h_corregida_mm}, "
                f"viento={viento_kmh}, dias_bajo={dias_consecutivos_nivel_bajo}, "
                f"ventanas={ventanas_criticas_detectadas})"
            )
            condiciones_meteo_disponibles = False
        else:
            logger.info(
                f"[ClasificarEAWS] FIX-CR7A-REFACTOR: Andes con calma confirmada "
                f"→ EAWS Paso 1 habilitado "
                f"(p72h_corr={precipitacion_72h_corregida_mm}mm, "
                f"viento={viento_kmh}km/h, dias_bajo={dias_consecutivos_nivel_bajo})"
            )

    # ─── CR-14 (v14.0): bloqueo EAWS Paso 1 en Alpes suizos ────────────────────
    # En Alpes, EAWS nivel 1 requiere confirmación explícita del manto nival
    # (Sclass2, pwl_100 — datos IMIS). Sin ellos, capas persistentes débiles son
    # invisibles a mediciones de superficie y el Paso 1 produce nivel 1 espurio.
    # La matriz estándar (estabilidad_pinn=poor, factor=ESTABLE) da nivel 2 → correcto.
    _paso1_bloqueado_alpes = (
        _region_meteo == "alpes_swiss"
        and condiciones_meteo_disponibles is True
    )
    if _paso1_bloqueado_alpes:
        logger.info(
            f"[ClasificarEAWS] CR-14 (v14.0): EAWS Paso 1 bloqueado en Alpes — "
            f"sin datos manto nival (Sclass2/pwl_100) → matriz estándar "
            f"(ubicacion={nombre_ubicacion})"
        )

    # ─── EAWS Paso 1 (v7.5 — gate basado en datos, no en supuestos) ─────────
    # Implementa EAWS 2025 Tabla 6 Paso 1: "no avalanche problems → level 1-Low".
    # CONDICIÓN: solo se activa cuando S3 tenía datos meteorológicos REALES que
    # permiten confirmar la ausencia de trigger. Si S3 no tuvo datos (e.g. runs
    # retroactivos donde condiciones_actuales está vacío), "sin datos" ≠ "sin trigger"
    # → se toma el camino conservador (matriz estándar).
    # Excepción: Alpes suizos bloqueados por CR-14 (sin datos de manto nival).
    _eaws_paso1 = (
        condiciones_meteo_disponibles is True
        and factor_meteorologico in _FACTORES_NEUTROS
        and ventanas_criticas_detectadas == 0
        and not _paso1_bloqueado_alpes
    )
    if _eaws_paso1:
        logger.info(
            f"[ClasificarEAWS] EAWS Paso 1 (v7.5): datos_meteo=True, "
            f"factor={factor_meteorologico}, ventanas=0 → nivel 1 directo"
        )
        return {
            "nivel_eaws_24h": 1,
            "nivel_eaws_48h": 1,
            "nivel_eaws_72h": 1,
            "nombre_nivel_24h": "Débil",
            "factores_eaws": {
                "estabilidad": "good",
                "frecuencia": "nearly_none",
                "tamano": 1,
                "fuente_tamano": "eaws_paso1_sin_problema_confirmado",
            },
            "fuentes_estabilidad": {
                "topografica_pinn": estabilidad_topografica,
                "satelital_vit": estabilidad_satelital,
                "ajuste_meteorologico": None,
            },
            "factor_meteorologico": factor_meteorologico,
            "tendencia_pronostico": tendencia_pronostico,
            "viento_kmh": viento_kmh,
            "recomendaciones": [],
            "descripcion_nivel": "Sin problemas de avalancha confirmados por datos meteorológicos (EAWS Paso 1). Manto estable con condiciones calmas.",
            "problema_avalancha_presente": False,
            "tipo_problema_eaws": "no_distinct_avalanche_problem",
        }

    # ─── 1. Determinar estabilidad dominante ─────────────────────────────────
    estabilidad_final = _determinar_estabilidad_dominante(
        estabilidad_topografica=estabilidad_topografica,
        estabilidad_satelital=estabilidad_satelital,
        factor_meteorologico=factor_meteorologico,
        dias_consecutivos_nivel_bajo=dias_consecutivos_nivel_bajo,
        nombre_ubicacion=nombre_ubicacion,
        ventanas_criticas_detectadas=ventanas_criticas_detectadas,
    )

    # ─── 2. Ajustar frecuencia ───────────────────────────────────────────────
    frecuencia_final = _determinar_frecuencia(
        frecuencia_topografica=frecuencia_topografica,
        ventanas_criticas=ventanas_criticas_detectadas,
        factor_meteorologico=factor_meteorologico,
        estabilidad=estabilidad_final,
        viento_kmh=viento_kmh,
        nombre_ubicacion=nombre_ubicacion,
    )

    # ─── 3. Determinar tamaño (dinámico desde topografía si es posible) ──────
    tamano_final, fuente_tamano = _determinar_tamano(
        tamano_eaws=tamano_eaws,
        desnivel_inicio_deposito_m=desnivel_inicio_deposito_m,
        zona_inicio_ha=zona_inicio_ha,
        pendiente_max_grados=pendiente_max_grados
    )

    # FIX-HN24-SIZE (v20.0): graduación de tamaño por HN24 IMIS (D3/D4/D5).
    # Reemplaza FIX-CR18-CH-3 (boost binario) por umbrales escalonados según Techel 2022 Tabla 7.
    # Guard region=alpes_swiss: La Parva no tiene IMIS → nieve_nueva_cm_imis siempre None en Andes.
    # Outlier filter: nieve_nueva_cm_imis validada en consultor_bigquery.py (0–200cm).
    _region = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    if _region == "alpes_swiss":
        if nieve_nueva_cm_imis is not None and nieve_nueva_cm_imis > 0:
            # Escala graduada por medición directa HN24
            if   nieve_nueva_cm_imis >= 60: tamano_min_hn24 = 5
            elif nieve_nueva_cm_imis >= 40: tamano_min_hn24 = 4
            elif nieve_nueva_cm_imis >= 25: tamano_min_hn24 = 3
            else:                            tamano_min_hn24 = 0
            if tamano_min_hn24 > tamano_final:
                logger.info(
                    f"[ClasificarEAWS] FIX-HN24-SIZE: tamano "
                    f"{tamano_final}→{tamano_min_hn24} (HN24={nieve_nueva_cm_imis}cm)"
                )
                tamano_final = tamano_min_hn24
                fuente_tamano = f"{fuente_tamano}→hn24_grad"
        elif (
            "NEVADA_RECIENTE" in factor_meteorologico
            and ventanas_criticas_detectadas >= 2
            and tamano_final < 3
        ):
            # Fallback CR18-CH-3: sin HN24 IMIS disponible, usar el comportamiento anterior
            logger.info(
                f"[ClasificarEAWS] FIX-HN24-SIZE fallback (sin HN24): tamano mínimo 3 "
                f"(original={tamano_final}, factor={factor_meteorologico}, "
                f"ventanas={ventanas_criticas_detectadas})"
            )
            tamano_final = 3
            fuente_tamano = f"{fuente_tamano}→min3_cr18ch3_fallback"

    # FIX-WN2-SIZE-ANDES (v25.0): graduación de tamaño por pronóstico ensemble WN2 (Andes Chile).
    # Análogo a FIX-HN24-SIZE pero usando nieve_24h_cm_p50_corr de WeatherNext 2 en lugar de IMIS.
    # Guard: solo cuando factor de tormenta activo (evita falsos positivos en calma).
    # Umbrales Techel 2022 Tabla 7: 25cm→D3, 40cm→D4, 60cm→D5.
    # Schweizer et al. (2003): carga nívea ≥ 25cm/24h sobre pendientes >28° → avalancha de placa.
    _factor_activo_tamano_pre = bool(
        factor_meteorologico and factor_meteorologico not in _FACTORES_NEUTROS
    )
    if _region == "andes_chile" and nieve_nueva_cm_wn2 is not None and nieve_nueva_cm_wn2 > 0:
        if _factor_activo_tamano_pre:
            if   nieve_nueva_cm_wn2 >= 60: tamano_min_wn2 = 5
            elif nieve_nueva_cm_wn2 >= 40: tamano_min_wn2 = 4
            elif nieve_nueva_cm_wn2 >= 25: tamano_min_wn2 = 3
            else:                           tamano_min_wn2 = 0
            if tamano_min_wn2 > tamano_final:
                logger.info(
                    f"[ClasificarEAWS] FIX-WN2-SIZE-ANDES: tamano "
                    f"{tamano_final}→{tamano_min_wn2} (WN2_nieve={nieve_nueva_cm_wn2:.0f}cm)"
                )
                tamano_final = tamano_min_wn2
                fuente_tamano = f"{fuente_tamano}→wn2_size_andes"

    # FIX-T+FIX-GEO (v7.0): cap tamano≤3 en condiciones calmas, solo en Andes Chile.
    # FIX-T (v6.2): en días sin factor activo ni ventanas críticas, el terreno andino
    #   de alta pendiente (desnivel/ha) sobreestima el tamaño posible.
    # FIX-GEO (v7.0): este cap solo aplica en Andes Chile. En Alpes suizos, ERA5/SLF
    #   reflejan las condiciones reales y el cap produce subestimación sistemática.
    _factor_activo_tamano = bool(
        factor_meteorologico and factor_meteorologico not in _FACTORES_NEUTROS
    )
    if (
        _region == "andes_chile"
        and tamano_final > 3
        and not _factor_activo_tamano
        and ventanas_criticas_detectadas < 2
    ):
        logger.info(
            f"[ClasificarEAWS] FIX-T+FIX-GEO: tamano capado {tamano_final}→3 "
            f"(region={_region}, factor={factor_meteorologico}, ventanas={ventanas_criticas_detectadas})"
        )
        tamano_final = 3
        fuente_tamano = f"{fuente_tamano}→cap_calmo"

    # FIX-CR7C (v8.0): cap adicional para tamano EXPLÍCITO en Andes Chile con factor neutro.
    # Cuando S5 provee tamano_eaws=4/5 basado en área topográfica pero el factor es neutro,
    # el LLM sobreestima el tamaño posible. Este cap es independiente de ventanas_criticas
    # (defensa en profundidad vs CR-7b donde vc inflado bloqueaba el cap anterior).
    if (
        fuente_tamano == "explicito"
        and _region == "andes_chile"
        and tamano_final > 3
        and not _factor_activo_tamano
    ):
        logger.info(
            f"[ClasificarEAWS] FIX-CR7C: tamano explícito capado {tamano_final}→3 "
            f"(region={_region}, fuente=explicito, factor_neutro)"
        )
        tamano_final = 3
        fuente_tamano = "explicito→cap_cr7c"

    # ─── 4. Consultar matriz EAWS ─────────────────────────────────────────────
    # consultar_matriz_eaws devuelve Tuple[int, Optional[int]] → (D1, D2)
    nivel_d1, nivel_d2 = consultar_matriz_eaws(
        estabilidad=estabilidad_final,
        frecuencia=frecuencia_final,
        tamano=tamano_final
    )
    nivel_24h = nivel_d1  # Nivel primario

    # Información del nivel desde NIVELES_PELIGRO
    info_nivel = NIVELES_PELIGRO.get(nivel_24h, {})

    # ─── 5. Proyección 48h y 72h ─────────────────────────────────────────────
    nivel_48h = _proyectar_nivel(nivel_24h, factor_meteorologico, horas=48, tendencia_pronostico=tendencia_pronostico)
    nivel_72h = _proyectar_nivel(nivel_24h, factor_meteorologico, horas=72, tendencia_pronostico=tendencia_pronostico)

    # ─── 6. Recomendaciones EAWS ─────────────────────────────────────────────
    recomendaciones = []
    if ventanas_criticas_detectadas > 0:
        recomendaciones.append(
            f"Se detectaron {ventanas_criticas_detectadas} ventanas criticas "
            "meteorologicas — monitoreo continuo recomendado"
        )
    if viento_kmh and viento_kmh > 40:
        recomendaciones.append(
            f"Viento fuerte detectado ({viento_kmh:.0f} km/h) — "
            "transporte eolico activo incrementa frecuencia de avalanchas"
        )

    # FIX-CALIB-REG (Fase D, v21.0): calibración estadística post-LLM.
    # Aplica α+β·nivel por región solo si los gates estadísticos se aprobaron
    # en el entrenamiento offline (coeficientes_calibracion.json).
    # Si el JSON no existe o la región no fue aprobada, retorna identidad.
    _region_cal = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    nivel_24h_raw = nivel_24h
    nivel_48h_raw = nivel_48h
    nivel_72h_raw = nivel_72h
    nivel_24h = _calibrar_nivel(nivel_24h, _region_cal)
    nivel_48h = _calibrar_nivel(nivel_48h, _region_cal)
    nivel_72h = _calibrar_nivel(nivel_72h, _region_cal)
    info_nivel = NIVELES_PELIGRO.get(nivel_24h, info_nivel)

    return {
        "nivel_eaws_24h": nivel_24h,
        "nivel_eaws_24h_raw": nivel_24h_raw,
        "nivel_eaws_48h": nivel_48h,
        "nivel_eaws_72h": nivel_72h,
        "nombre_nivel_24h": info_nivel.get("nombre"),
        "factores_eaws": {
            "estabilidad": estabilidad_final,
            "frecuencia": frecuencia_final,
            "tamano": tamano_final,
            "fuente_tamano": fuente_tamano
        },
        "fuentes_estabilidad": {
            "topografica_pinn": estabilidad_topografica,
            "satelital_vit": estabilidad_satelital,
            "ajuste_meteorologico": _obtener_ajuste_meteorologico(factor_meteorologico)
        },
        "factor_meteorologico": factor_meteorologico,
        "tendencia_pronostico": tendencia_pronostico,
        "viento_kmh": viento_kmh,
        "recomendaciones": recomendaciones,
        "descripcion_nivel": info_nivel.get("descripcion", ""),
        "problema_avalancha_presente": None,
        "tipo_problema_eaws": None,
    }


def _determinar_estabilidad_dominante(
    estabilidad_topografica: str,
    estabilidad_satelital: str,
    factor_meteorologico: str,
    dias_consecutivos_nivel_bajo: int = 0,
    nombre_ubicacion: str = None,
    ventanas_criticas_detectadas: int = 0,
) -> str:
    """
    Determina la estabilidad dominante combinando todas las fuentes.

    Reglas:
    - Si el factor meteorológico implica una estabilidad peor → prioridad
    - Si las fuentes topo y satelital difieren → tomar la peor
    - Si calma sostenida confirmada (días_nivel_bajo ≥ 4 y factor ESTABLE) → cap en 'fair'
      para evitar el piso artificial en nivel 3 causado por topografía estática del PINN.
    """
    escala = ["good", "fair", "poor", "very_poor"]

    # Estabilidad base: la peor entre topo y satelital
    idx_topo = escala.index(estabilidad_topografica) if estabilidad_topografica in escala else 1

    # FIX-H (v7.0): cuando ViT no tiene datos, el default de estabilidad satelital
    # depende de la región. En Andes Chile, ViT fue entrenado aquí → default 'fair'.
    # En Alpes suizos, ViT no tiene datos de entrenamiento → default conservador 'poor'.
    if estabilidad_satelital in escala:
        idx_sat = escala.index(estabilidad_satelital)
    else:
        _region_sat = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
        _default_sat = "fair" if _region_sat == "andes_chile" else "poor"
        idx_sat = escala.index(_default_sat)
        logger.info(
            f"[ClasificarEAWS] FIX-H: estabilidad_satelital='{estabilidad_satelital}' → "
            f"default '{_default_sat}' (region={_region_sat})"
        )
    idx_base = max(idx_topo, idx_sat)

    _factor_activo = bool(
        factor_meteorologico
        and factor_meteorologico not in _FACTORES_NEUTROS
    )

    # FIX-CR17A (v17.0): en Andes Chile la topografía siempre reporta 'poor' porque
    # el PINN refleja el terreno potencial (pendientes >35°, desnivel >600m). Sin embargo,
    # la estabilidad topográfica es riesgo POTENCIAL, no ACTIVO. Sin trigger meteorológico
    # ni ventanas críticas, la matriz EAWS no debe superar nivel 2. Capeamos idx_base en
    # 'fair' para que max(fair, fair_sat_default) = 'fair' → matriz → nivel ≤ 2.
    # No aplica a Alpes (guard de región) ni cuando hay trigger activo.
    _region_dom = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    if (
        _region_dom == "andes_chile"
        and not _factor_activo
        and ventanas_criticas_detectadas == 0
        and idx_base > 1  # solo si la base es peor que 'fair'
    ):
        logger.info(
            f"[ClasificarEAWS] FIX-CR17A: Andes sin trigger → estabilidad base capada "
            f"'fair' (original={escala[idx_base]}, factor={factor_meteorologico}, "
            f"ventanas={ventanas_criticas_detectadas})"
        )
        idx_base = 1  # 'fair'

    # Ajuste meteorológico
    ajuste_meteo = _obtener_ajuste_meteorologico(factor_meteorologico)
    if ajuste_meteo and ajuste_meteo in escala:
        idx_meteo = escala.index(ajuste_meteo)
        idx_final = max(idx_base, idx_meteo)
    else:
        idx_final = idx_base

    # Confirmación de calma sostenida: si ≥ 4 días consecutivos nivel ≤ 2 y sin
    # factor meteorológico activo, el PINN topográfico puede estar sobreestimando.
    # Cap en 'fair' (índice 1) para evitar piso artificial en nivel 3.
    # REQ-06: CICLO_DIURNO_NORMAL es neutro (igual que ESTABLE) para la lógica de calma
    if dias_consecutivos_nivel_bajo >= 4 and not _factor_activo:
        idx_final = min(idx_final, 1)  # cap en 'fair'
        logger.info(
            f"[ClasificarEAWS] Calma sostenida confirmada ({dias_consecutivos_nivel_bajo} días "
            f"nivel≤2, factor={factor_meteorologico}) — estabilidad capada en 'fair'"
        )

    return escala[idx_final]


def _obtener_ajuste_meteorologico(factor_meteorologico: str) -> str:
    """Obtiene el ajuste de estabilidad del factor meteorológico."""
    for patron, ajuste in _AJUSTE_METEOROLOGICO.items():
        if patron in factor_meteorologico:
            return ajuste
    return None


def _determinar_frecuencia(
    frecuencia_topografica: str,
    ventanas_criticas: int,
    factor_meteorologico: str,
    estabilidad: str,
    viento_kmh: float = None,
    nombre_ubicacion: str = None,
) -> str:
    """
    Determina la frecuencia EAWS final.

    Incorpora viento como factor directo: viento >40 km/h incrementa
    la clase de frecuencia en 1 (transporte eólico activo redistribuye
    nieve hacia zonas de acumulación, aumentando probabilidad de
    desprendimiento).
    """
    escala = ["nearly_none", "a_few", "some", "many"]

    idx_base = escala.index(frecuencia_topografica) if frecuencia_topografica in escala else 1

    # Ajuste por ventanas críticas.
    # FIX-CR18-CH-2 (v18.0): en Alpes suizos con NEVADA_RECIENTE activa, bajar el
    # umbral de >=3 a >=2. Durante nevadas intensas (HN24 >30cm), 2 ventanas EAWS
    # ya reflejan condiciones de alta frecuencia de desprendimiento (D3+).
    _region_freq = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
    _vc_threshold = (
        2
        if (_region_freq == "alpes_swiss" and "NEVADA_RECIENTE" in factor_meteorologico)
        else 3
    )
    if ventanas_criticas >= _vc_threshold:
        logger.info(
            f"[ClasificarEAWS] FIX-CR18-CH-2: frecuencia boost por ventanas "
            f"({ventanas_criticas}>={_vc_threshold}, region={_region_freq}, "
            f"factor={factor_meteorologico})"
        )
        idx_base = min(3, idx_base + 1)

    # Ajuste por viento fuerte (C3: >40 km/h → transporte eólico activo)
    if viento_kmh and viento_kmh > 40:
        idx_base = min(3, idx_base + 1)
        if viento_kmh > 70:
            # Viento extremo → sube otro nivel más
            idx_base = min(3, idx_base + 1)

    # Ajuste por estabilidad: si very_poor → frecuencia sube
    if estabilidad == "very_poor" and idx_base < 2:
        idx_base = 2  # Al menos "some"

    # FIX-STORM-FREQ-WN2 (v25.0): tormenta extrema confirmada → frecuencia "many".
    # Cuando manto CRITICO (very_poor) + señal NEVADA_RECIENTE activa + al menos 1 ventana,
    # todos los terrenos >28° se movilizan simultáneamente (Schweizer et al. 2003, §4.2).
    # Solo Andes Chile; en Alpes el mecanismo equivalente es FIX-CR18-CH-2 + IMIS.
    if (
        _region_freq == "andes_chile"
        and estabilidad == "very_poor"
        and "NEVADA_RECIENTE" in factor_meteorologico
        and ventanas_criticas >= 1
    ):
        idx_base = 3  # many
        logger.info(
            f"[ClasificarEAWS] FIX-STORM-FREQ-WN2: tormenta extrema confirmada "
            f"(very_poor + NEVADA_RECIENTE + ventanas={ventanas_criticas}) → frecuencia=many"
        )

    # Ajuste por factor meteorológico de precipitación crítica
    if "PRECIPITACION_CRITICA" in factor_meteorologico:
        idx_base = min(3, idx_base + 1)

    return escala[idx_base]


def _determinar_tamano(
    tamano_eaws: str = None,
    desnivel_inicio_deposito_m: float = None,
    zona_inicio_ha: float = None,
    pendiente_max_grados: float = None
) -> tuple:
    """
    Determina el tamaño EAWS dinámicamente usando estimar_tamano_potencial()
    cuando hay datos topográficos disponibles.

    Returns:
        tuple: (tamano_int, fuente_str)
    """
    # Si se pasó explícitamente un tamaño, usarlo (acepta entero o string)
    if tamano_eaws and str(tamano_eaws) in ["1", "2", "3", "4", "5"]:
        return int(tamano_eaws), "explicito"

    # Calcular dinámicamente si hay datos topográficos suficientes
    if desnivel_inicio_deposito_m is not None and desnivel_inicio_deposito_m > 0:
        ha = zona_inicio_ha if zona_inicio_ha and zona_inicio_ha > 0 else 25.0
        pendiente = pendiente_max_grados if pendiente_max_grados and pendiente_max_grados > 0 else 38.0

        tamano = estimar_tamano_potencial(
            desnivel_inicio_deposito=desnivel_inicio_deposito_m,
            ha_zona_inicio=ha,
            pendiente_max=pendiente
        )
        logger.info(
            f"Tamaño EAWS calculado dinámicamente: {tamano} "
            f"(desnivel={desnivel_inicio_deposito_m}m, ha={ha}, pendiente={pendiente}°)"
        )
        return tamano, "estimar_tamano_potencial"

    # Fallback: default 2 (mediano)
    return 2, "default"


def _proyectar_nivel(
    nivel_24h: int,
    factor_meteorologico: str,
    horas: int,
    tendencia_pronostico: str = None
) -> int:
    """
    Proyecta el nivel EAWS para 48h y 72h.

    Incorpora tendencia_pronostico (empeorando/estable/mejorando) para
    proyecciones más realistas. Sin tendencia, aplica reglas conservadoras
    por factor meteorológico.

    Reglas por factor:
    - PRECIPITACION_CRITICA / LLUVIA_SOBRE_NIEVE: sube en 48h, depende de tendencia en 72h
    - FUSION_ACTIVA / CICLO_FUSION_CONGELACION: mantiene ambos días salvo mejora confirmada
    - NEVADA_RECIENTE + VIENTO: mantiene en 48h, puede bajar en 72h si mejora
    - ESTABLE: mantiene en 48h, baja 1 en 72h
    - General: mantiene; si mejorando baja 1 en 72h, si empeorando sube 1 en 48h
    """
    mejorando = tendencia_pronostico == "mejorando"
    empeorando = tendencia_pronostico == "empeorando"

    # Precipitación crítica o lluvia sobre nieve → situación en aumento
    if "PRECIPITACION_CRITICA" in factor_meteorologico or "LLUVIA_SOBRE_NIEVE" in factor_meteorologico:
        if horas == 48:
            return min(5, nivel_24h + 1)
        else:  # 72h
            if mejorando:
                return max(1, nivel_24h - 1)
            return nivel_24h  # Sin mejora confirmada, mantener

    # Factor estable o ciclo diurno normal → reducción progresiva (REQ-06)
    if factor_meteorologico in ("ESTABLE", "CICLO_DIURNO_NORMAL") or factor_meteorologico not in _AJUSTE_METEOROLOGICO:
        if horas == 72:
            return max(1, nivel_24h - 1)
        return nivel_24h

    # Fusión activa con carga, ciclo fusión-congelación (compatibilidad) → persiste
    if "FUSION_ACTIVA" in factor_meteorologico or "CICLO_FUSION_CONGELACION" in factor_meteorologico:
        if horas == 48:
            if empeorando:
                return min(5, nivel_24h + 1)
            return nivel_24h  # Fusión no remite en 24h
        else:  # 72h
            if mejorando:
                return max(1, nivel_24h - 1)
            return nivel_24h  # Sin cambio de temperatura confirmado, mantener

    # Caso general (NEVADA_RECIENTE, VIENTO_FUERTE, etc.)
    if horas == 48:
        if empeorando:
            return min(5, nivel_24h + 1)
        return nivel_24h
    else:  # 72h
        if mejorando and nivel_24h > 1:
            return nivel_24h - 1
        if not empeorando and nivel_24h > 2:
            # Sin tendencia clara: reducción conservadora solo desde nivel ≥3
            return nivel_24h - 1
        return nivel_24h
