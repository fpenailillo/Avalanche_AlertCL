#!/usr/bin/env python3
"""
Migración del schema de boletines_riesgo: 35 → 37 campos (v7.0).

Agrega 2 campos de trazabilidad FIX-S1-SEMANTICA:
  - problema_avalancha_presente (BOOL)
  - tipo_problema_eaws (STRING)

Uso:
  python migrar_schema_boletines_v7.py [--dry-run] [--verificar]

Requiere: gcloud auth application-default login
"""

import argparse
import json
import logging
import os
import sys

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT") or os.environ.get("ID_PROYECTO", "climas-chileno")
DATASET = os.environ.get("DATASET_ID", "clima")
TABLA = "boletines_riesgo"
TABLA_COMPLETA = f"{GCP_PROJECT}.{DATASET}.{TABLA}"

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'salidas', 'schema_boletines.json'
)

CAMPOS_NUEVOS_V7 = {"problema_avalancha_presente", "tipo_problema_eaws"}


def obtener_campos_actuales(cliente: bigquery.Client) -> set:
    try:
        tabla = cliente.get_table(TABLA_COMPLETA)
        return {campo.name for campo in tabla.schema}
    except NotFound:
        logger.error(f"Tabla {TABLA_COMPLETA} no existe")
        sys.exit(1)


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


def verificar(cliente: bigquery.Client):
    campos_bq = obtener_campos_actuales(cliente)
    schema_obj = cargar_schema_objetivo()
    campos_objetivo = {c.name for c in schema_obj}

    faltantes = campos_objetivo - campos_bq
    extras = campos_bq - campos_objetivo

    print(f"\n{'='*60}")
    print(f"  Tabla: {TABLA_COMPLETA}")
    print(f"  Campos en BQ:     {len(campos_bq)}")
    print(f"  Campos objetivo:  {len(campos_objetivo)}")
    print(f"{'='*60}")

    if faltantes:
        print(f"\n  ⚠️  Campos FALTANTES ({len(faltantes)}):")
        for c in sorted(faltantes):
            marcador = " ← v7.0" if c in CAMPOS_NUEVOS_V7 else ""
            print(f"    - {c}{marcador}")
    else:
        print("\n  ✅ Todos los campos del schema están presentes")

    if extras:
        print(f"\n  ℹ️  Campos EXTRA en BQ (no en schema):")
        for c in sorted(extras):
            print(f"    - {c}")
    print()


def migrar(cliente: bigquery.Client, dry_run: bool):
    campos_bq = obtener_campos_actuales(cliente)
    schema_objetivo = cargar_schema_objetivo()

    campos_a_agregar = [
        f for f in schema_objetivo
        if f.name in CAMPOS_NUEVOS_V7 and f.name not in campos_bq
    ]

    if not campos_a_agregar:
        logger.info("No hay campos nuevos que agregar — la tabla ya está actualizada.")
        return

    logger.info(f"Campos a agregar: {[f.name for f in campos_a_agregar]}")

    if dry_run:
        logger.info("[DRY-RUN] No se realizaron cambios.")
        return

    tabla = cliente.get_table(TABLA_COMPLETA)
    schema_actual = list(tabla.schema)
    schema_nuevo = schema_actual + campos_a_agregar
    tabla.schema = schema_nuevo
    cliente.update_table(tabla, ["schema"])
    logger.info(f"Migración completada. {len(campos_a_agregar)} campo(s) agregado(s).")


def main():
    parser = argparse.ArgumentParser(description="Migración schema boletines v7.0")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar cambios sin aplicar")
    parser.add_argument("--verificar", action="store_true", help="Solo verificar estado actual")
    args = parser.parse_args()

    cliente = bigquery.Client(project=GCP_PROJECT)

    if args.verificar:
        verificar(cliente)
    else:
        migrar(cliente, dry_run=args.dry_run)
        if args.dry_run:
            verificar(cliente)


if __name__ == "__main__":
    main()
