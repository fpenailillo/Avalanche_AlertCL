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

# ROI: Andes de Chile central (mismo recuadro del script GEE del usuario).
ROI_COORDS = [-70.8, -34.5, -69.7, -32.5]  # [oeste, sur, este, norte]
DIAS_VENTANA = 30  # ventana hacia atrás para el mosaico más reciente
MAX_NUBOSIDAD = 40

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
    roi = ee.Geometry.Rectangle(ROI_COORDS)

    hoy = ee.Date(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    inicio = hoy.advance(-DIAS_VENTANA, "day")

    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(inicio, hoy)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_NUBOSIDAD))
    )
    n_imagenes = coleccion.size().getInfo()
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
    return capas, n_imagenes, inicio.format("YYYY-MM-dd").getInfo()


@functions_framework.http
def mapa_gee(solicitud):
    if solicitud.method == "OPTIONS":
        return _cors("", 204)
    try:
        _init_ee()
        capas, n_imagenes, desde = _construir_capas()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error generando capas GEE")
        return _cors(json.dumps({"error": str(exc)}), 500)

    oeste, sur, este, norte = ROI_COORDS
    cuerpo = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "capas": capas,
        "bounds": [[sur, oeste], [norte, este]],  # Leaflet: [[S,W],[N,E]]
        "centro": [(sur + norte) / 2, (oeste + este) / 2],
        "zoom": 9,
        "imagenes_usadas": n_imagenes,
        "ventana_desde": desde,
        "atribucion": "Sentinel-2 (Copernicus) · SRTM · Google Earth Engine",
    }
    logger.info("Capas GEE generadas (%s imágenes, desde %s)", n_imagenes, desde)
    return _cors(json.dumps(cuerpo, ensure_ascii=False), 200)
