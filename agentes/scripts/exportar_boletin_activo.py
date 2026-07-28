"""
Regenera y publica el boletín activo del frontend desde BigQuery.

Toma el boletín más reciente de cada zona chilena en clima.boletines_riesgo
y publica el JSON consolidado en gs://avalanche-alertcl-boletines/.
Útil para refrescar el boletín sin re-ejecutar el pipeline completo
(la corrida diaria de generar_todos.py ya lo publica automáticamente).

Uso:
    python agentes/scripts/exportar_boletin_activo.py
    python agentes/scripts/exportar_boletin_activo.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from google.cloud import bigquery

from agentes.salidas.almacenador import (
    GCP_PROJECT,
    DATASET,
    TABLA_BOLETINES,
    _consolidar_registros,
    _derivar_tendencia,
    _nivel_valido,
    _parsear_boletin_texto,
    subir_boletin_activo,
    subir_boletin_fecha,
)
from agentes.datos.constantes_zonas import ZONAS_ANDES_CHILE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CAMPOS_BOLETIN = """nombre_ubicacion, fecha_emision, nivel_eaws_24h, nivel_eaws_48h,
    nivel_eaws_72h, confianza, viento_kmh, estado_pinn,
    factor_seguridad_pinn, estado_vit, score_anomalia_vit,
    datos_satelitales_disponibles, relatos_analizados,
    tipo_alud_predominante, indice_riesgo_historico,
    tipo_problema_eaws, wn2_avalanche_problem, boletin_texto"""

# Un boletín tiene lectura satelital utilizable (el ViT llegó a un veredicto)
VIT_UTIL = "estado_vit IS NOT NULL AND estado_vit NOT IN ('sin_datos')"

# El boletín publicado es SIEMPRE el más reciente de cada ubicación: la frescura
# meteorológica manda. El análisis ViT es intermitente (cobertura de pasadas y
# nubosidad dejan ~4-5 ubicaciones sin lectura cada día), así que sus campos se
# completan aparte con la última lectura útil de la ventana, fechada con
# fecha_satelital para que el frontend no la muestre como si fuera de hoy.
SQL_ULTIMOS_BOLETINES = f"""
WITH ventana AS (
    SELECT {CAMPOS_BOLETIN}
    FROM `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}`
    WHERE DATE(fecha_emision) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
),
ultimo_boletin AS (
    SELECT * FROM ventana
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY nombre_ubicacion ORDER BY fecha_emision DESC
    ) = 1
),
ultimo_satelital AS (
    SELECT nombre_ubicacion, estado_vit, score_anomalia_vit,
           datos_satelitales_disponibles, fecha_emision AS fecha_satelital
    FROM ventana
    WHERE {VIT_UTIL}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY nombre_ubicacion ORDER BY fecha_emision DESC
    ) = 1
)
SELECT
    b.* EXCEPT (estado_vit, score_anomalia_vit, datos_satelitales_disponibles),
    s.estado_vit, s.score_anomalia_vit, s.datos_satelitales_disponibles,
    s.fecha_satelital
FROM ultimo_boletin b
LEFT JOIN ultimo_satelital s USING (nombre_ubicacion)
"""

SQL_BOLETINES_FECHA = f"""
SELECT {CAMPOS_BOLETIN},
       IF({VIT_UTIL}, fecha_emision, NULL) AS fecha_satelital
FROM `{GCP_PROJECT}.{DATASET}.{TABLA_BOLETINES}`
WHERE DATE(fecha_emision) = @fecha
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY nombre_ubicacion ORDER BY fecha_emision DESC
) = 1
"""


def _registro_desde_fila_bq(fila) -> dict | None:
    """Convierte una fila de boletines_riesgo en el registro del boletín activo."""
    nivel = _nivel_valido(fila.nivel_eaws_24h)
    if nivel is None:
        return None

    parseado = _parsear_boletin_texto(fila.boletin_texto or "")
    nivel_48h = _nivel_valido(fila.nivel_eaws_48h)
    parseado["tendencia"] = _derivar_tendencia(nivel, nivel_48h, parseado.get("tendencia"))
    return {
        "ubicacion": fila.nombre_ubicacion,
        "nivel_eaws": nivel,
        "nivel_eaws_48h": nivel_48h,
        "nivel_eaws_72h": _nivel_valido(fila.nivel_eaws_72h),
        "confianza": fila.confianza,
        "viento_kmh": fila.viento_kmh,
        "manto": {
            "estado": fila.estado_pinn,
            "factor_seguridad": fila.factor_seguridad_pinn,
        },
        "satelital": {
            "estado": fila.estado_vit,
            "score_anomalia": fila.score_anomalia_vit,
            "datos_disponibles": bool(fila.datos_satelitales_disponibles),
            # Puede ser anterior al boletín: el ViT no tiene lectura todos los días
            "fecha": fila.fecha_satelital.isoformat() if fila.fecha_satelital else None,
        },
        "comunidad": {
            "relatos_analizados": fila.relatos_analizados,
            "tipo_alud_predominante": fila.tipo_alud_predominante,
            "indice_riesgo_historico": fila.indice_riesgo_historico,
        },
        "problema": fila.tipo_problema_eaws or fila.wn2_avalanche_problem,
        "emitido": fila.fecha_emision.isoformat() if fila.fecha_emision else None,
        **parseado,
    }


def regenerar_boletin_activo_desde_bq(fecha: str = None) -> Optional[dict]:
    """
    Re-consulta BigQuery por el boletín más reciente de cada zona chilena y
    consolida el resultado, sin subir nada a GCS.

    Usado tanto por este script (CLI) como por generar_todos.py, para que
    cualquier corrida — incluso con --ubicaciones parcial — republique el
    consolidado completo de producción en vez de solo lo que generó esa
    corrida (evita sobrescribir boletin_activo.json con un subconjunto).

    Returns:
        dict con {"boletines": [...], "zonas": [...]} o None si no hay datos.
    """
    cliente = bigquery.Client(project=GCP_PROJECT)
    if fecha:
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("fecha", "DATE", fecha),
        ])
        filas = list(cliente.query(SQL_BOLETINES_FECHA, job_config=job_config).result())
    else:
        filas = list(cliente.query(SQL_ULTIMOS_BOLETINES).result())
    logger.info(f"Boletines en BQ ({fecha or 'recientes'}): {len(filas)} ubicaciones")

    registros = [_registro_desde_fila_bq(f) for f in filas]
    boletines = _consolidar_registros(registros)

    if not boletines:
        return None

    zonas = [b["zona"] for b in boletines]
    logger.info(f"Zonas consolidadas ({ZONAS_ANDES_CHILE and 'andes_chile'}): {zonas}")
    return {"boletines": boletines, "zonas": zonas}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Imprimir el JSON sin subirlo a GCS')
    parser.add_argument('--fecha', type=str, default=None,
                        help='Exportar el boletín de una fecha (YYYY-MM-DD) a '
                             'historico/ sin tocar boletin_activo.json')
    args = parser.parse_args()

    resultado = regenerar_boletin_activo_desde_bq(args.fecha)
    if not resultado:
        logger.error("Sin boletines chilenos recientes para exportar")
        return 1
    boletines = resultado["boletines"]

    if args.dry_run:
        print(json.dumps({"boletines": boletines}, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.fecha:
        uri = subir_boletin_fecha(boletines, args.fecha, es_activo=False)
    else:
        uri = subir_boletin_activo(boletines)
    if uri:
        print(f"✓ Boletín publicado: {uri}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
