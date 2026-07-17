"""
Cloud Function HTTP que genera, con Google Earth Engine, las capas de
visualización para el mapa interactivo del frontend (Leaflet):

  - Color verdadero (mosaico Sentinel-2 reciente, baja nubosidad)
  - Cobertura de nieve (NDSI >= 0.4)
  - Zonas de riesgo de avalancha (nieve + pendiente 30–45° sobre SRTM)

Devuelve las plantillas de tiles XYZ de EE (getMapId) que Leaflet consume
directamente, más metadatos (bounds, centro, n.º de imágenes, ventana).
"""

import json
import logging
import os
from datetime import datetime, timezone

import ee
import functions_framework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mapa_gee")

PROYECTO = os.environ.get("GEE_PROJECT", os.environ.get("GCP_PROJECT", "climas-chileno"))
ORIGEN_PERMITIDO = "https://fpenailillo.github.io"

# Coordenadas [lon, lat] de los 22 centros de esquí monitoreados.
# ROI = unión de buffers de 30 km alrededor de cada centro, cubre Chile completo.
CENTROS_PUNTOS = [
    [-70.39,   -32.60],   # Ski Arpa
    [-70.129,  -32.837],  # Portillo
    [-70.28,   -33.34],   # La Parva
    [-70.25,   -33.35],   # Valle Nevado
    [-70.29,   -33.36],   # El Colorado
    [-70.25,   -33.68],   # Lagunillas
    [-70.05,   -33.90],   # Valle de las Arenas
    [-70.37,   -34.17],   # Chapa Verde
    [-70.437,  -34.953],  # Termas del Flaco
    [-70.57,   -35.24],   # Planchón-Peteroa
    [-70.56,   -36.058],  # Laguna del Maule
    [-71.3727, -36.858],  # Nevados de Chillán
    [-71.42,   -37.41],   # Antuco
    [-71.57,   -38.37],   # Corralco
    [-71.74,   -38.73],   # Las Araucarias
    [-71.58,   -38.41],   # Los Arenales (ladera sur Lonquimay)
    [-71.96,   -39.50],   # Ski Pucón
    [-72.03,   -39.93],   # Mocho-Choshuenco
    [-72.2046, -40.7756], # Antillanca
    [-72.50,   -41.10],   # Volcán Osorno
    [-72.68,   -42.83],   # Ski Chaitén
    [-71.94,   -45.68],   # El Fraile
    [-70.98,   -53.13],   # Cerro Mirador
]

BUFFER_M     = 30_000  # 30 km alrededor de cada centro
DIAS_VENTANA = 90      # ventana más amplia para cubrir sur de Chile
MAX_NUBOSIDAD = 70     # más permisivo: sur de Chile tiene alta nubosidad

# Bounds estáticos derivados de las coordenadas de los centros + buffer ~0.3°
_LONS = [p[0] for p in CENTROS_PUNTOS]
_LATS = [p[1] for p in CENTROS_PUNTOS]
BOUNDS_CHILE = [
    [min(_LATS) - 0.3, min(_LONS) - 0.3],  # [sur, oeste]
    [max(_LATS) + 0.3, max(_LONS) + 0.3],  # [norte, este]
]

_ee_listo = False


def _init_ee():
    global _ee_listo
    if not _ee_listo:
        ee.Initialize(project=PROYECTO)
        _ee_listo = True


def _cors(body, codigo=200):
    headers = {
        "Access-Control-Allow-Origin": ORIGEN_PERMITIDO,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
        "Content-Type": "application/json",
    }
    return (body, codigo, headers)


def _url_tiles(imagen, vis):
    """getMapId → plantilla de tiles XYZ usable por Leaflet."""
    mapid = imagen.getMapId(vis)
    return mapid["tile_fetcher"].url_format


def _construir_capas():
    # ROI: MultiPoint bufferizado = unión de discos de 30 km
    roi = ee.Geometry.MultiPoint(CENTROS_PUNTOS).buffer(BUFFER_M, maxError=100)

    hoy = ee.Date(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    inicio = hoy.advance(-DIAS_VENTANA, "day")

    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(inicio, hoy)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_NUBOSIDAD))
    )
    # Metadatos reales de las imágenes usadas (1 consulta a EE).
    info = ee.Dictionary({
        "n": coleccion.size(),
        "desde": ee.Date(coleccion.aggregate_min("system:time_start")).format("YYYY-MM-dd"),
        "hasta": ee.Date(coleccion.aggregate_max("system:time_start")).format("YYYY-MM-dd"),
        "hasta_hora": ee.Date(coleccion.aggregate_max("system:time_start")).format("HH:mm"),
    }).getInfo()
    imagen = coleccion.median().clip(roi)

    # NDSI y máscara de nieve
    ndsi = imagen.normalizedDifference(["B3", "B11"]).rename("NDSI")
    mascara_nieve = ndsi.gte(0.4)
    nieve_visual = mascara_nieve.updateMask(mascara_nieve)

    # Pendiente (SRTM) y máscara de pendientes críticas 30–45°
    dem = ee.Image("USGS/SRTMGL1_003").clip(roi)
    pendiente = ee.Terrain.slope(dem)
    mascara_pendiente = pendiente.gte(30).And(pendiente.lte(45))

    # Riesgo = nieve ∧ pendiente crítica
    zona_riesgo = mascara_nieve.And(mascara_pendiente)
    riesgo_visual = zona_riesgo.updateMask(zona_riesgo)

    capas = {
        "color": _url_tiles(imagen, {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3500}),
        "nieve": _url_tiles(nieve_visual, {"min": 1, "max": 1, "palette": ["cyan"]}),
        "riesgo": _url_tiles(riesgo_visual, {"palette": ["red"]}),
    }
    return capas, info


@functions_framework.http
def mapa_gee(solicitud):
    if solicitud.method == "OPTIONS":
        return _cors("", 204)
    try:
        _init_ee()
        capas, info = _construir_capas()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error generando capas GEE")
        return _cors(json.dumps({"error": str(exc)}), 500)

    cuerpo = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "capas": capas,
        "bounds": BOUNDS_CHILE,
        "imagenes_usadas": info.get("n"),
        "fecha_desde": info.get("desde"),
        "fecha_hasta": info.get("hasta"),
        "hora_hasta": info.get("hasta_hora"),
        "atribucion": "Sentinel-2 (Copernicus) · SRTM · Google Earth Engine",
    }
    logger.info(
        "Capas GEE generadas (%s imágenes, %s–%s) · %d centros",
        info.get("n"), info.get("desde"), info.get("hasta"), len(CENTROS_PUNTOS),
    )
    return _cors(json.dumps(cuerpo, ensure_ascii=False), 200)
