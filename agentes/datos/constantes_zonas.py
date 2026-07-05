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
    "Lagunillas":           (-33.610, -70.290),
    "Chapa Verde":          (-34.170, -70.370),
    "Laguna del Maule":     (-36.058, -70.560),
    # Sur de Chile (Biobío → Magallanes)
    "Nevados de Chillán":   (-36.858, -71.373),
    "Antuco":               (-37.410, -71.420),
    "Corralco":             (-38.370, -71.570),
    "Las Araucarias":       (-38.730, -71.740),
    "Ski Pucón":            (-39.500, -71.960),
    "Antillanca":           (-40.776, -72.205),
    "Volcán Osorno":        (-41.100, -72.500),
    "El Fraile":            (-45.680, -71.940),
    "Cerro Mirador":        (-53.130, -70.980),
    # Centros nuevos (expansión lista canónica)
    "Valle de las Arenas":  (-33.900, -70.050),
    "Planchón-Peteroa":     (-35.240, -70.570),
    "Los Arenales":         (-38.850, -72.000),
    "Mocho-Choshuenco":     (-39.930, -72.030),
    "Ski Chaitén":          (-42.830, -72.680),
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
    "Lagunillas":           [-70.39, -33.71, -70.19, -33.51],
    "Chapa Verde":          [-70.47, -34.27, -70.27, -34.07],
    "Laguna del Maule":     [-70.76, -36.26, -70.36, -35.86],
    # Sur de Chile (Biobío → Magallanes)
    "Nevados de Chillán":   [-71.57, -37.06, -71.17, -36.66],
    "Antuco":               [-71.62, -37.61, -71.22, -37.21],
    "Corralco":             [-71.77, -38.57, -71.37, -38.17],
    "Las Araucarias":       [-71.94, -38.93, -71.54, -38.53],
    "Ski Pucón":            [-72.16, -39.70, -71.76, -39.30],
    "Antillanca":           [-72.41, -40.98, -72.01, -40.58],
    "Volcán Osorno":        [-72.70, -41.30, -72.30, -40.90],
    "El Fraile":            [-72.14, -45.88, -71.74, -45.48],
    "Cerro Mirador":        [-71.18, -53.33, -70.78, -52.93],
    # Centros nuevos (expansión lista canónica)
    "Valle de las Arenas":  [-70.25, -34.10, -69.85, -33.70],
    "Planchón-Peteroa":     [-70.77, -35.44, -70.37, -35.04],
    "Los Arenales":         [-72.20, -39.05, -71.80, -38.65],
    "Mocho-Choshuenco":     [-72.23, -40.13, -71.83, -39.73],
    "Ski Chaitén":          [-72.88, -43.03, -72.48, -42.63],
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
            [-70.39, -33.71], [-70.19, -33.71],
            [-70.19, -33.51], [-70.39, -33.51],
            [-70.39, -33.71],
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
    "Laguna del Maule": {
        "type": "Polygon",
        "coordinates": [[
            [-70.76, -36.26], [-70.36, -36.26],
            [-70.36, -35.86], [-70.76, -35.86],
            [-70.76, -36.26],
        ]],
    },
    "Nevados de Chillán": {
        "type": "Polygon",
        "coordinates": [[
            [-71.57, -37.06], [-71.17, -37.06],
            [-71.17, -36.66], [-71.57, -36.66],
            [-71.57, -37.06],
        ]],
    },
    "Antuco": {
        "type": "Polygon",
        "coordinates": [[
            [-71.62, -37.61], [-71.22, -37.61],
            [-71.22, -37.21], [-71.62, -37.21],
            [-71.62, -37.61],
        ]],
    },
    "Corralco": {
        "type": "Polygon",
        "coordinates": [[
            [-71.77, -38.57], [-71.37, -38.57],
            [-71.37, -38.17], [-71.77, -38.17],
            [-71.77, -38.57],
        ]],
    },
    "Las Araucarias": {
        "type": "Polygon",
        "coordinates": [[
            [-71.94, -38.93], [-71.54, -38.93],
            [-71.54, -38.53], [-71.94, -38.53],
            [-71.94, -38.93],
        ]],
    },
    "Ski Pucón": {
        "type": "Polygon",
        "coordinates": [[
            [-72.16, -39.70], [-71.76, -39.70],
            [-71.76, -39.30], [-72.16, -39.30],
            [-72.16, -39.70],
        ]],
    },
    "Antillanca": {
        "type": "Polygon",
        "coordinates": [[
            [-72.41, -40.98], [-72.01, -40.98],
            [-72.01, -40.58], [-72.41, -40.58],
            [-72.41, -40.98],
        ]],
    },
    "Volcán Osorno": {
        "type": "Polygon",
        "coordinates": [[
            [-72.70, -41.30], [-72.30, -41.30],
            [-72.30, -40.90], [-72.70, -40.90],
            [-72.70, -41.30],
        ]],
    },
    "El Fraile": {
        "type": "Polygon",
        "coordinates": [[
            [-72.14, -45.88], [-71.74, -45.88],
            [-71.74, -45.48], [-72.14, -45.48],
            [-72.14, -45.88],
        ]],
    },
    "Cerro Mirador": {
        "type": "Polygon",
        "coordinates": [[
            [-71.18, -53.33], [-70.78, -53.33],
            [-70.78, -52.93], [-71.18, -52.93],
            [-71.18, -53.33],
        ]],
    },
    # Centros nuevos (expansión lista canónica)
    "Valle de las Arenas": {
        "type": "Polygon",
        "coordinates": [[
            [-70.25, -34.10], [-69.85, -34.10],
            [-69.85, -33.70], [-70.25, -33.70],
            [-70.25, -34.10],
        ]],
    },
    "Planchón-Peteroa": {
        "type": "Polygon",
        "coordinates": [[
            [-70.77, -35.44], [-70.37, -35.44],
            [-70.37, -35.04], [-70.77, -35.04],
            [-70.77, -35.44],
        ]],
    },
    "Los Arenales": {
        "type": "Polygon",
        "coordinates": [[
            [-72.20, -39.05], [-71.80, -39.05],
            [-71.80, -38.65], [-72.20, -38.65],
            [-72.20, -39.05],
        ]],
    },
    "Mocho-Choshuenco": {
        "type": "Polygon",
        "coordinates": [[
            [-72.23, -40.13], [-71.83, -40.13],
            [-71.83, -39.73], [-72.23, -39.73],
            [-72.23, -40.13],
        ]],
    },
    "Ski Chaitén": {
        "type": "Polygon",
        "coordinates": [[
            [-72.88, -43.03], [-72.48, -43.03],
            [-72.48, -42.63], [-72.88, -42.63],
            [-72.88, -43.03],
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
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro Falsa Parva",
        "tipo_operacion": "Centro Comercial",
    },
    "La Parva Sector Bajo": {
        "elevacion_min_m": 2200,
        "elevacion_max_m": 3200,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro Falsa Parva",
        "tipo_operacion": "Centro Comercial",
    },
    "La Parva Sector Medio": {
        "elevacion_min_m": 2500,
        "elevacion_max_m": 3800,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro Falsa Parva",
        "tipo_operacion": "Centro Comercial",
    },
    "La Parva Sector Alto": {
        "elevacion_min_m": 3000,
        "elevacion_max_m": 4500,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro Falsa Parva",
        "tipo_operacion": "Centro Comercial",
    },
    "Valle Nevado": {
        "elevacion_min_m": 2800,
        "elevacion_max_m": 4500,
        "exposicion_predominante": "NO",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro El Plomo",
        "tipo_operacion": "Centro Comercial",
    },
    "El Colorado": {
        "elevacion_min_m": 2400,
        "elevacion_max_m": 4100,
        "exposicion_predominante": "O",
        "region_eaws": "Andes Central Norte",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Cerro Colorado",
        "tipo_operacion": "Centro Comercial",
    },
    "Portillo": {
        "elevacion_min_m": 2580,
        "elevacion_max_m": 3310,
        "exposicion_predominante": "NE",
        "region_eaws": "Andes del Aconcagua",
        "region": "andes_chile",
        "region_admin": "Valparaíso",
        "macizo_volcan": "Alta Montaña (Laguna del Inca)",
        "tipo_operacion": "Centro Comercial",
    },
    "Ski Arpa": {
        "elevacion_min_m": 2600,
        "elevacion_max_m": 3700,
        "exposicion_predominante": "S",
        "region_eaws": "Andes del Aconcagua",
        "region": "andes_chile",
        "region_admin": "Valparaíso",
        "macizo_volcan": "Cerro Blanco / Aconcagua",
        "tipo_operacion": "Cat-Ski / Freeride",
    },
    "Lagunillas": {
        "elevacion_min_m": 2250,
        "elevacion_max_m": 2700,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes Cajón del Maipo",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Precordillera (Cajón del Maipo)",
        "tipo_operacion": "Club Andino",
    },
    "Valle de las Arenas": {
        "elevacion_min_m": 2200,
        "elevacion_max_m": 3200,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes Cajón del Maipo",
        "region": "andes_chile",
        "region_admin": "Metropolitana",
        "macizo_volcan": "Morado / San José",
        "tipo_operacion": "Randonnée / Expedición",
    },
    "Chapa Verde": {
        "elevacion_min_m": 2700,
        "elevacion_max_m": 3100,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de O'Higgins",
        "region": "andes_chile",
        "region_admin": "O'Higgins",
        "macizo_volcan": "Cordillera de Rancagua",
        "tipo_operacion": "Club de Ski",
    },
    "Planchón-Peteroa": {
        "elevacion_min_m": 1600,
        "elevacion_max_m": 3000,
        "exposicion_predominante": "N",
        "region_eaws": "Andes de O'Higgins",
        "region": "andes_chile",
        "region_admin": "O'Higgins",
        "macizo_volcan": "Volcán Planchón-Peteroa",
        "tipo_operacion": "Randonnée / Expedición",
    },
    "Laguna del Maule": {
        "elevacion_min_m": 2100,
        "elevacion_max_m": 3200,
        "exposicion_predominante": "E",
        "region_eaws": "Andes del Maule",
        "region": "andes_chile",
        "region_admin": "Maule",
        "macizo_volcan": "Complejo Volcánico Laguna del Maule",
        "tipo_operacion": "Randonnée / Nieve Salvaje",
    },
    # Sur de Chile (Biobío → Magallanes)
    "Nevados de Chillán": {
        "elevacion_min_m": 1530,
        "elevacion_max_m": 2400,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de Biobío",
        "region": "andes_chile",
        "region_admin": "Ñuble",
        "macizo_volcan": "Volcán Chillán",
        "tipo_operacion": "Centro Comercial",
    },
    "Antuco": {
        "elevacion_min_m": 1400,
        "elevacion_max_m": 1850,
        "exposicion_predominante": "NO",
        "region_eaws": "Andes de Biobío",
        "region": "andes_chile",
        "region_admin": "Biobío",
        "macizo_volcan": "Volcán Antuco",
        "tipo_operacion": "Club de Ski",
    },
    "Corralco": {
        "elevacion_min_m": 1550,
        "elevacion_max_m": 2400,
        "exposicion_predominante": "NE",
        "region_eaws": "Andes de La Araucanía",
        "region": "andes_chile",
        "region_admin": "La Araucanía",
        "macizo_volcan": "Volcán Lonquimay",
        "tipo_operacion": "Centro Comercial",
    },
    "Los Arenales": {
        "elevacion_min_m": 1500,
        "elevacion_max_m": 1845,
        "exposicion_predominante": "S",
        "region_eaws": "Andes de La Araucanía",
        "region": "andes_chile",
        "region_admin": "La Araucanía",
        "macizo_volcan": "Volcán Lonquimay (Ladera Sur)",
        "tipo_operacion": "Randonnée / Recreativo",
    },
    "Las Araucarias": {
        "elevacion_min_m": 1550,
        "elevacion_max_m": 1942,
        "exposicion_predominante": "O",
        "region_eaws": "Andes de La Araucanía",
        "region": "andes_chile",
        "region_admin": "La Araucanía",
        "macizo_volcan": "Volcán Llaima",
        "tipo_operacion": "Centro Comercial",
    },
    "Ski Pucón": {
        "elevacion_min_m": 1380,
        "elevacion_max_m": 2100,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de La Araucanía",
        "region": "andes_chile",
        "region_admin": "La Araucanía",
        "macizo_volcan": "Volcán Villarrica",
        "tipo_operacion": "Centro Comercial",
    },
    "Mocho-Choshuenco": {
        "elevacion_min_m": 1700,
        "elevacion_max_m": 2422,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de Los Ríos",
        "region": "andes_chile",
        "region_admin": "Los Ríos",
        "macizo_volcan": "Volcán Mocho-Choshuenco",
        "tipo_operacion": "Randonnée / Glaciar",
    },
    "Antillanca": {
        "elevacion_min_m": 1040,
        "elevacion_max_m": 1540,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes de Los Lagos",
        "region": "andes_chile",
        "region_admin": "Los Lagos",
        "macizo_volcan": "Volcán Casablanca",
        "tipo_operacion": "Centro Comercial",
    },
    "Volcán Osorno": {
        "elevacion_min_m": 1230,
        "elevacion_max_m": 1760,
        "exposicion_predominante": "SO",
        "region_eaws": "Andes de Los Lagos",
        "region": "andes_chile",
        "region_admin": "Los Lagos",
        "macizo_volcan": "Volcán Osorno",
        "tipo_operacion": "Centro Comercial",
    },
    "Ski Chaitén": {
        "elevacion_min_m": 600,
        "elevacion_max_m": 1500,
        "exposicion_predominante": "N",
        "region_eaws": "Andes de Los Lagos",
        "region": "andes_chile",
        "region_admin": "Los Lagos",
        "macizo_volcan": "Volcán Michinmahuida",
        "tipo_operacion": "Club de Ski",
    },
    "El Fraile": {
        "elevacion_min_m": 980,
        "elevacion_max_m": 1280,
        "exposicion_predominante": "N",
        "region_eaws": "Andes de Aysén",
        "region": "andes_chile",
        "region_admin": "Aysén",
        "macizo_volcan": "Cerro El Fraile",
        "tipo_operacion": "Centro Comercial",
    },
    "Cerro Mirador": {
        "elevacion_min_m": 380,
        "elevacion_max_m": 570,
        "exposicion_predominante": "SE",
        "region_eaws": "Andes de Magallanes",
        "region": "andes_chile",
        "region_admin": "Magallanes",
        "macizo_volcan": "Monte Fenton",
        "tipo_operacion": "Centro Comercial",
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
