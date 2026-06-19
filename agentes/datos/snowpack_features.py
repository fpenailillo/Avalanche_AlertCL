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
import os
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


# ─── Fase F: nivel base alpino por modelo supervisado (RF features IMIS) ──────────
# Solo VALIDACIÓN (flag USE_RF_ALPES). Lee las features directo de slf_meteo_snowpack
# (mismos nombres que el entrenamiento) y predice el nivel con el artefacto RF
# train-2010-2016. No operacional (requiere IMIS histórico).

_RF_ARTIFACT = None
_SECTOR_IDS_RF = {"Interlaken": 4113, "Matterhorn Zermatt": 2223, "St Moritz": 6113}


def _cargar_rf():
    global _RF_ARTIFACT
    if _RF_ARTIFACT is None:
        import joblib
        ruta = os.path.join(os.path.dirname(__file__), "..", "validacion",
                            "modelo_h3_rf_train2016.joblib")
        _RF_ARTIFACT = joblib.load(ruta)
    return _RF_ARTIFACT


@lru_cache(maxsize=512)
def nivel_rf_alpes(nombre_ubicacion: str, fecha: str):
    """Nivel EAWS predicho por el RF de snowpack para una estación alpina/fecha.
    Retorna int 1-5, o None si no es estación alpina, no hay datos o falta el artefacto."""
    sid = _SECTOR_IDS_RF.get(nombre_ubicacion)
    if sid is None or not fecha:
        return None
    try:
        art = _cargar_rf()
        feats, med, model = art["features"], art["medianas"], art["model"]
        from google.cloud import bigquery
        cli = bigquery.Client(project=GCP_PROJECT)
        cols = ", ".join(feats)
        sql = f"""
            SELECT {cols}
            FROM `{GCP_PROJECT}.validacion_avalanchas.slf_meteo_snowpack`
            WHERE sector_id = @sid AND DATE(datum) = @f AND HS_meas IS NOT NULL
            LIMIT 1
        """
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("sid", "INT64", sid),
            bigquery.ScalarQueryParameter("f", "DATE", fecha),
        ])
        filas = list(cli.query(sql, job_config=cfg).result())
        if not filas:
            return None
        row = dict(filas[0])
        x = [[float(row[f]) if row.get(f) is not None else float(med[f]) for f in feats]]
        nivel = int(model.predict(x)[0])
        logger.info(f"[NivelRF-Alpes] {nombre_ubicacion} {fecha} → nivel RF={nivel}")
        return nivel
    except Exception as exc:
        logger.warning(f"[NivelRF-Alpes] error {nombre_ubicacion} {fecha}: {exc}")
        return None
