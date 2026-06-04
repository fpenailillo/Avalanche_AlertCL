"""
Cache de outputs S1-S4 por (ubicación, fecha).

Permite el modo --solo-s5 en reprocesar_retroactivo.py:
los subagentes 1-4 son determinísticos respecto a la fecha histórica
(BigQuery devuelve los mismos datos), por lo que solo S5 necesita
re-ejecutarse cuando cambia la lógica del integrador.

Flujo:
  1. --generar-cache: ejecuta S1-S4 normalmente y persiste resultados aquí.
  2. --solo-s5: carga resultados S1-S4 del cache y ejecuta solo S5.

Reduce ~120 runs × 100s → 120 runs × 2s = ~4 min por ciclo de validación.
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)


def _ruta_archivo(cache_dir: str, ubicacion: str, fecha_str: str) -> str:
    nombre = re.sub(r"[^a-z0-9]", "_", ubicacion.lower().strip())
    nombre = re.sub(r"_+", "_", nombre).strip("_")
    return os.path.join(cache_dir, f"{nombre}__{fecha_str}.json")


def guardar_cache(
    cache_dir: str,
    ubicacion: str,
    fecha_str: str,
    resultado_topo: dict,
    resultado_sat: dict,
    resultado_meteo: dict,
    resultado_nlp: dict,
    contexto_s4: str,
) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    ruta = _ruta_archivo(cache_dir, ubicacion, fecha_str)
    payload = {
        "ubicacion": ubicacion,
        "fecha_str": fecha_str,
        "resultado_topo": resultado_topo,
        "resultado_sat": resultado_sat,
        "resultado_meteo": resultado_meteo,
        "resultado_nlp": resultado_nlp,
        "contexto_s4": contexto_s4,
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"[CacheS1-S4] Guardado: {ruta}")


def cargar_cache(
    cache_dir: str,
    ubicacion: str,
    fecha_str: str,
) -> dict | None:
    """Retorna el payload del cache o None si no existe."""
    ruta = _ruta_archivo(cache_dir, ubicacion, fecha_str)
    if not os.path.exists(ruta):
        logger.warning(f"[CacheS1-S4] No encontrado: {ruta}")
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"[CacheS1-S4] Cargado: {ruta}")
    return data


def existe_cache(cache_dir: str, ubicacion: str, fecha_str: str) -> bool:
    return os.path.exists(_ruta_archivo(cache_dir, ubicacion, fecha_str))
