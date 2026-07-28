"""
Tipo de precipitación observado y transición lluvia/nieve.

Google Weather entrega en `clima.pronostico_horas` el campo `tipo_precipitacion`
con el tipo REAL de precipitación hora a hora, además de la temperatura de bulbo
húmedo. Hasta la v25.19 ninguna tool los leía: el tipo se infería de la
temperatura del aire con umbrales (>2 °C = lluvia) que perdían los eventos de
lluvia sobre nieve cerca de 0 °C.

Caso de referencia — La Parva Sector Bajo, 25-jul-2026: Google Weather reportó
RAIN_AND_SNOW y LIGHT_RAIN desde la 01:00 con temperatura del aire de 0,8-0,9 °C
y bulbo húmedo de 0,0-0,4 °C. El sistema publicó `new_snow`.

Funciones puras, sin dependencia de BigQuery: la capa de datos y el subagente
integrador comparten estos criterios.
"""

from typing import Iterable, Optional

# Valores observados en `pronostico_horas.tipo_precipitacion` (Google Weather).
# FREEZING_RAIN y las variantes ligeras/intensas de nieve no aparecen en los
# datos históricos pero la API las admite: se incluyen por robustez.
TIPOS_LLUVIA: frozenset[str] = frozenset({
    "RAIN", "LIGHT_RAIN", "HEAVY_RAIN", "FREEZING_RAIN",
})
TIPOS_MIXTOS: frozenset[str] = frozenset({
    "RAIN_AND_SNOW", "SLEET",
})
TIPOS_NIEVE: frozenset[str] = frozenset({
    "SNOW", "LIGHT_SNOW", "HEAVY_SNOW", "SNOW_SHOWERS",
})

# Umbral de bulbo húmedo para precipitación líquida. La transición lluvia/nieve
# ocurre en torno a T_bulbo_húmedo ≈ 0,5-1,0 °C y es un predictor mucho mejor que
# la temperatura del aire, porque incorpora el enfriamiento por evaporación
# (Steinacker 1983; Sims & Liu 2015). Con 0,5 °C el caso del 25-jul cae del lado
# correcto: bulbo húmedo 0,0-0,4 °C con lluvia observada es evento mixto real.
UMBRAL_BULBO_HUMEDO_LLUVIA_C = 0.5

# Horas de precipitación líquida a partir de las cuales el evento cuenta como
# lluvia sobre nieve y no como un chubasco aislado.
MIN_HORAS_LLUVIA = 2

# Acumulado mínimo para hablar de humedecimiento del manto. Sin este umbral, una
# llovizna de 0,2 mm repartida en dos horas dispara el problema de nieve húmeda:
# sobre los boletines del 24-28 jul 2026, 96 de 198 disparos quedaban por debajo
# de 3 mm. El agua tiene que ser suficiente para percolar, no solo para mojar la
# superficie.
MIN_MM_LLUVIA = 3.0


def es_lluvia(tipo: Optional[str]) -> bool:
    """True si el tipo observado incluye fase líquida (mixto cuenta como lluvia)."""
    if not tipo:
        return False
    t = tipo.strip().upper()
    return t in TIPOS_LLUVIA or t in TIPOS_MIXTOS


def es_nieve(tipo: Optional[str]) -> bool:
    """True si el tipo observado es nieve seca (el mixto NO cuenta como nieve)."""
    if not tipo:
        return False
    return tipo.strip().upper() in TIPOS_NIEVE


def fase_desde_condicion(condicion: Optional[str]) -> Optional[str]:
    """
    Fase ("lluvia" / "nieve") desde un texto descriptivo del clima.

    `condicion_clima` (en condiciones_actuales y pronostico_horas) no usa el
    vocabulario cerrado de `tipo_precipitacion`: aparecen LIGHT_TO_MODERATE_SNOW,
    LIGHT_SNOW_SHOWERS, RAIN_AND_SNOW… Por eso el match es por subcadena.
    RAIN gana sobre SNOW: en un evento mixto hay agua líquida mojando el manto.
    """
    if not condicion:
        return None
    texto = condicion.strip().upper()
    if "RAIN" in texto:
        return "lluvia"
    if "SNOW" in texto or "SLEET" in texto:
        return "nieve"
    return None


def hay_fase_liquida(tipo: Optional[str], bulbo_humedo_c: Optional[float]) -> bool:
    """
    Precipitación líquida por tipo observado o, si falta, por bulbo húmedo.

    El tipo observado manda: es una clasificación del proveedor, no una
    inferencia nuestra. El bulbo húmedo solo decide cuando no hay tipo.
    """
    if tipo:
        return es_lluvia(tipo)
    return bulbo_humedo_c is not None and bulbo_humedo_c > UMBRAL_BULBO_HUMEDO_LLUVIA_C


def resumir_horas(filas: Iterable[dict]) -> dict:
    """
    Agrega las horas de un día en las señales que necesita la clasificación.

    Args:
        filas: dicts con hora, tipo, precipitacion_mm, temperatura_c, bulbo_humedo_c

    Returns:
        dict con conteos, acumulados y máximos del día. `hay_lluvia_sobre_nieve`
        exige persistencia (MIN_HORAS_LLUVIA) y monto (MIN_MM_LLUVIA): un tipo
        RAIN con 0 mm es pronóstico de tipo, no lluvia caída, y una llovizna de
        décimas de milímetro no humedece el manto.
    """
    horas_lluvia = horas_nieve = 0
    mm_lluvia = mm_nieve = mm_total = 0.0
    temperaturas: list[float] = []
    bulbos: list[float] = []
    tipo_observado = False

    for fila in filas:
        tipo = fila.get("tipo")
        mm = fila.get("precipitacion_mm") or 0.0
        mm_total += mm
        if tipo and tipo.strip().upper() not in ("", "NONE"):
            tipo_observado = True

        if hay_fase_liquida(tipo, fila.get("bulbo_humedo_c")):
            horas_lluvia += 1
            mm_lluvia += mm
        elif es_nieve(tipo):
            horas_nieve += 1
            mm_nieve += mm

        if fila.get("temperatura_c") is not None:
            temperaturas.append(fila["temperatura_c"])
        if fila.get("bulbo_humedo_c") is not None:
            bulbos.append(fila["bulbo_humedo_c"])

    return {
        # Hubo clasificación del proveedor en alguna hora: cuando es True, el
        # tipo observado manda y no se debe inferir la fase por bulbo húmedo
        "tipo_observado": tipo_observado,
        "horas_lluvia": horas_lluvia,
        "horas_nieve": horas_nieve,
        "mm_lluvia": round(mm_lluvia, 1),
        "mm_nieve": round(mm_nieve, 1),
        "mm_total": round(mm_total, 1),
        "temperatura_max_c": max(temperaturas) if temperaturas else None,
        "temperatura_min_c": min(temperaturas) if temperaturas else None,
        "bulbo_humedo_max_c": max(bulbos) if bulbos else None,
        "hay_lluvia_sobre_nieve": (
            horas_lluvia >= MIN_HORAS_LLUVIA and mm_lluvia >= MIN_MM_LLUVIA
        ),
    }
