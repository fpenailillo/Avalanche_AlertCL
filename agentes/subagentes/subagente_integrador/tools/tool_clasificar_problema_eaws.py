"""
Tool: clasificar_problema_eaws

Determina el problema típico de avalancha (EAWS avalanche problem) de la zona a
partir de las señales que el pipeline ya ingiere, y estima la cota de nieve.

Hasta la v25.19 el problema publicado venía exclusivamente de
`wn2_avalanche_problem`, un CASE sobre el ensemble WeatherNext 2 que decide por
temperatura del aire a la altitud de referencia de la zona
(`ingestor_wn2.py`). El campo propio `tipo_problema_eaws` nunca se poblaba.

Eso hacía invisible el caso de lluvia sobre nieve del 25-jul-2026 en
La Parva/Farellones: Google Weather reportó RAIN_AND_SNOW y LIGHT_RAIN en el
Sector Bajo desde la 01:00, y el boletín publicó `new_snow` en los tres sectores.

Los cinco problemas típicos EAWS no tienen el mismo sustento de datos en los
Andes. Se declara explícitamente cuál es sólido y cuál es un proxy:

    nieve húmeda        observación directa del tipo de precipitación   SÓLIDO
    nieve reciente      ensemble WN2 + precipitación observada          SÓLIDO
    nieve venteada      ensemble WN2 + viento 100 m + exposición        SÓLIDO
    capa débil persist. proxy de amplitud térmica (IMIS no operacional) DÉBIL
    nieve deslizante    proxy SAR + pendiente + fusión                  PROXY

Los dos últimos nunca se emiten como dominante si compite una señal sólida, y
viajan siempre con `confianza: "baja"`.
"""

import logging
import os
import sys
from typing import Optional

_ROOT = os.path.join(os.path.dirname(__file__), '../../../..')
sys.path.insert(0, _ROOT)

logger = logging.getLogger(__name__)


# ─── Umbrales ────────────────────────────────────────────────────────────────

# Viento a 100 m que forma placa (EAWS operational guidelines: el transporte
# eólico empieza en torno a 8-10 m/s con nieve disponible)
VIENTO_TRANSPORTE_MS = 8.0

# Nieve nueva 24 h que sostiene un problema de nieve reciente (Schweizer 2003)
NIEVE_NUEVA_PROBLEMA_CM = 10.0

# Pendiente donde el manto puede reptar sobre terreno liso (Techel et al.)
PENDIENTE_GLIDING_MIN = 30.0
PENDIENTE_GLIDING_MAX = 45.0

# Gradiente térmico estándar para proyectar la cota de nieve (°C/km)
LAPSE_RATE_C_KM = 6.5

CONFIANZA_OBSERVADA = "alta"
CONFIANZA_MODELO = "media"
CONFIANZA_PROXY = "baja"


TOOL_CLASIFICAR_PROBLEMA_EAWS = {
    "name": "clasificar_problema_eaws",
    "description": (
        "Determina el problema típico de avalancha EAWS de la zona (nieve húmeda, "
        "nieve reciente, nieve venteada, capa débil persistente o nieve deslizante) "
        "y estima la cota de nieve en metros. Combina el tipo de precipitación "
        "OBSERVADO hora a hora (Google Weather), el ensemble WeatherNext 2, la "
        "humedad superficial SAR, el estado del manto del PINN y la topografía. "
        "Llamar después de las tools de los subagentes y antes de "
        "clasificar_riesgo_eaws_integrado: su salida puebla tipo_problema_eaws. "
        "Retorna problema dominante, problemas secundarios, cota de nieve, "
        "confianza y la evidencia que sustenta la decisión."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ubicacion": {
                "type": "string",
                "description": "Nombre exacto de la ubicación (ej: 'La Parva Sector Bajo')"
            },
            "fecha": {
                "type": "string",
                "description": "Fecha del boletín en ISO YYYY-MM-DD. Omitir para el día en curso."
            },
        },
        "required": ["ubicacion"]
    }
}


# ─── Núcleo determinista (sin dependencias de BigQuery) ──────────────────────

def clasificar_problemas(
    precipitacion: Optional[dict] = None,
    wn2: Optional[dict] = None,
    manto: Optional[dict] = None,
    pinn: Optional[dict] = None,
    topografia: Optional[dict] = None,
    exposicion_zona: Optional[str] = None,
) -> dict:
    """
    Decide el problema dominante y los secundarios a partir de las señales.

    Función pura: recibe los dicts tal como los devuelven
    ConsultorBigQuery.obtener_precipitacion_horaria, wn2_features.obtener(),
    tool_estado_manto, tool_calcular_pinn y el perfil topográfico.

    El orden de decisión sigue la inmediatez del proceso físico: el
    humedecimiento por lluvia actúa sobre el manto en horas, mientras que una
    capa débil persistente es un problema latente. Cuando hay lluvia observada
    sobre nieve, ese es el problema dominante aunque el ensemble prevea nevada.

    Returns:
        dict con problema_dominante, problemas_secundarios, confianza y evidencia
    """
    precipitacion = precipitacion or {}
    wn2 = wn2 or {}
    manto = manto or {}
    pinn = pinn or {}
    topografia = topografia or {}

    candidatos: list[dict] = []

    # ── Nieve húmeda ──────────────────────────────────────────────────────────
    # Prioridad 1: lluvia observada sobre el manto. Es un dato del proveedor, no
    # una inferencia por temperatura, así que la confianza es la más alta.
    if precipitacion.get("hay_lluvia_sobre_nieve"):
        candidatos.append({
            "problema": "wet_snow",
            "prioridad": 1,
            "confianza": CONFIANZA_OBSERVADA,
            "evidencia": (
                f"Lluvia observada {precipitacion.get('horas_lluvia')}h "
                f"({precipitacion.get('mm_lluvia')}mm) sobre el manto"
            ),
        })
    elif (not precipitacion.get("tipo_observado")
          and precipitacion.get("bulbo_humedo_max_c") is not None
          and precipitacion["bulbo_humedo_max_c"] > 0.5
          and (precipitacion.get("mm_total") or 0) > 0):
        # Solo cuando el proveedor no clasificó el tipo: si dijo SNOW, un pico de
        # bulbo húmedo en otra hora del día no convierte la nevada en lluvia
        # (La Parva Sector Alto, 25-jul: 19 h de nieve con máximo de 1,7 °C)
        candidatos.append({
            "problema": "wet_snow",
            "prioridad": 2,
            "confianza": CONFIANZA_MODELO,
            "evidencia": (
                f"Bulbo húmedo {precipitacion['bulbo_humedo_max_c']:.1f}°C con "
                f"precipitación: fase líquida probable"
            ),
        })
    elif wn2.get("wet_snow"):
        candidatos.append({
            "problema": "wet_snow",
            "prioridad": 3,
            "confianza": CONFIANZA_MODELO,
            "evidencia": "Alerta wet_snow del ensemble WN2",
        })
    elif _manto_humedo(manto) and _hay_fusion(pinn, manto):
        # Humedecimiento sin precipitación: fusión por radiación o temperatura
        candidatos.append({
            "problema": "wet_snow",
            "prioridad": 4,
            "confianza": CONFIANZA_MODELO,
            "evidencia": (
                f"Humedad superficial SAR (ΔVV {manto.get('sar_delta_baseline')}dB) "
                f"con fusión activa"
            ),
        })

    # ── Nieve venteada ────────────────────────────────────────────────────────
    viento_ms = _viento_ms(wn2, precipitacion)
    hay_nieve_transportable = (
        (wn2.get("nieve_24h_p50") or 0) > 0
        or (precipitacion.get("mm_nieve") or 0) > 0
    )
    if wn2.get("storm_slab") or (
        viento_ms >= VIENTO_TRANSPORTE_MS and hay_nieve_transportable
    ):
        detalle = f"Viento {viento_ms:.0f} m/s con nieve disponible"
        if exposicion_zona:
            detalle += f"; laderas a sotavento de {exposicion_zona}"
        candidatos.append({
            "problema": "wind_slab",
            "prioridad": 2,
            "confianza": CONFIANZA_MODELO,
            "evidencia": detalle,
        })

    # ── Nieve reciente ────────────────────────────────────────────────────────
    nieve_cm = wn2.get("nieve_24h_p50") or 0
    if wn2.get("heavy_snow") or nieve_cm >= NIEVE_NUEVA_PROBLEMA_CM:
        candidatos.append({
            "problema": "new_snow",
            "prioridad": 2,
            "confianza": CONFIANZA_MODELO,
            "evidencia": f"Nieve nueva {nieve_cm:.0f}cm/24h",
        })
    elif (precipitacion.get("mm_nieve") or 0) > 0 and precipitacion.get("horas_nieve", 0) >= 3:
        candidatos.append({
            "problema": "new_snow",
            "prioridad": 3,
            "confianza": CONFIANZA_OBSERVADA,
            "evidencia": (
                f"Nevada observada {precipitacion['horas_nieve']}h "
                f"({precipitacion.get('mm_nieve')}mm)"
            ),
        })

    # ── Capa débil persistente (sustento débil) ───────────────────────────────
    # Sin observación del manto en Andes: los índices IMIS de snowpack_features
    # solo existen para los Alpes. Se conserva el proxy del ensemble, marcado.
    if wn2.get("prob_problem") == "persistent_weak_layer":
        candidatos.append({
            "problema": "persistent_weak_layer",
            "prioridad": 5,
            "confianza": CONFIANZA_PROXY,
            "evidencia": "Proxy de amplitud térmica del ensemble (sin sondeo de manto)",
            "proxy": True,
        })

    # ── Nieve deslizante (proxy) ──────────────────────────────────────────────
    pendiente = topografia.get("pendiente_media_inicio")
    if (
        _manto_humedo(manto)
        and pendiente is not None
        and PENDIENTE_GLIDING_MIN <= pendiente <= PENDIENTE_GLIDING_MAX
        and nieve_cm < NIEVE_NUEVA_PROBLEMA_CM
        and _hay_fusion(pinn, manto)
    ):
        candidatos.append({
            "problema": "gliding_snow",
            "prioridad": 6,
            "confianza": CONFIANZA_PROXY,
            "evidencia": (
                f"Manto húmedo en base (SAR) sobre pendiente {pendiente:.0f}° "
                f"sin carga reciente"
            ),
            "proxy": True,
        })

    return _resolver(candidatos)


def _resolver(candidatos: list[dict]) -> dict:
    """
    Elige el dominante y ordena los secundarios.

    Un candidato marcado `proxy` (capa débil persistente, nieve deslizante) no
    puede ser dominante mientras exista uno sustentado en datos: son señales
    indirectas y encabezar el boletín con ellas sobrevendería su fiabilidad.
    """
    if not candidatos:
        return {
            "problema_dominante": "no_distinct",
            "problemas_secundarios": [],
            "confianza": CONFIANZA_PROXY,
            "evidencia": ["Sin señal de problema típico en los datos del día"],
        }

    ordenados = sorted(candidatos, key=lambda c: c["prioridad"])
    solidos = [c for c in ordenados if not c.get("proxy")]
    dominante = solidos[0] if solidos else ordenados[0]

    secundarios = []
    for c in ordenados:
        if c is dominante or c["problema"] == dominante["problema"]:
            continue
        if c["problema"] not in secundarios:
            secundarios.append(c["problema"])

    return {
        "problema_dominante": dominante["problema"],
        "problemas_secundarios": secundarios,
        "confianza": dominante["confianza"],
        "evidencia": [c["evidencia"] for c in ordenados],
    }


def _manto_humedo(manto: dict) -> bool:
    """
    Humedad superficial detectada por SAR (ΔVV < −3 dB vs baseline, Nagler 2016).

    Acepta las dos claves en circulación: `humedad_activa` la emite
    ConsultorBigQuery.obtener_sar_baseline y `humedad_sar_activa` la tool
    consultar_estado_manto del subagente satelital.
    """
    return bool(manto.get("humedad_sar_activa") or manto.get("humedad_activa"))


def _hay_fusion(pinn: dict, manto: Optional[dict] = None) -> bool:
    """
    Fusión activa: energía de fusión del PINN, o manto templado según LST.

    `manto_frio` viene de obtener_estado_manto (temperatura de superficie GOES /
    MODIS): un manto que dejó de estar frío está absorbiendo energía.
    """
    ratio = pinn.get("ratio_energia_fusion")
    if ratio is not None and ratio > 0.5:
        return True
    if pinn.get("fusion_activa"):
        return True
    manto = manto or {}
    if (manto.get("dias_lst_positivo") or 0) > 0:
        return True
    return manto.get("manto_frio") is False


def _viento_ms(wn2: dict, precipitacion: dict) -> float:
    """Viento a 100 m en m/s; la alerta del ensemble vale como piso."""
    viento = wn2.get("viento_100m_ms")
    if viento is not None:
        return float(viento)
    return VIENTO_TRANSPORTE_MS if wn2.get("wind_strong") else 0.0


# ─── Cota de nieve ───────────────────────────────────────────────────────────

def interpolar_cota(observaciones: list[tuple], bulbo_humedo_c=None,
                    altitud_referencia_m=None) -> Optional[int]:
    """
    Cota de nieve a partir de sectores a distinta altitud.

    Args:
        observaciones: [(altitud_m, hubo_lluvia)] de los sectores de la zona
        bulbo_humedo_c: bulbo húmedo en la altitud de referencia (fallback)
        altitud_referencia_m: altitud de ese bulbo húmedo

    Returns:
        Cota en metros, o None si en la zona no hubo transición que reportar.

    Los sectores dan la medición directa: la cota está entre el sector más alto
    con lluvia y el más bajo con nieve. Sin sectores, se proyecta la altitud
    donde el bulbo húmedo cae a 0,5 °C con gradiente estándar.

    Si nevó en todo el rango de la zona no se devuelve cota: la transición queda
    por debajo del terreno observado y publicar la altitud del punto más bajo se
    leería como una cota real, cuando el dato solo dice "nevó hasta aquí abajo".
    """
    if observaciones:
        con_lluvia = [alt for alt, lluvia in observaciones if lluvia]
        con_nieve = [alt for alt, lluvia in observaciones if not lluvia]
        if con_lluvia and con_nieve:
            techo_lluvia = max(con_lluvia)
            piso_nieve = min(a for a in con_nieve if a > techo_lluvia) if any(
                a > techo_lluvia for a in con_nieve
            ) else None
            if piso_nieve is not None:
                return int(round((techo_lluvia + piso_nieve) / 2, -1))
        if con_lluvia and not con_nieve:
            # Llovió hasta el sector más alto: la cota está al menos ahí
            return int(max(con_lluvia))
        if con_nieve and not con_lluvia:
            return None

    if bulbo_humedo_c is not None and altitud_referencia_m is not None:
        from agentes.datos.precipitacion import UMBRAL_BULBO_HUMEDO_LLUVIA_C
        delta_c = bulbo_humedo_c - UMBRAL_BULBO_HUMEDO_LLUVIA_C
        return int(round(altitud_referencia_m + (delta_c / LAPSE_RATE_C_KM) * 1000, -1))

    return None


# ─── Wrapper con acceso a datos ──────────────────────────────────────────────

def ejecutar_clasificar_problema_eaws(
    ubicacion: str,
    fecha: Optional[str] = None,
) -> dict:
    """
    Clasifica el problema típico de la ubicación consultando el pipeline.

    Nunca levanta excepción: ante un fallo de datos retorna `no_distinct` con la
    razón, para no bloquear la emisión del boletín.
    """
    from datetime import datetime, timezone

    from agentes.datos.consultor_bigquery import ConsultorBigQuery
    from agentes.datos.constantes_zonas import METADATA_ZONAS

    try:
        consultor = ConsultorBigQuery()
        referencia = None
        if fecha:
            referencia = datetime.fromisoformat(f"{fecha}T23:59:59").replace(
                tzinfo=timezone.utc
            )

        precipitacion = consultor.obtener_precipitacion_horaria(
            ubicacion, fecha_referencia=referencia
        )

        wn2 = {}
        try:
            from agentes.datos.wn2_features import obtener_features_wn2
            fecha_wn2 = fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            wn2 = obtener_features_wn2(ubicacion, fecha_wn2) or {}
        except Exception as exc:
            logger.debug(f"[ClasificarProblema] WN2 no disponible: {exc}")

        # Estado del manto: humedad SAR (Sentinel-1) + estado térmico (LST).
        # Son dos consultas distintas del consultor y se combinan en un dict.
        manto = {
            **(consultor.obtener_sar_baseline(ubicacion) or {}),
            **(consultor.obtener_estado_manto(ubicacion) or {}),
        }
        topografia = consultor.obtener_perfil_topografico(ubicacion) or {}

        metadata = METADATA_ZONAS.get(ubicacion, {})
        resultado = clasificar_problemas(
            precipitacion=precipitacion,
            wn2=wn2,
            manto=manto,
            topografia=topografia,
            exposicion_zona=metadata.get("exposicion_predominante"),
        )
        resultado["cota_nieve_m"] = _cota_de_la_zona(
            consultor, ubicacion, referencia, precipitacion, wn2
        )
        resultado["disponible"] = True
        logger.info(
            f"[ClasificarProblema] {ubicacion}: {resultado['problema_dominante']} "
            f"(confianza {resultado['confianza']}, cota {resultado['cota_nieve_m']})"
        )
        return resultado

    except Exception as exc:
        logger.warning(f"[ClasificarProblema] error para {ubicacion}: {exc}")
        return {
            "disponible": False,
            "problema_dominante": "no_distinct",
            "problemas_secundarios": [],
            "confianza": CONFIANZA_PROXY,
            "evidencia": [f"Clasificación no disponible: {exc}"],
            "cota_nieve_m": None,
        }


def _cota_de_la_zona(consultor, ubicacion: str, referencia, precipitacion: dict,
                     wn2: Optional[dict] = None):
    """
    Estima la cota consultando los sectores hermanos de la misma zona base.

    La Parva tiene sectores a 2.700 / 3.000 / 3.600 m (altitud de referencia):
    consultarlos da la transición lluvia→nieve medida, no proyectada. Si la zona
    no tiene sectores ni transición observable, se usa la isoterma 0 °C del
    ensemble (`cota_0c_m`), que fuente_weathernext2 ya calcula con lapse rate
    variable por presión — mejor que proyectar con un gradiente fijo.
    """
    import re

    from agentes.datos.constantes_zonas import METADATA_ZONAS, obtener_elevacion_referencia
    from agentes.subagentes.subagente_meteorologico.fuentes.correccion_orografica import (
        ALTITUD_REFERENCIA_ZONAS_M,
    )

    def _altitud(zona: str):
        # ALTITUD_REFERENCIA_ZONAS_M solo cubre las zonas con corrección orográfica
        # calibrada; para el resto vale la elevación media de METADATA_ZONAS
        return ALTITUD_REFERENCIA_ZONAS_M.get(zona) or obtener_elevacion_referencia(zona)

    zona_base = re.sub(r"\s+Sector\s+\S+$", "", ubicacion).strip()
    hermanas = [
        z for z in METADATA_ZONAS
        if z == zona_base or z.startswith(f"{zona_base} Sector ")
    ]

    observaciones = []
    for zona in hermanas:
        altitud = _altitud(zona)
        if altitud is None:
            continue
        datos = (
            precipitacion if zona == ubicacion
            else consultor.obtener_precipitacion_horaria(zona, fecha_referencia=referencia)
        )
        if not datos.get("disponible") or (datos.get("mm_total") or 0) <= 0:
            continue
        observaciones.append((altitud, bool(datos.get("horas_lluvia"))))

    cota = interpolar_cota(
        observaciones,
        bulbo_humedo_c=precipitacion.get("bulbo_humedo_max_c"),
        altitud_referencia_m=_altitud(ubicacion),
    )
    if cota is None and not observaciones:
        # Sin precipitación observada en ningún sector: queda la isoterma del modelo
        cota = (wn2 or {}).get("cota_0c_m")
        cota = int(cota) if cota is not None else None
    return cota
