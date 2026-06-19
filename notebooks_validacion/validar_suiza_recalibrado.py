"""
Valida H3 Suiza aplicando la calibración ACTUAL (coeficientes_calibracion.json) al
nivel crudo de los boletines v25.18, usando la función de producción
aplicar_calibracion_regional. Equivale al comportamiento operacional tras la
recalibración B2 (identidad) SIN re-ejecutar los subagentes (el raw es invariante).

Compara: calibrado viejo (+0.7, en BQ) vs recalibrado actual (identidad).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from google.cloud import bigquery
from agentes.validacion.calibrador import aplicar_calibracion_regional
mod7 = __import__("07_validacion_slf_suiza", fromlist=[
    "obtener_niveles_slf_preciso", "calcular_kappa_ponderado_cuadratico",
    "FECHAS_QC_2324_POR_ESTACION", "MAPEO_ESTACIONES_SLF", "obtener_nuestros_boletines",
])
qwk = mod7.calcular_kappa_ponderado_cuadratico
FECHAS = mod7.FECHAS_QC_2324_POR_ESTACION

GCP_PROJECT = "climas-chileno"
cli = bigquery.Client(project=GCP_PROJECT)

# raw + calibrado-en-BQ por (estacion, fecha)
q = """
SELECT nombre_ubicacion est, CAST(DATE(fecha_emision) AS STRING) f,
  nivel_eaws_24h cal_bq, COALESCE(nivel_eaws_24h_raw, nivel_eaws_24h) raw
FROM `climas-chileno.clima.boletines_riesgo`
WHERE STARTS_WITH(version_prompts,'v25.18')
  AND nombre_ubicacion IN ('Interlaken','Matterhorn Zermatt','St Moritz')
QUALIFY ROW_NUMBER() OVER (PARTITION BY nombre_ubicacion, DATE(fecha_emision) ORDER BY fecha_emision DESC)=1
"""
pred = {(r["est"], r["f"]): (r["cal_bq"], r["raw"]) for r in cli.query(q).result()}

todas = sorted({f for fs in FECHAS.values() for f in fs})
gt_dict, _meta = mod7.obtener_niveles_slf_preciso(cli, todas)

gt, cal_bq, recal = [], [], []
for est, fechas in FECHAS.items():
    for f in fechas:
        if (est, f) in pred and (est, f) in gt_dict:
            cb, raw = pred[(est, f)]
            gt.append(int(gt_dict[(est, f)]))
            cal_bq.append(int(cb))
            # aplicar la calibración de PRODUCCIÓN actual (identidad tras B2) al raw
            recal.append(int(aplicar_calibracion_regional(float(raw), "alpes_swiss")))

def m(y, p):
    y, p = np.array(y), np.array(p)
    return (f"QWK={qwk(y.tolist(), p.tolist())['kappa_ponderado']:.4f}  "
            f"sesgo={np.mean(p-y):+.3f}  acc={np.mean(y==p):.3f}  acc±1={np.mean(np.abs(y-p)<=1):.3f}")

print(f"n={len(gt)}")
print(f"  Calibrado VIEJO (+0.7, en BQ):       {m(gt, cal_bq)}")
print(f"  RECALIBRADO actual (identidad B2):   {m(gt, recal)}")
import collections
print(f"  dist recalibrado: {dict(sorted(collections.Counter(recal).items()))}")
print(f"  dist GT         : {dict(sorted(collections.Counter(gt).items()))}")
