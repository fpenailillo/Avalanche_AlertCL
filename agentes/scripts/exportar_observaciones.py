"""
Exporta a GCS las observaciones de la comunidad (tabla
clima.observaciones_comunidad) para que la tarjeta "Comunidad · S4" del
frontend muestre reportes reales en vez de datos de demostración.

Privacidad: solo se publican nombre (o "Anónimo"), comentarios y fecha.
NUNCA se exponen el contacto ni las fotos.

Uso:
    python agentes/scripts/exportar_observaciones.py
    python agentes/scripts/exportar_observaciones.py --dry-run
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from google.cloud import bigquery, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("exportar_observaciones")

GCP_PROJECT = "climas-chileno"
BUCKET = "avalanche-alertcl-boletines"
OBJETO = "observaciones.json"
DIAS_VENTANA = 30
MAX_POR_CENTRO = 8


def construir_contenido(cliente: bigquery.Client) -> dict:
    sql = f"""
        SELECT
          centro,
          COALESCE(NULLIF(TRIM(nombre), ''), 'Anónimo') AS autor,
          comentarios,
          fecha_registro,
          (fotos IS NOT NULL AND fotos != '[]') AS tiene_fotos
        FROM `{GCP_PROJECT}.clima.observaciones_comunidad`
        WHERE comentarios IS NOT NULL
          AND fecha_registro >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {DIAS_VENTANA} DAY)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY centro ORDER BY fecha_registro DESC
        ) <= {MAX_POR_CENTRO}
        ORDER BY fecha_registro DESC
    """
    observaciones = [
        {
            "centro": f.centro,
            "autor": f.autor,
            "comentarios": f.comentarios,
            "fecha": f.fecha_registro.astimezone(timezone.utc).isoformat(),
            "tiene_fotos": bool(f.tiene_fotos),
        }
        for f in cliente.query(sql).result()
    ]
    return {
        "generado": datetime.now(timezone.utc).isoformat(),
        "fuente": "observaciones_comunidad",
        "observaciones": observaciones,
    }


def subir(contenido: dict) -> str:
    bucket = storage.Client(project=GCP_PROJECT).bucket(BUCKET)
    blob = bucket.blob(OBJETO)
    blob.cache_control = "public, max-age=300"
    blob.upload_from_string(
        json.dumps(contenido, ensure_ascii=False, indent=2),
        content_type="application/json",
        timeout=60,
    )
    return f"gs://{BUCKET}/{OBJETO}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta observaciones de comunidad a GCS")
    parser.add_argument("--dry-run", action="store_true", help="No sube a GCS")
    args = parser.parse_args()

    cliente = bigquery.Client(project=GCP_PROJECT)
    contenido = construir_contenido(cliente)
    logger.info(f"{len(contenido['observaciones'])} observaciones en ventana de {DIAS_VENTANA} días")

    if args.dry_run:
        print(json.dumps(contenido, ensure_ascii=False, indent=2)[:1500])
        return 0

    logger.info(f"Subido {subir(contenido)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
