"""
Fase E (H3): modelo supervisado de features IMIS → nivel EAWS publicado.

Mide si las features meteo+snowpack disponibles permiten alcanzar el rendimiento de
Techel 2022 (QWK 0.59) con un modelo supervisado (como DEAPSnow RF), separando la
capacidad predictiva de los datos del gap del agentic loop (v25.19: QWK 0.444).

- Features: físicas de slf_meteo_snowpack (NO dangerLevel → evita circularidad).
- GT: slf_danger_levels_qc (nivel publicado, el de Techel).
- Split temporal: train 2010-2016 / test 2017-2019 (sin fuga).
- Compara: modelo (este) vs DEAPSnow RF (dangerLevel) vs Techel (0.59) vs agentic (0.444).

Uso: python notebooks_validacion/modelo_h3_supervisado.py
"""
import os
import sys
import argparse
import numpy as np
import joblib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from google.cloud import bigquery
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import f1_score, confusion_matrix

mod7 = __import__("07_validacion_slf_suiza", fromlist=["calcular_kappa_ponderado_cuadratico"])
_qwk = mod7.calcular_kappa_ponderado_cuadratico

GCP_PROJECT = "climas-chileno"
GUARDAR = False
FEATURES = [
    "HS_meas", "HN24", "HN72_24", "HN24_7d", "SWE", "TA", "TSS_mod", "RH", "VW", "DW",
    "wind_trans24", "hoar_size", "pwl_100", "base_pwl", "ssi_pwl", "sk38_pwl",
    "sn38_pwl", "ccl_pwl", "Sclass2", "elevation_station",
]


def qwk(y, p):
    return _qwk(list(map(int, y)), list(map(int, p)))["kappa_ponderado"]


def cargar():
    cli = bigquery.Client(project=GCP_PROJECT)
    cols = ", ".join(f"m.{c}" for c in FEATURES)
    sql = f"""
        SELECT EXTRACT(YEAR FROM m.datum) AS anio, {cols},
               m.dangerLevel AS deapsnow_rf, q.danger_level_qc AS gt
        FROM `{GCP_PROJECT}.validacion_avalanchas.slf_meteo_snowpack` m
        JOIN `{GCP_PROJECT}.validacion_avalanchas.slf_danger_levels_qc` q
          ON m.sector_id = q.sector_id AND DATE(m.datum) = q.date
        WHERE m.sector_id IN (4113, 2223, 6113) AND m.HS_meas IS NOT NULL
          AND q.danger_level_qc BETWEEN 1 AND 5
          AND EXTRACT(YEAR FROM m.datum) BETWEEN 2010 AND 2019
    """
    return cli.query(sql).to_dataframe()


def bootstrap_ic(y, p, n=2000, seed=42):
    rng = np.random.default_rng(seed)
    y, p = np.array(y), np.array(p)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) > 1 and len(set(p[idx])) > 1:
            vals.append(qwk(y[idx], p[idx]))
    if not vals:
        return float("nan"), float("nan")  # predicción constante (sanity naïve)
    return np.percentile(vals, 2.5), np.percentile(vals, 97.5)


def reporte(nombre, y, p):
    y, p = np.array(y, int), np.array(p, int)
    lo, hi = bootstrap_ic(y, p)
    print(f"\n  {nombre}")
    print(f"    QWK={qwk(y,p):.3f}  IC95%=[{lo:.3f}, {hi:.3f}]  "
          f"F1m={f1_score(y,p,average='macro',zero_division=0):.3f}  "
          f"acc={np.mean(y==p):.3f}  acc±1={np.mean(np.abs(y-p)<=1):.3f}")


def main():
    df = cargar()
    tr = df[df.anio <= 2016]
    te = df[df.anio >= 2017]
    print(f"Train (2010-2016): n={len(tr)} | Test (2017-2019): n={len(te)}")

    Xtr, Xte = tr[FEATURES].astype(float), te[FEATURES].astype(float)
    ytr, yte = tr["gt"].astype(int), te["gt"].astype(int)

    print("\n" + "=" * 64)
    print("H3 — MODELO SUPERVISADO features IMIS → nivel publicado (test 2017-2019)")
    print("=" * 64)

    # 1) RandomForest (réplica DEAPSnow/Techel) — imputar nulos con mediana del train
    med = Xtr.median()
    rf = RandomForestClassifier(n_estimators=400, class_weight="balanced",
                                random_state=42, n_jobs=-1)
    rf.fit(Xtr.fillna(med), ytr)
    reporte("RandomForest (class_weight=balanced)", yte, rf.predict(Xte.fillna(med)))

    if GUARDAR:
        ruta = os.path.join(os.path.dirname(__file__), "..", "agentes", "validacion",
                            "modelo_h3_rf_train2016.joblib")
        joblib.dump({"model": rf, "features": FEATURES,
                     "medianas": med.to_dict()}, ruta)
        print(f"\n  Artefacto guardado: {os.path.abspath(ruta)} "
              f"(RF train 2010-2016, {len(FEATURES)} features)")

    # 2) HistGradientBoosting (maneja NaN nativamente)
    hgb = HistGradientBoostingClassifier(random_state=42, max_iter=400)
    hgb.fit(Xtr, ytr)
    reporte("HistGradientBoosting (NaN-aware)", yte, hgb.predict(Xte))

    # 3) Baselines de referencia
    reporte("DEAPSnow RF (dangerLevel) — techo de las features", yte, te["deapsnow_rf"].round().astype(int))
    reporte("Naïve 'siempre N3' (sanity)", yte, np.full(len(te), 3))

    print("\n  Referencias: agentic loop v25.19 = 0.444 | Techel 2022 = 0.590")

    # Matriz del RF
    p_rf = rf.predict(Xte.fillna(med))
    niveles = sorted(set(yte) | set(p_rf))
    cm = confusion_matrix(yte, p_rf, labels=niveles)
    print("\n  Matriz RF (filas=GT, cols=pred):")
    print("     " + "  ".join(f"P{n}" for n in niveles))
    for i, n in enumerate(niveles):
        print(f"  GT{n} " + "  ".join(f"{cm[i][j]:3d}" for j in range(len(niveles))))

    # Feature importance
    imp = sorted(zip(FEATURES, rf.feature_importances_), key=lambda x: -x[1])
    print("\n  Top-8 feature importance (RF):")
    for f, v in imp[:8]:
        print(f"    {f:18s} {v:.3f}")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--guardar", action="store_true",
                     help="Serializar el RF (train 2010-2016) a artefacto joblib para inferencia")
    GUARDAR = _ap.parse_args().guardar
    main()
