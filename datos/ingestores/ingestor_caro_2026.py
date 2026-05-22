"""
Ingestor del dataset Caro et al. 2026 → BigQuery climas-chileno.clima.snow_depth_caro_2026

Fuente: DOI 10.5281/zenodo.20089265 (CC BY 4.0)
Archivos: Southern_Andes_Snow_Depth_Dataset_v4.2.csv (wide, 5318 fechas × 69 estaciones)
           stations_data.csv (metadata de estaciones)

El dataset ya está con QC aplicado (solo se carga como qc_status='clean').
No hay archivo raw separado en Zenodo v4.2.

Tabla destino: climas-chileno.clima.snow_depth_caro_2026
  Partición  : observation_date (DAY)
  Clustering : station_id, basin

Nota: el REQ-2026-09 menciona 21 estaciones del Maipo. El dataset público
tiene 13 para esa cuenca (las 8 AMTC/Piuquenes son datos de campo no publicados).

Referencia obligatoria (CC BY 4.0):
    Medina, J., and Caro, A.: The Southern Andes Daily Snow Depth Dataset
    (2010–2024): quality-controlled dataset from Chile and Argentina,
    Zenodo [data set], doi:10.5281/zenodo.20089265, 2026.

Uso:
    python3 datos/ingestores/ingestor_caro_2026.py --zona maipo --dry-run
    python3 datos/ingestores/ingestor_caro_2026.py --zona elqui
    python3 datos/ingestores/ingestor_caro_2026.py --zona all
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT", "climas-chileno")
DATASET = "clima"
TABLA = "snow_depth_caro_2026"
TABLA_BQ = f"{GCP_PROJECT}.{DATASET}.{TABLA}"
SCHEMA_PATH = Path(__file__).parent / "schema_snow_depth_caro_2026.json"
DIRECTORIO_LOCAL = Path(__file__).parent.parent.parent / "data" / "external" / "caro_2026"
ARCHIVO_DATOS = "Southern_Andes_Snow_Depth_Dataset_v4.2.csv"
ARCHIVO_ESTACIONES = "stations_data.csv"
ZENODO_BASE = "https://zenodo.org/records/20089265/files"
TIMEOUT_DESCARGA = 300
LOTE_INSERCION = 10_000
PAPER_REFERENCE = "Medina & Caro 2026, doi:10.5281/zenodo.20089265"

# Basins presentes en el dataset (nombre exacto en stations_data.csv)
BASIN_MAIPO = "Río Maipo"
BASIN_ELQUI = "Río Elqui"

FILTROS_ZONA = {
    "maipo": BASIN_MAIPO,
    "elqui": BASIN_ELQUI,
    "all": None,
}


def _inferir_andean_zone(lat: float) -> str:
    """Infiere zona climática andina según latitud (Caro et al. 2026 clasificación)."""
    if lat > -27.0:
        return "Arid"
    if lat > -37.0:
        return "Mediterranean"
    return "Wet"


def _inferir_country(source: str) -> str:
    """IANIGLA es Argentina; el resto son instituciones chilenas."""
    return "AR" if source == "IANIGLA" else "CL"


# ── Helpers BigQuery ───────────────────────────────────────────────────────────

def _cargar_schema() -> list:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return [
            bigquery.SchemaField(
                name=c["name"],
                field_type=c["type"],
                mode=c.get("mode", "NULLABLE"),
                description=c.get("description", ""),
            )
            for c in json.load(f)
        ]


def _asegurar_tabla(bq: bigquery.Client) -> None:
    try:
        bq.get_table(TABLA_BQ)
    except NotFound:
        logger.info(f"[IngestorCaro2026] Creando tabla {TABLA_BQ}...")
        t = bigquery.Table(TABLA_BQ, schema=_cargar_schema())
        t.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="observation_date",
        )
        t.clustering_fields = ["station_id", "basin"]
        bq.create_table(t)
        logger.info("[IngestorCaro2026] Tabla creada.")


def _borrar_filas_existentes(bq: bigquery.Client, station_ids: list[str]) -> None:
    ids_str = ", ".join(f"'{sid}'" for sid in station_ids)
    sql = f"DELETE FROM `{TABLA_BQ}` WHERE station_id IN ({ids_str})"
    try:
        bq.query(sql).result()
        logger.info(f"[IngestorCaro2026] Filas previas eliminadas ({len(station_ids)} estaciones).")
    except Exception as exc:
        if "streaming buffer" in str(exc).lower():
            logger.warning("[IngestorCaro2026] Streaming buffer activo — DELETE omitido.")
        else:
            raise


# ── Descarga ───────────────────────────────────────────────────────────────────

def _descargar_si_no_existe(nombre: str) -> Path:
    destino = DIRECTORIO_LOCAL / nombre
    if destino.exists():
        logger.info(f"[IngestorCaro2026] Cache local: {nombre}")
        return destino
    DIRECTORIO_LOCAL.mkdir(parents=True, exist_ok=True)
    import requests
    url = f"{ZENODO_BASE}/{nombre}"
    logger.info(f"[IngestorCaro2026] Descargando {nombre}...")
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
                    print(f"\r  {pct}% ({round(descargado / 1_048_576, 1)} MB)", end="", flush=True)
    print()
    logger.info(f"[IngestorCaro2026] Descargado → {destino}")
    return destino


# ── Transformación ─────────────────────────────────────────────────────────────

def _cargar_y_transformar(zona: str) -> pd.DataFrame:
    """
    Lee los 2 CSVs, hace melt del wide format y retorna DataFrame long listo para BQ.

    Estructura real:
    - stations_data.csv: code_internal, name, lat, lon, elevation, basin, source
    - Southern_Andes_Snow_Depth_Dataset_v4.2.csv: date, [code_internal...] (wide)
    """
    ruta_estaciones = _descargar_si_no_existe(ARCHIVO_ESTACIONES)
    ruta_datos = _descargar_si_no_existe(ARCHIVO_DATOS)

    df_est = pd.read_csv(ruta_estaciones, encoding="utf-8-sig", dtype={"code_internal": str})
    df_est["code_internal"] = df_est["code_internal"].str.strip()

    # Filtrar por zona si aplica
    basin_filtro = FILTROS_ZONA.get(zona)
    if basin_filtro:
        df_est = df_est[df_est["basin"] == basin_filtro]
        if df_est.empty:
            logger.warning(f"[IngestorCaro2026] Sin estaciones para zona='{zona}'.")
            return pd.DataFrame()

    logger.info(
        f"[IngestorCaro2026] Zona '{zona}': {len(df_est)} estaciones "
        f"({list(df_est['name'])})"
    )

    # Leer CSV wide y conservar solo columnas de estaciones de la zona + date
    columnas_estacion = [c for c in df_est["code_internal"].tolist()]
    df_wide = pd.read_csv(
        ruta_datos, encoding="utf-8-sig",
        usecols=lambda c: c == "date" or c in columnas_estacion,
        parse_dates=["date"],
    )

    cols_presentes = [c for c in columnas_estacion if c in df_wide.columns]
    cols_faltantes = [c for c in columnas_estacion if c not in df_wide.columns]
    if cols_faltantes:
        logger.warning(f"[IngestorCaro2026] Estaciones no encontradas en CSV: {cols_faltantes}")

    if not cols_presentes:
        logger.warning("[IngestorCaro2026] Ninguna estación de la zona encontrada en el CSV.")
        return pd.DataFrame()

    # Wide → long
    df_long = df_wide.melt(
        id_vars=["date"],
        value_vars=cols_presentes,
        var_name="code_internal",
        value_name="snow_depth_cm",
    )
    df_long = df_long.rename(columns={"date": "observation_date"})

    # Join con metadata de estaciones
    df_long = df_long.merge(df_est, on="code_internal", how="left")

    # Agregar columnas derivadas
    df_long["station_id"] = df_long["code_internal"]
    df_long["station_name"] = df_long["name"].str.strip()
    df_long["elevation_m"] = df_long["elevation"]
    df_long["andean_zone"] = df_long["lat"].apply(_inferir_andean_zone)
    df_long["country"] = df_long["source"].apply(_inferir_country)
    df_long["data_source"] = df_long["source"]
    df_long["sensor_model"] = None
    df_long["qc_status"] = "clean"

    total = len(df_long)
    no_nulos = df_long["snow_depth_cm"].notna().sum()
    logger.info(
        f"[IngestorCaro2026] Transformación: {total} filas totales, "
        f"{no_nulos} con dato ({round(no_nulos/total*100,1)}% completitud)"
    )
    return df_long


def _construir_filas_bq(df: pd.DataFrame) -> list[dict]:
    ts_ingesta = datetime.now(timezone.utc).isoformat()
    filas = []
    for _, fila in df.iterrows():
        filas.append({
            "station_id": str(fila["station_id"]),
            "station_name": str(fila["station_name"]),
            "basin": str(fila.get("basin", "")),
            "andean_zone": str(fila["andean_zone"]),
            "country": str(fila["country"]),
            "latitude": float(fila["lat"]) if pd.notna(fila.get("lat")) else None,
            "longitude": float(fila["lon"]) if pd.notna(fila.get("lon")) else None,
            "elevation_m": float(fila["elevation_m"]) if pd.notna(fila.get("elevation_m")) else None,
            "observation_date": str(fila["observation_date"])[:10],
            "snow_depth_cm": float(fila["snow_depth_cm"]) if pd.notna(fila.get("snow_depth_cm")) else None,
            "qc_status": "clean",
            "data_source": str(fila["data_source"]),
            "sensor_model": None,
            "ingestion_timestamp": ts_ingesta,
            "paper_reference": PAPER_REFERENCE,
        })
    return filas


def _preparar_df_para_bq(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el DataFrame al schema exacto de la tabla BQ."""
    ts_ingesta = pd.Timestamp.now(tz="UTC")
    resultado = pd.DataFrame({
        "station_id": df["station_id"].astype(str),
        "station_name": df["station_name"].astype(str),
        "basin": df["basin"].astype(str),
        "andean_zone": df["andean_zone"].astype(str),
        "country": df["country"].astype(str),
        "latitude": pd.to_numeric(df["lat"], errors="coerce"),
        "longitude": pd.to_numeric(df["lon"], errors="coerce"),
        "elevation_m": pd.to_numeric(df["elevation_m"], errors="coerce"),
        "observation_date": pd.to_datetime(df["observation_date"]).dt.date,
        "snow_depth_cm": pd.to_numeric(df["snow_depth_cm"], errors="coerce"),
        "qc_status": "clean",
        "data_source": df["data_source"].astype(str),
        "sensor_model": None,
        "ingestion_timestamp": ts_ingesta,
        "paper_reference": PAPER_REFERENCE,
    })
    return resultado


def _insertar_dataframe(bq: bigquery.Client, df_raw: pd.DataFrame) -> dict:
    """
    Carga datos históricos usando load_table_from_dataframe en chunks anuales.

    BigQuery limita a 4000 particiones DAY por job. El dataset Caro 2026 cubre
    2010-2024 (~5318 fechas únicas), superando ese límite si se carga de una vez.
    Dividir por año (<366 particiones/job) resuelve el problema.

    Usa Load Jobs en lugar de insert_rows_json para evitar el límite de 3650 días
    del streaming insert.
    """
    import pyarrow  # requerido por load_table_from_dataframe

    df = _preparar_df_para_bq(df_raw)
    schema = _cargar_schema()
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    df["_anio"] = pd.to_datetime(df["observation_date"]).dt.year
    anos = sorted(df["_anio"].unique())
    total_filas = 0
    errores_total = []

    logger.info(f"[IngestorCaro2026] Cargando {len(df)} filas en {len(anos)} chunks anuales...")
    for anio in anos:
        chunk = df[df["_anio"] == anio].drop(columns=["_anio"])
        try:
            job = bq.load_table_from_dataframe(chunk, TABLA_BQ, job_config=job_config)
            job.result()
            total_filas += len(chunk)
            logger.info(f"[IngestorCaro2026] {anio}: {len(chunk)} filas OK.")
        except Exception as exc:
            logger.error(f"[IngestorCaro2026] Error en {anio}: {exc}")
            errores_total.append(f"{anio}: {exc}")

    return {
        "insertado": len(errores_total) == 0,
        "total_filas": total_filas,
        "errores": errores_total,
    }


# ── Función principal ──────────────────────────────────────────────────────────

def cargar_dataset_caro(
    bq: bigquery.Client | None,
    zona: str = "maipo",
    dry_run: bool = False,
) -> dict:
    """
    Descarga y carga el dataset Caro 2026 en BigQuery.

    Args:
        bq: Cliente BigQuery (None en dry_run).
        zona: 'maipo' | 'elqui' | 'all'
        dry_run: Si True, procesa sin escribir en BQ.

    Returns:
        dict con estadísticas de la carga.
    """
    df = _cargar_y_transformar(zona)

    if df.empty:
        return {"insertado": False, "razon": "sin_datos", "zona": zona}

    station_ids = df["station_id"].unique().tolist()
    n_estaciones = len(station_ids)
    n_filas = len(df)
    n_con_dato = int(df["snow_depth_cm"].notna().sum())

    logger.info(
        f"[IngestorCaro2026] zona='{zona}' | {n_estaciones} estaciones | "
        f"{n_filas} filas totales | {n_con_dato} filas con SD"
    )

    if dry_run:
        logger.info("[IngestorCaro2026] [DRY-RUN] Sin escritura en BigQuery.")
        return {
            "dry_run": True,
            "zona": zona,
            "n_estaciones": n_estaciones,
            "filas_procesadas": n_filas,
            "filas_con_dato": n_con_dato,
            "estaciones": station_ids,
        }

    _asegurar_tabla(bq)
    _borrar_filas_existentes(bq, station_ids)
    resultado = _insertar_dataframe(bq, df)
    resultado["zona"] = zona
    resultado["n_estaciones"] = n_estaciones
    return resultado


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingestor Caro et al. 2026 → BigQuery climas-chileno.clima.snow_depth_caro_2026"
    )
    parser.add_argument(
        "--zona",
        choices=["maipo", "elqui", "all"],
        default="maipo",
        help="Zona geográfica (default: maipo = Río Maipo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Procesar sin escribir en BigQuery",
    )
    args = parser.parse_args()

    logger.info(
        f"[IngestorCaro2026] Iniciando — zona={args.zona} dry_run={args.dry_run}"
    )

    bq = None if args.dry_run else bigquery.Client(project=GCP_PROJECT)

    resultado = cargar_dataset_caro(bq=bq, zona=args.zona, dry_run=args.dry_run)
    logger.info(f"[IngestorCaro2026] Resultado final: {resultado}")


if __name__ == "__main__":
    main()
