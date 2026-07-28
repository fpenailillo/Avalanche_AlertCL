#!/usr/bin/env python3
"""
Migración del schema de boletines_riesgo: 43 → 45 campos (v25.19).

Agrega los dos campos del problema típico EAWS que faltaban para publicarlo:
  - problemas_secundarios_eaws (STRING, lista JSON)
  - cota_nieve_m (INT64)

`tipo_problema_eaws` ya existía desde la v7.0 pero nunca se poblaba: el boletín
publicaba el problema del ensemble WN2. Ver tool_clasificar_problema_eaws.py.

A diferencia de las migraciones anteriores, esta agrega TODOS los campos del
schema JSON que falten en la tabla, no una lista fija: el JSON es la fuente de
verdad y así el script sirve para la próxima ampliación sin duplicarse.

Ambas operaciones son aditivas: BigQuery permite agregar columnas NULLABLE sin
reescribir la tabla y las filas existentes quedan con NULL.

Uso:
  python agentes/scripts/migrar_schema_boletines_v25_19.py --verificar
  python agentes/scripts/migrar_schema_boletines_v25_19.py --dry-run
  python agentes/scripts/migrar_schema_boletines_v25_19.py

Requiere: gcloud auth application-default login
"""

import argparse
import json
import logging
import os
import sys

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT") or os.environ.get("ID_PROYECTO", "climas-chileno")
DATASET = os.environ.get("DATASET_ID", "clima")
TABLA = "boletines_riesgo"
TABLA_COMPLETA = f"{GCP_PROJECT}.{DATASET}.{TABLA}"

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'salidas', 'schema_boletines.json'
)


def cargar_schema_objetivo() -> list:
    ruta = os.path.abspath(SCHEMA_PATH)
    if not os.path.exists(ruta):
        logger.error(f"Schema no encontrado: {ruta}")
        sys.exit(1)
    with open(ruta, 'r') as f:
        campos_json = json.load(f)
    return [
        bigquery.SchemaField(
            name=c["name"],
            field_type=c["type"],
            mode=c.get("mode", "NULLABLE"),
            description=c.get("description", ""),
        )
        for c in campos_json
    ]


def obtener_campos_actuales(cliente: bigquery.Client) -> set:
    try:
        return {campo.name for campo in cliente.get_table(TABLA_COMPLETA).schema}
    except NotFound:
        logger.error(f"Tabla {TABLA_COMPLETA} no existe")
        sys.exit(1)


def campos_faltantes(cliente: bigquery.Client) -> list:
    en_bq = obtener_campos_actuales(cliente)
    return [f for f in cargar_schema_objetivo() if f.name not in en_bq]


def verificar(cliente: bigquery.Client) -> None:
    en_bq = obtener_campos_actuales(cliente)
    objetivo = {f.name for f in cargar_schema_objetivo()}
    faltantes = objetivo - en_bq
    extras = en_bq - objetivo

    print(f"\n{'='*60}")
    print(f"  Tabla: {TABLA_COMPLETA}")
    print(f"  Campos en BQ:    {len(en_bq)}")
    print(f"  Campos objetivo: {len(objetivo)}")
    print(f"{'='*60}")
    if faltantes:
        print(f"\n  ⚠️  Faltantes ({len(faltantes)}):")
        for c in sorted(faltantes):
            print(f"    - {c}")
    else:
        print("\n  ✅ Todos los campos del schema están presentes")
    if extras:
        print(f"\n  ℹ️  Extra en BQ (no en schema): {sorted(extras)}")
    print()


def migrar(cliente: bigquery.Client, dry_run: bool) -> None:
    nuevos = campos_faltantes(cliente)
    if not nuevos:
        logger.info("No hay campos nuevos que agregar — la tabla ya está actualizada.")
        return

    logger.info(f"Campos a agregar: {[f.name for f in nuevos]}")
    if dry_run:
        logger.info("[DRY-RUN] No se realizaron cambios.")
        return

    tabla = cliente.get_table(TABLA_COMPLETA)
    tabla.schema = list(tabla.schema) + nuevos
    cliente.update_table(tabla, ["schema"])
    logger.info(f"✓ Schema actualizado: {len(tabla.schema)} campos")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='No aplica cambios')
    parser.add_argument('--verificar', action='store_true', help='Solo comparar schemas')
    args = parser.parse_args()

    cliente = bigquery.Client(project=GCP_PROJECT)
    if args.verificar:
        verificar(cliente)
        return 0
    migrar(cliente, args.dry_run)
    verificar(cliente)
    return 0


if __name__ == "__main__":
    sys.exit(main())
