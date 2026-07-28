#!/usr/bin/env python3
"""
Reprocesa el problema típico EAWS de boletines ya emitidos (v25.19).

Hasta la v25.19, `tipo_problema_eaws` nunca se poblaba y el boletín publicaba el
problema del ensemble WN2, que decidía la fase por temperatura del aire a la
altitud de referencia. Los días de lluvia sobre nieve quedaron clasificados como
`new_snow` — La Parva, 25-jul-2026, con 11 h de lluvia observada.

Este script recalcula el problema con tool_clasificar_problema_eaws usando los
datos que ya están en BigQuery: NO re-ejecuta el pipeline ni el LLM, solo la
clasificación determinista. Actualiza `tipo_problema_eaws`,
`problemas_secundarios_eaws` y `cota_nieve_m`, y republica los boletines
históricos afectados.

Uso:
  python agentes/scripts/backfill_problema_eaws.py --desde 2026-07-24 --hasta 2026-07-28 --dry-run
  python agentes/scripts/backfill_problema_eaws.py --desde 2026-07-24 --hasta 2026-07-28
  python agentes/scripts/backfill_problema_eaws.py --desde ... --hasta ... --todos

Por defecto solo toca los días/ubicaciones con lluvia observada en
`pronostico_horas` (que son los que la clasificación anterior erraba). Con
`--todos` recorre todas las filas del rango.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from google.cloud import bigquery

from agentes.datos.consultor_bigquery import establecer_fecha_referencia_global
from agentes.datos.precipitacion import TIPOS_LLUVIA, TIPOS_MIXTOS
from agentes.salidas.almacenador import DATASET, GCP_PROJECT, TABLA_BOLETINES
from agentes.scripts.exportar_boletin_activo import regenerar_boletin_activo_desde_bq
from agentes.salidas.almacenador import subir_boletin_fecha
from agentes.subagentes.subagente_integrador.tools.tool_clasificar_problema_eaws import (
    ejecutar_clasificar_problema_eaws,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_TIPOS_LIQUIDOS = sorted(TIPOS_LLUVIA | TIPOS_MIXTOS)

# Días/ubicaciones con precipitación líquida observada: son los que la
# clasificación por temperatura del aire no podía ver.
SQL_DIAS_CON_LLUVIA = f"""
SELECT DISTINCT
    b.nombre_ubicacion,
    DATE(b.fecha_emision) AS fecha
FROM `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}` b
JOIN `{GCP_PROJECT}.{DATASET}.pronostico_horas` h
  ON h.nombre_ubicacion = b.nombre_ubicacion
 AND DATE(h.hora_inicio) = DATE(b.fecha_emision)
WHERE DATE(b.fecha_emision) BETWEEN @desde AND @hasta
  AND h.tipo_precipitacion IN UNNEST(@tipos_liquidos)
  AND h.cantidad_precipitacion > 0
ORDER BY fecha, nombre_ubicacion
"""

SQL_TODAS_LAS_FILAS = f"""
SELECT DISTINCT nombre_ubicacion, DATE(fecha_emision) AS fecha
FROM `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}`
WHERE DATE(fecha_emision) BETWEEN @desde AND @hasta
ORDER BY fecha, nombre_ubicacion
"""

SQL_PROBLEMA_ACTUAL = f"""
SELECT nombre_ubicacion, DATE(fecha_emision) AS fecha,
       tipo_problema_eaws, wn2_avalanche_problem, cota_nieve_m
FROM `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}`
WHERE DATE(fecha_emision) BETWEEN @desde AND @hasta
"""

SQL_ACTUALIZAR = f"""
UPDATE `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}`
SET tipo_problema_eaws = @problema,
    problemas_secundarios_eaws = @secundarios,
    cota_nieve_m = @cota,
    problema_avalancha_presente = @presente
WHERE nombre_ubicacion = @ubicacion
  AND DATE(fecha_emision) = @fecha
"""


def _parametros_rango(desde: str, hasta: str, con_tipos: bool = False) -> list:
    parametros = [
        bigquery.ScalarQueryParameter("desde", "DATE", desde),
        bigquery.ScalarQueryParameter("hasta", "DATE", hasta),
    ]
    if con_tipos:
        parametros.append(
            bigquery.ArrayQueryParameter("tipos_liquidos", "STRING", _TIPOS_LIQUIDOS)
        )
    return parametros


def objetivos(cliente, desde: str, hasta: str, todos: bool) -> list:
    sql = SQL_TODAS_LAS_FILAS if todos else SQL_DIAS_CON_LLUVIA
    job = cliente.query(sql, bigquery.QueryJobConfig(
        query_parameters=_parametros_rango(desde, hasta, con_tipos=not todos)
    ))
    return [(f.nombre_ubicacion, f.fecha.isoformat()) for f in job.result()]


def problemas_actuales(cliente, desde: str, hasta: str) -> dict:
    job = cliente.query(SQL_PROBLEMA_ACTUAL, bigquery.QueryJobConfig(
        query_parameters=_parametros_rango(desde, hasta)
    ))
    return {
        (f.nombre_ubicacion, f.fecha.isoformat()): {
            "problema": f.tipo_problema_eaws or f.wn2_avalanche_problem,
            "cota": f.cota_nieve_m,
        }
        for f in job.result()
    }


def reclasificar(ubicacion: str, fecha: str) -> dict:
    """Clasifica con la fecha del boletín como referencia global del consultor."""
    establecer_fecha_referencia_global(
        datetime.fromisoformat(f"{fecha}T23:59:59").replace(tzinfo=timezone.utc)
    )
    try:
        return ejecutar_clasificar_problema_eaws(ubicacion, fecha=fecha)
    finally:
        establecer_fecha_referencia_global(None)


def aplicar(cliente, ubicacion: str, fecha: str, resultado: dict) -> None:
    dominante = resultado.get("problema_dominante")
    cliente.query(SQL_ACTUALIZAR, bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("problema", "STRING", dominante),
        bigquery.ScalarQueryParameter(
            "secundarios", "STRING",
            json.dumps(resultado.get("problemas_secundarios") or [], ensure_ascii=False),
        ),
        bigquery.ScalarQueryParameter("cota", "INT64", resultado.get("cota_nieve_m")),
        bigquery.ScalarQueryParameter(
            "presente", "BOOL", bool(dominante and dominante != "no_distinct")
        ),
        bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
        bigquery.ScalarQueryParameter("fecha", "DATE", fecha),
    ])).result()


def _rango_fechas(desde: str, hasta: str):
    actual = datetime.strptime(desde, "%Y-%m-%d").date()
    fin = datetime.strptime(hasta, "%Y-%m-%d").date()
    while actual <= fin:
        yield actual.isoformat()
        actual += timedelta(days=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", required=True, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--hasta", required=True, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra los cambios sin escribir en BigQuery ni GCS")
    parser.add_argument("--todos", action="store_true",
                        help="Reprocesar todas las filas del rango, no solo las de días con lluvia")
    parser.add_argument("--sin-republicar", action="store_true",
                        help="Actualiza BigQuery pero no republica los JSON históricos")
    args = parser.parse_args()

    cliente = bigquery.Client(project=GCP_PROJECT)
    filas = objetivos(cliente, args.desde, args.hasta, args.todos)
    if not filas:
        logger.info("Sin boletines que reprocesar en el rango indicado.")
        return 0

    antes = problemas_actuales(cliente, args.desde, args.hasta)
    logger.info(f"Boletines a reclasificar: {len(filas)}")

    cambios = []
    for ubicacion, fecha in filas:
        resultado = reclasificar(ubicacion, fecha)
        if not resultado.get("disponible"):
            logger.warning(f"  {fecha} {ubicacion}: sin datos — se omite")
            continue

        previo = antes.get((ubicacion, fecha), {})
        nuevo = resultado.get("problema_dominante")
        if previo.get("problema") == nuevo and previo.get("cota") == resultado.get("cota_nieve_m"):
            continue

        cambios.append((ubicacion, fecha, previo.get("problema"), resultado))
        logger.info(
            f"  {fecha} {ubicacion}: {previo.get('problema')} → {nuevo} "
            f"(cota {resultado.get('cota_nieve_m')}, confianza {resultado.get('confianza')})"
        )

    if not cambios:
        logger.info("Ningún boletín cambia de problema — nada que aplicar.")
        return 0

    if args.dry_run:
        logger.info(f"[DRY-RUN] {len(cambios)} boletines cambiarían. Sin escrituras.")
        return 0

    for ubicacion, fecha, _, resultado in cambios:
        aplicar(cliente, ubicacion, fecha, resultado)
    logger.info(f"✓ BigQuery actualizado: {len(cambios)} boletines")

    if args.sin_republicar:
        return 0

    fechas_afectadas = sorted({fecha for _, fecha, _, _ in cambios})
    for fecha in fechas_afectadas:
        datos = regenerar_boletin_activo_desde_bq(fecha)
        if not datos:
            logger.warning(f"  {fecha}: sin boletines consolidados — no se republica")
            continue
        es_hoy = fecha == datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subir_boletin_fecha(datos["boletines"], fecha, es_activo=es_hoy)
    logger.info(f"✓ Republicados {len(fechas_afectadas)} boletines históricos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
