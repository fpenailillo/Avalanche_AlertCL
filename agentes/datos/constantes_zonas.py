"""
Definiciones geográficas centralizadas de las zonas objetivo del sistema.

Fuente única de verdad para coordenadas, polígonos y metadatos de zona.
Importar desde aquí en lugar de duplicar coordenadas en cada módulo.
"""

# ─── Coordenadas puntuales (lat, lon) ─────────────────────────────────────────
# Usadas por Open-Meteo, ERA5-Land, WeatherNext 2 para queries puntuales.

COORDENADAS_ZONAS: dict[str, tuple[float, float]] = {
    "La Parva":             (-33.354, -70.298),
    "La Parva Sector Bajo": (-33.363, -70.301),
    "La Parva Sector Medio":(-33.352, -70.290),
    "La Parva Sector Alto": (-33.344, -70.280),
    "Valle Nevado":         (-33.357, -70.270),
    "El Colorado":          (-33.360, -70.289),
    # Centros adicionales (coordenadas alineadas con datos/extractor)
    "Portillo":             (-32.837, -70.129),
    "Ski Arpa":             (-32.600, -70.390),
    "Lagunillas":           (-33.680, -70.250),
    "Chapa Verde":          (-34.170, -70.370),
    # Alpes suizos (validación H1/H3 SLF)
    "Interlaken":           (46.686,   7.863),
    "Matterhorn Zermatt":   (45.977,   7.659),
    "St Moritz":            (46.491,   9.836),
}

# ─── Bounding boxes (lon_min, lat_min, lon_max, lat_max) ──────────────────────
# Usados por Earth Engine para filtrar imágenes satelitales.

BBOX_ZONAS: dict[str, list[float]] = {
    "La Parva":             [-70.45, -33.45, -70.15, -33.25],
    "La Parva Sector Bajo": [-70.40, -33.43, -70.25, -33.32],
    "Valle Nevado":         [-70.38, -33.40, -70.18, -33.25],
    "El Colorado":          [-70.35, -33.43, -70.22, -33.30],
    "Portillo":             [-70.23, -32.94, -70.03, -32.74],
    "Ski Arpa":             [-70.49, -32.70, -70.29, -32.50],
    "Lagunillas":           [-70.35, -33.78, -70.15, -33.58],
    "Chapa Verde":          [-70.47, -34.27, -70.27, -34.07],
}

# ─── Polígonos GeoJSON (para BigQuery GEOGRAPHY y ST_REGIONSTATS) ─────────────
# Formato: anillo exterior cerrado (primer punto = último punto).

POLIGONOS_ZONAS: dict[str, dict] = {
    "La Parva": {
        "type": "Polygon",
        "coordinates": [[
            [-70.45, -33.45], [-70.15, -33.45],
            [-70.15, -33.25], [-70.45, -33.25],
            [-70.45, -33.45],
        ]],
    },
    "La Parva Sector Bajo": {
        "type": "Polygon",
        "coordinates": [[
            [-70.40, -33.43], [-70.25, -33.43],
            [-70.25, -33.32], [-70.40, -33.32],
            [-70.40, -33.43],
        ]],
    },
    "Valle Nevado": {
        "type": "Polygon",
        "coordinates": [[
            [-70.38, -33.40], [-70.18, -33.40],
            [-70.18, -33.25], [-70.38, -33.25],
            [-70.38, -33.40],
        ]],
    },
    "El Colorado": {
        "type": "Polygon",
        "coordinates": [[
            [-70.35, -33.43], [-70.22, -33.43],
            [-70.22, -33.30], [-70.35, -33.30],
            [-70.35, -33.43],
        ]],
    },
    "Portillo": {
        "type": "Polygon",
        "coordinates": [[
            [-70.23, -32.94], [-70.03, -32.94],
            [-70.03, -32.74], [-70.23, -32.74],
            [-70.23, -32.94],
        ]],
    },
    "Ski Arpa": {
        "type": "Polygon",
        "coordinates": [[
            [-70.49, -32.70], [-70.29, -32.70],
            [-70.29, -32.50], [-70.49, -32.50],
            [-70.49, -32.70],
        ]],
    },
    "Lagunillas": {
        "type": "Polygon",
        "coordinates": [[
            [-70.35, -33.78], [-70.15, -33.78],
            [-70.15, -33.58], [-70.35, -33.58],
            [-70.35, -33.78],
        ]],
    },
    "Chapa Verde": {
        "type": "Polygon",
        "coordinates": [[
            [-70.47, -34.27], [-70.27, -34.27],
            [-70.27, -34.07], [-70.47, -34.07],
            [-70.47, -34.27],
        ]],
    },
}

# ─── Metadata de zonas ─────────────────────────────────────────────────────────

METADATA_ZONAS: dict[str, dict] = {
    "La Parva": {
        "elevacion_min_m": 2200,
        "elevacion_max_m": 4500,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "La Parva Sector Bajo": {
        "elevacion_min_m": 2200,
        "elevacion_max_m": 3200,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "La Parva Sector Medio": {
        "elevacion_min_m": 2500,
        "elevacion_max_m": 3800,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "La Parva Sector Alto": {
        "elevacion_min_m": 3000,
        "elevacion_max_m": 4500,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "Valle Nevado": {
        "elevacion_min_m": 2800,
        "elevacion_max_m": 4500,
        "exposicion_predominante": "NO",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "El Colorado": {
        "elevacion_min_m": 2400,
        "elevacion_max_m": 4100,
        "exposicion_predominante": "O",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
    },
    "Portillo": {
        "elevacion_min_m": 2580,
        "elevacion_max_m": 3310,
        "exposicion_predominante": "NE",
        "region_eaws": "Andes del Aconcagua",
        "region": "andes_chile",
    },
    "Ski Arpa": {
        "elevacion_min_m": 2600,
        "elevacion_max_m": 3700,
        "exposicion_predominante": "S",
        "region_eaws": "Andes del Aconcagua",
        "region": "andes_chile",
    },
    "Lagunillas": {
        "elevacion_min_m": 2250,
        "elevacion_max_m": 2700,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes Cajón del Maipo",
        "region": "andes_chile",
    },
    "Chapa Verde": {
        "elevacion_min_m": 2700,
        "elevacion_max_m": 3100,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de O'Higgins",
        "region": "andes_chile",
    },
    # Alpes suizos (validación H1/H3 SLF)
    "Interlaken": {
        "elevacion_min_m": 1200,
        "elevacion_max_m": 3400,
        "exposicion_predominante": "N",
        "region_eaws": "Bernese Alps",
        "region": "alpes_swiss",
    },
    "Matterhorn Zermatt": {
        "elevacion_min_m": 2600,
        "elevacion_max_m": 4478,
        "exposicion_predominante": "N",
        "region_eaws": "Valais",
        "region": "alpes_swiss",
    },
    "St Moritz": {
        "elevacion_min_m": 1900,
        "elevacion_max_m": 3400,
        "exposicion_predominante": "SE",
        "region_eaws": "Graubuenden",
        "region": "alpes_swiss",
    },
}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def obtener_elevacion_referencia(zona: str) -> int:
    """Retorna elevación media de la zona en metros (promedio entre min y max)."""
    meta = METADATA_ZONAS.get(zona, {})
    emin = meta.get("elevacion_min_m", 2500)
    emax = meta.get("elevacion_max_m", 3500)
    return (emin + emax) // 2


def obtener_region(zona: str) -> str:
    """Retorna 'andes_chile' (default) o 'alpes_swiss' según la zona.

    FIX-GEO / FIX-H (v7.0): usado para aplicar caps y defaults condicionados por región.
    Default seguro = 'andes_chile' para zonas no mapeadas (comportamiento conservador).
    """
    return METADATA_ZONAS.get(zona, {}).get("region", "andes_chile")


def obtener_coordenadas(zona: str) -> tuple[float, float]:
    """Retorna (lat, lon) para la zona; usa La Parva como fallback."""
    return COORDENADAS_ZONAS.get(zona, (-33.354, -70.298))


def obtener_bbox(zona: str) -> list[float]:
    """Retorna [lon_min, lat_min, lon_max, lat_max]; usa La Parva como fallback."""
    nombre_base = zona.split(" Sector")[0] if " Sector" in zona else zona
    return BBOX_ZONAS.get(zona) or BBOX_ZONAS.get(nombre_base, [-70.45, -33.45, -70.15, -33.25])


def poligono_geojson_str(zona: str) -> str:
    """Retorna el polígono como string GeoJSON para ST_GeogFromGeoJSON()."""
    import json
    nombre_base = zona.split(" Sector")[0] if " Sector" in zona else zona
    poly = POLIGONOS_ZONAS.get(zona) or POLIGONOS_ZONAS.get(nombre_base, POLIGONOS_ZONAS["La Parva"])
    return json.dumps(poly)


ZONAS_DISPONIBLES: list[str] = sorted(COORDENADAS_ZONAS.keys())

ZONAS_ANDES_CHILE: list[str] = [z for z, m in METADATA_ZONAS.items() if m.get("region") == "andes_chile"]
ZONAS_ALPES_SWISS: list[str] = [z for z, m in METADATA_ZONAS.items() if m.get("region") == "alpes_swiss"]
