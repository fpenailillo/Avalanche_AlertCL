"""
Cloud Function HTTP que recibe observaciones de la comunidad enviadas desde el
frontend (GitHub Pages) y las guarda en la arquitectura GCP del proyecto:

  - Fotos (opcionales, base64) → bucket privado de GCS
  - Registro → tabla BigQuery clima.observaciones_comunidad

Endpoint público (sin auth, lo invoca un sitio estático anónimo), con CORS
restringido al dominio del frontend y validación básica de tamaño/tipo.
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import functions_framework
from google.cloud import bigquery, storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("receptor_observaciones")

PROYECTO = os.environ.get("GCP_PROJECT", "climas-chileno")
DATASET = os.environ.get("DATASET_CLIMA", "clima")
TABLA = "observaciones_comunidad"
BUCKET_FOTOS = os.environ.get("BUCKET_FOTOS", "avalanche-alertcl-observaciones")

ORIGEN_PERMITIDO = "https://fpenailillo.github.io"

MAX_FOTOS = 2
MAX_BYTES_FOTO = 6 * 1024 * 1024  # 6 MB por foto (ya decodificada)
TIPOS_FOTO = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_TEXTO = 4000


def _cors(respuesta_body, codigo=200):
    """Adjunta headers CORS a la respuesta."""
    headers = {
        "Access-Control-Allow-Origin": ORIGEN_PERMITIDO,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }
    return (respuesta_body, codigo, headers)


def _limpiar(texto, maximo=MAX_TEXTO):
    if texto is None:
        return None
    return str(texto).strip()[:maximo] or None


def _subir_fotos(fotos, id_obs):
    """Sube fotos base64 a GCS y devuelve la lista de rutas gs://."""
    if not fotos:
        return []
    if len(fotos) > MAX_FOTOS:
        raise ValueError(f"Máximo {MAX_FOTOS} fotos")

    bucket = storage.Client(project=PROYECTO).bucket(BUCKET_FOTOS)
    rutas = []
    for i, foto in enumerate(fotos):
        tipo = (foto.get("tipo") or "").lower()
        if tipo not in TIPOS_FOTO:
            raise ValueError(f"Tipo de imagen no permitido: {tipo}")
        datos_b64 = foto.get("datos_base64") or ""
        # Acepta data URLs ("data:image/jpeg;base64,....")
        if "," in datos_b64 and datos_b64.strip().startswith("data:"):
            datos_b64 = datos_b64.split(",", 1)[1]
        try:
            binario = base64.b64decode(datos_b64, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Foto base64 inválida") from exc
        if len(binario) > MAX_BYTES_FOTO:
            raise ValueError("Foto supera el tamaño máximo (6 MB)")

        ext = TIPOS_FOTO[tipo]
        ruta = f"observaciones/{id_obs}/foto_{i + 1}.{ext}"
        blob = bucket.blob(ruta)
        blob.upload_from_string(binario, content_type=tipo, timeout=60)
        rutas.append(f"gs://{BUCKET_FOTOS}/{ruta}")
    return rutas


@functions_framework.http
def recibir_observacion(solicitud):
    # Preflight CORS
    if solicitud.method == "OPTIONS":
        return _cors("", 204)

    if solicitud.method != "POST":
        return _cors(json.dumps({"error": "Método no permitido"}), 405)

    try:
        cuerpo = solicitud.get_json(silent=True) or {}
    except Exception:  # noqa: BLE001
        return _cors(json.dumps({"error": "JSON inválido"}), 400)

    nombre = _limpiar(cuerpo.get("nombre"), 200)
    contacto = _limpiar(cuerpo.get("contacto"), 200)
    comentarios = _limpiar(cuerpo.get("comentarios"))
    centro = _limpiar(cuerpo.get("centro"), 120)
    fecha_obs = _limpiar(cuerpo.get("fecha_observacion"), 10)

    # Validación mínima: comentarios obligatorios y algún dato de contacto.
    if not comentarios:
        return _cors(json.dumps({"error": "Los comentarios son obligatorios"}), 400)
    if not nombre and not contacto:
        return _cors(json.dumps({"error": "Indica al menos nombre o contacto"}), 400)

    id_obs = uuid.uuid4().hex
    try:
        rutas_fotos = _subir_fotos(cuerpo.get("fotos") or [], id_obs)
    except ValueError as exc:
        return _cors(json.dumps({"error": str(exc)}), 400)
    except Exception:  # noqa: BLE001
        logger.exception("Error subiendo fotos")
        return _cors(json.dumps({"error": "No se pudieron guardar las fotos"}), 500)

    fila = {
        "id": id_obs,
        "fecha_registro": datetime.now(timezone.utc).isoformat(),
        "fecha_observacion": fecha_obs,
        "nombre": nombre,
        "contacto": contacto,
        "centro": centro,
        "comentarios": comentarios,
        "fotos": json.dumps(rutas_fotos, ensure_ascii=False),
        "origen": "frontend-poc",
        "user_agent": _limpiar(solicitud.headers.get("User-Agent"), 300),
    }

    try:
        cliente = bigquery.Client(project=PROYECTO)
        errores = cliente.insert_rows_json(f"{PROYECTO}.{DATASET}.{TABLA}", [fila])
        if errores:
            logger.error("Errores BQ: %s", errores)
            return _cors(json.dumps({"error": "No se pudo registrar"}), 500)
    except Exception:  # noqa: BLE001
        logger.exception("Error insertando en BigQuery")
        return _cors(json.dumps({"error": "No se pudo registrar"}), 500)

    logger.info("Observación registrada: %s (%s fotos)", id_obs, len(rutas_fotos))
    return _cors(json.dumps({"ok": True, "id": id_obs, "fotos": len(rutas_fotos)}), 200)
