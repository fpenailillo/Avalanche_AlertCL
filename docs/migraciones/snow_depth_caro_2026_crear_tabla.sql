-- Tabla: climas-chileno.clima.snow_depth_caro_2026
-- Dataset: Caro et al. (2026) - Southern Andes Daily Snow Depth
-- DOI: 10.5281/zenodo.20089265  |  Licencia: CC BY 4.0
-- Partición: observation_date (DAY)  |  Clustering: station_id, basin

CREATE TABLE IF NOT EXISTS `climas-chileno.clima.snow_depth_caro_2026` (
  station_id        STRING    NOT NULL OPTIONS(description="Identificador único de estación"),
  station_name      STRING    NOT NULL OPTIONS(description="Nombre descriptivo de la estación"),
  basin             STRING    NOT NULL OPTIONS(description="Cuenca hidrográfica (Maipo, Elqui, Baker, etc.)"),
  andean_zone       STRING    NOT NULL OPTIONS(description="Zona climática: Arid | Mediterranean | Wet"),
  country           STRING    NOT NULL OPTIONS(description="País: CL | AR"),
  latitude          FLOAT64   NOT NULL OPTIONS(description="Latitud decimal WGS84"),
  longitude         FLOAT64   NOT NULL OPTIONS(description="Longitud decimal WGS84"),
  elevation_m       FLOAT64   NOT NULL OPTIONS(description="Elevación m.s.n.m."),
  observation_date  DATE      NOT NULL OPTIONS(description="Fecha de la observación diaria"),
  snow_depth_cm     FLOAT64            OPTIONS(description="Profundidad de nieve en cm (null=faltante/QC)"),
  qc_status         STRING    NOT NULL OPTIONS(description="raw | clean"),
  data_source       STRING    NOT NULL OPTIONS(description="DGA | CEAZA | UdeChile | CIEP | IANIGLA"),
  sensor_model      STRING             OPTIONS(description="Modelo de sensor ej: Campbell/SR50A"),
  ingestion_timestamp TIMESTAMP        OPTIONS(description="Timestamp de ingesta"),
  paper_reference   STRING             OPTIONS(description="Cita CC BY 4.0: doi:10.5281/zenodo.20089265")
)
PARTITION BY observation_date
CLUSTER BY station_id, basin
OPTIONS(
  description="Dataset Caro et al. 2026 - Profundidad de nieve diaria Andes del Sur 2010-2024. Requiere citar: Medina & Caro (2026), doi:10.5281/zenodo.20089265"
);
