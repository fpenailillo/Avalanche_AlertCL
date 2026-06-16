"""
Features de capa débil persistente (snowpack IMIS) para el Integrador.

Fase D (H3): provee un helper cacheado que lee los índices de estabilidad de la
capa débil persistente desde `condiciones_actuales` (poblados por
cargar_imis_condiciones_actuales.py para fechas con datos IMIS DEAPSnow).
Análogo a wn2_features.py. Solo hay datos en Alpes histórico (2001-2020);
en Andes / fechas sin IMIS retorna disponible=False.
"""
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

GCP_PROJECT = "climas-chileno"


@lru_cache(maxsize=256)
def obtener_snowpack_imis(nombre_ubicacion: str, fecha: str) -> dict:
    """
    Lee pwl_100, ssi_pwl, sk38_pwl de condiciones_actuales (fuente IMIS_DEAPSnow_RF2)
    para una zona/fecha. Cacheado por (nombre_ubicacion, fecha).

    Returns dict con:
        - disponible (bool)   — False si no hay registro IMIS o error
        - pwl_100   (float)   — presencia de capa débil persistente (0-1)
        - ssi_pwl   (float)   — Snow Stability Index sobre la pwl (bajo = inestable)
        - sk38_pwl  (float)   — stability index a 38° (bajo = inestable)
    """
    base = dict(disponible=False, pwl_100=None, ssi_pwl=None, sk38_pwl=None)
    if not nombre_ubicacion or not fecha:
        return base
    try:
        from google.cloud import bigquery
        cliente = bigquery.Client(project=GCP_PROJECT)
        sql = f"""
            SELECT datos_json_crudo
            FROM `{GCP_PROJECT}.clima.condiciones_actuales`
            WHERE nombre_ubicacion = @ubic
              AND DATE(hora_actual) = @fecha
              AND JSON_VALUE(datos_json_crudo, '$.fuente') = 'IMIS_DEAPSnow_RF2'
            ORDER BY marca_tiempo_ingestion DESC
            LIMIT 1
        """
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("ubic",  "STRING", nombre_ubicacion),
            bigquery.ScalarQueryParameter("fecha", "DATE",   fecha),
        ])
        filas = list(cliente.query(sql, job_config=cfg).result())
        if not filas:
            return base
        crudo = json.loads(filas[0]["datos_json_crudo"])
        def _f(k):
            v = crudo.get(k)
            try:
                return float(v) if v is not None else None
            except (ValueError, TypeError):
                return None
        pwl, ssi, sk38 = _f("pwl_100"), _f("ssi_pwl"), _f("sk38_pwl")
        if pwl is None and ssi is None and sk38 is None:
            return base
        logger.info(
            f"[SnowpackIMIS] '{nombre_ubicacion}' {fecha}: pwl_100={pwl} ssi_pwl={ssi} sk38_pwl={sk38}"
        )
        return dict(disponible=True, pwl_100=pwl, ssi_pwl=ssi, sk38_pwl=sk38)
    except Exception as exc:
        logger.warning(f"[SnowpackIMIS] error '{nombre_ubicacion}' {fecha}: {exc}")
        return base


def invalidar_cache_snowpack() -> None:
    obtener_snowpack_imis.cache_clear()
