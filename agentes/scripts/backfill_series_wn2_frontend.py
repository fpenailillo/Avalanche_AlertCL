"""
Backfill de series WN2 datadas para el frontend.

Para cada fecha del rango, consulta la corrida de WeatherNext 2 inicializada
ese día y publica gs://<bucket>/series_wn2/series_<fecha>.json. Permite ver
en el frontend el pronóstico que estaba vigente al navegar boletines
históricos (cambio día a día).

NO toca BigQuery ni el bronce ni series_wn2.json (la última versión): solo
escribe las copias datadas. Para la serie vigente usa el ingestor normal.

Uso:
    python agentes/scripts/backfill_series_wn2_frontend.py --desde 2026-06-10 --hasta 2026-06-12
    python agentes/scripts/backfill_series_wn2_frontend.py --desde 2026-06-10 --hasta 2026-06-12 --dry-run
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from agentes.datos.ingestores.ingestor_wn2 import IngestorWN2
from agentes.datos.constantes_zonas import COORDENADAS_ZONAS, ZONAS_ANDES_CHILE

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def _rango_fechas(desde: str, hasta: str):
    d0 = datetime.strptime(desde, "%Y-%m-%d").date()
    d1 = datetime.strptime(hasta, "%Y-%m-%d").date()
    actual = d0
    while actual <= d1:
        yield actual.isoformat()
        actual += timedelta(days=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", required=True, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--hasta", required=True, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="No subir a GCS")
    parser.add_argument(
        "--fallback-dias", type=int, default=0,
        help="Si no hay corrida WN2 para la fecha exacta, usar la más reciente "
             "dentro de los N días previos (útil por el desfase de publicación)"
    )
    parser.add_argument(
        "--actualizar-vigente", action="store_true",
        help="Además de la copia datada, sobreescribir series_wn2.json (vigente) "
             "con la última fecha del rango"
    )
    args = parser.parse_args()

    # Zonas base chilenas con coordenadas (sin sectores ni suizas)
    zonas = [
        z for z in ZONAS_ANDES_CHILE
        if " Sector " not in z and z in COORDENADAS_ZONAS
    ]
    logger.info(f"Zonas a backfillear: {zonas}")

    ingestor = IngestorWN2(dry_run=args.dry_run)

    for fecha in _rango_fechas(args.desde, args.hasta):
        # Ventana de búsqueda: fecha exacta, o hasta N días previos si hay desfase
        inicio_busqueda = (
            datetime.strptime(fecha, "%Y-%m-%d").date()
            - timedelta(days=args.fallback_dias)
        ).isoformat()
        etiqueta = fecha if args.fallback_dias == 0 else f"{inicio_busqueda}→{fecha} (corrida más reciente)"
        logger.info(f"\n=== Series {fecha} · init {etiqueta} ===")
        series_por_zona = {}
        for nombre in zonas:
            lat, lon = COORDENADAS_ZONAS[nombre]
            try:
                filas = ingestor._consultar_wn2(lat, lon, inicio_busqueda, fecha)
                diarios = [r for r in filas if r.get("nivel") == "diario"]
                if diarios:
                    series_por_zona[nombre] = diarios
                    logger.info(f"  [{nombre}] {len(diarios)} días")
                else:
                    logger.warning(f"  [{nombre}] sin datos WN2 para init {etiqueta}")
            except Exception as exc:
                logger.error(f"  [{nombre}] ERROR: {exc}")

        # fecha_desde=fecha: la serie arranca en su fecha de referencia, aunque
        # la corrida usada (por fallback) sea de días previos
        contenido = IngestorWN2.construir_contenido_series(
            series_por_zona, generado=f"{fecha}T00:00:00+00:00", fecha_desde=fecha
        )
        if contenido is None:
            logger.warning(f"  Sin series para {fecha} — se omite")
            continue

        rutas = [f"series_wn2/series_{fecha}.json"]
        # La última fecha del rango también puede actualizar la serie vigente
        if args.actualizar_vigente and fecha == args.hasta:
            rutas.append("series_wn2.json")
        if args.dry_run:
            logger.info(f"  [dry-run] {', '.join(rutas)}: {len(contenido['series'])} zonas")
        else:
            ingestor.subir_series_frontend(contenido, rutas)

    logger.info("\nBackfill de series WN2 frontend completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
