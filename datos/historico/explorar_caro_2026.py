"""
Exploración inicial del dataset Caro et al. 2026 (Zenodo 10.5281/zenodo.20089265).

Descarga el bundle, detecta el formato (CSV / NetCDF / HDF5) e imprime
un resumen de la estructura: archivos, columnas, estaciones disponibles,
rango temporal y tamaño. Guarda el resumen en JSON para uso posterior.

Uso:
    python datos/ingestores/explorar_caro_2026.py
    python datos/ingestores/explorar_caro_2026.py --output /tmp/caro_summary.json
    python datos/ingestores/explorar_caro_2026.py --solo-metadata
"""

import argparse
import json
import logging
import os
import sys
import zipfile
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

ZENODO_BASE = "https://zenodo.org/api/records/20089265"
DIRECTORIO_LOCAL = Path(__file__).parent.parent.parent / "data" / "external" / "caro_2026"
TIMEOUT_DESCARGA = 300


def _obtener_metadata_zenodo() -> dict:
    """Obtiene metadata del registro Zenodo sin descargar archivos."""
    logger.info("[ExplorarCaro2026] Consultando metadata Zenodo...")
    resp = requests.get(ZENODO_BASE, timeout=30)
    resp.raise_for_status()
    datos = resp.json()
    archivos = [
        {
            "nombre": f["key"],
            "tamano_mb": round(f["size"] / 1_048_576, 2),
            "url": f["links"]["self"],
            "checksum": f.get("checksum", ""),
        }
        for f in datos.get("files", [])
    ]
    return {
        "doi": datos.get("doi", ""),
        "titulo": datos.get("metadata", {}).get("title", ""),
        "fecha_publicacion": datos.get("metadata", {}).get("publication_date", ""),
        "archivos": archivos,
    }


def _descargar_archivo(url: str, destino: Path) -> None:
    if destino.exists():
        logger.info(f"[ExplorarCaro2026] Ya existe: {destino.name} — omitiendo descarga")
        return
    logger.info(f"[ExplorarCaro2026] Descargando {destino.name}...")
    with requests.get(url, stream=True, timeout=TIMEOUT_DESCARGA) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        descargado = 0
        with open(destino, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1_048_576):
                f.write(chunk)
                descargado += len(chunk)
                if total:
                    pct = round(100 * descargado / total)
                    print(f"\r  {pct}% ({round(descargado/1_048_576,1)} MB)", end="", flush=True)
    print()
    logger.info(f"[ExplorarCaro2026] Descargado → {destino}")


def _descomprimir_si_es_zip(ruta: Path) -> list[Path]:
    if ruta.suffix.lower() != ".zip":
        return [ruta]
    destino_dir = ruta.parent / ruta.stem
    destino_dir.mkdir(exist_ok=True)
    logger.info(f"[ExplorarCaro2026] Descomprimiendo {ruta.name}...")
    with zipfile.ZipFile(ruta) as z:
        z.extractall(destino_dir)
    archivos = list(destino_dir.rglob("*"))
    logger.info(f"[ExplorarCaro2026] Extraídos {len(archivos)} archivos en {destino_dir}")
    return archivos


def _detectar_formato_y_resumir(ruta: Path) -> dict | None:
    """Analiza un archivo de datos y retorna resumen de estructura."""
    sufijo = ruta.suffix.lower()
    resumen: dict = {"archivo": ruta.name, "formato": sufijo, "ruta_local": str(ruta)}

    if sufijo in (".csv", ".tsv"):
        try:
            import pandas as pd
            sep = "\t" if sufijo == ".tsv" else ","
            df = pd.read_csv(ruta, sep=sep, nrows=5)
            total = sum(1 for _ in open(ruta)) - 1
            resumen.update({
                "columnas": list(df.columns),
                "n_filas_total": total,
                "muestra_valores": df.head(3).to_dict(orient="records"),
            })
            return resumen
        except Exception as exc:
            resumen["error"] = str(exc)
            return resumen

    if sufijo in (".nc", ".nc4", ".netcdf"):
        try:
            import xarray as xr
            ds = xr.open_dataset(ruta)
            resumen.update({
                "variables": list(ds.data_vars),
                "coordenadas": list(ds.coords),
                "dimensiones": dict(ds.dims),
                "atributos_globales": dict(ds.attrs),
            })
            ds.close()
            return resumen
        except Exception as exc:
            resumen["error"] = str(exc)
            return resumen

    if sufijo in (".h5", ".hdf5", ".he5"):
        try:
            import h5py
            with h5py.File(ruta, "r") as f:
                def _listar(nombre, obj):
                    if hasattr(obj, "shape"):
                        resumen.setdefault("datasets_hdf5", {})[nombre] = {
                            "shape": obj.shape,
                            "dtype": str(obj.dtype),
                        }
                f.visititems(_listar)
            return resumen
        except Exception as exc:
            resumen["error"] = str(exc)
            return resumen

    return None


def main():
    parser = argparse.ArgumentParser(description="Explorar dataset Caro et al. 2026")
    parser.add_argument("--output", default=str(DIRECTORIO_LOCAL / "resumen_exploracion.json"),
                        help="Ruta del JSON de salida")
    parser.add_argument("--solo-metadata", action="store_true",
                        help="Solo obtener metadata Zenodo, sin descargar archivos")
    args = parser.parse_args()

    DIRECTORIO_LOCAL.mkdir(parents=True, exist_ok=True)

    meta = _obtener_metadata_zenodo()
    logger.info(f"[ExplorarCaro2026] DOI: {meta['doi']}")
    logger.info(f"[ExplorarCaro2026] Título: {meta['titulo']}")
    logger.info(f"[ExplorarCaro2026] Archivos encontrados: {len(meta['archivos'])}")
    for a in meta["archivos"]:
        logger.info(f"  - {a['nombre']} ({a['tamano_mb']} MB)")

    if args.solo_metadata:
        ruta_salida = Path(args.output)
        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        logger.info(f"[ExplorarCaro2026] Metadata guardada en {ruta_salida}")
        return

    resumenes_datos = []
    for archivo_info in meta["archivos"]:
        nombre = archivo_info["nombre"]
        ruta_local = DIRECTORIO_LOCAL / nombre
        _descargar_archivo(archivo_info["url"], ruta_local)
        archivos_expandidos = _descomprimir_si_es_zip(ruta_local)
        for ruta_expandida in archivos_expandidos:
            if ruta_expandida.is_file():
                resumen = _detectar_formato_y_resumir(ruta_expandida)
                if resumen:
                    resumenes_datos.append(resumen)
                    logger.info(f"[ExplorarCaro2026] Analizado: {ruta_expandida.name} → formato={resumen['formato']}")

    salida = {
        "metadata_zenodo": meta,
        "archivos_analizados": resumenes_datos,
    }
    ruta_salida = Path(args.output)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    logger.info(f"[ExplorarCaro2026] Resumen guardado en {ruta_salida}")


if __name__ == "__main__":
    main()
