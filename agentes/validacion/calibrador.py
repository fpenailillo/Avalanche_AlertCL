"""
FIX-CALIB-REG (Fase D, v21.0) — Calibración estadística post-LLM

Ajusta una regresión lineal simple (OLS) por región entre el nivel predicho
por el LLM y el ground truth EAWS. Aplicable solo si se cumplen gates:
  - n ≥ 20 pares GT disponibles
  - p-value(β) < 0.05 (la correlación pred→GT es estadísticamente significativa)
  - β ∈ [0.5, 2.0] (sin soluciones degeneradas)
  - ΔQWK_CV ≥ 0.03 sobre K=5-fold temporal (mejora real, no sobre-ajuste)

Modelo: nivel_calibrado = clip(round(α + β·nivel_predicho), 1, 5)

Uso (entrenamiento offline, requiere acceso BQ):
    python -m agentes.validacion.calibrador --entrenar --version v20
    python -m agentes.validacion.calibrador --verificar

Uso (aplicación online — importar en tool_clasificar_eaws.py):
    from agentes.validacion.calibrador import aplicar_calibracion_regional
    nivel_cal = aplicar_calibracion_regional(nivel, region)
"""

import json
import logging
import math
import os
import random
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Rutas ────────────────────────────────────────────────────────────────────
COEF_PATH = os.path.join(os.path.dirname(__file__), "coeficientes_calibracion.json")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "climas-chileno")

# ─── Hiperparámetros ──────────────────────────────────────────────────────────
BETA_MIN = 0.5           # β mínimo permitido (sin invertir la escala)
BETA_MAX = 2.0           # β máximo permitido (sin amplificación excesiva)
N_MIN = 20               # pares mínimos por región para calibrar
P_UMBRAL = 0.05          # p-value máximo para β ≠ 0
DELTA_QWK_MIN = 0.03     # mejora mínima en QWK por CV para aplicar
N_BOOTSTRAP = 1000       # iteraciones bootstrap para CI 95%
K_FOLDS = 5              # folds temporales para CV


# ═══════════════════════════════════════════════════════════════════════════════
# Primitivas estadísticas (stdlib only)
# ═══════════════════════════════════════════════════════════════════════════════

def _ols(x: List[float], y: List[float]) -> Tuple[float, float, float, float]:
    """OLS: y = α + β·x. Retorna (α, β, R², SE(β))."""
    n = len(x)
    if n < 2:
        return float(sum(y) / n if n else 0), 0.0, 0.0, float("inf")

    mx = sum(x) / n
    my = sum(y) / n
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    ss_yy = sum((yi - my) ** 2 for yi in y)

    if ss_xx == 0:
        return my, 0.0, 0.0, float("inf")

    beta = ss_xy / ss_xx
    alpha = my - beta * mx

    y_hat = [alpha + beta * xi for xi in x]
    ss_res = sum((yi - yhi) ** 2 for yi, yhi in zip(y, y_hat))

    r2 = 1.0 - ss_res / ss_yy if ss_yy > 0 else 0.0
    mse = ss_res / (n - 2) if n > 2 else 0.0
    se_beta = math.sqrt(mse / ss_xx) if ss_xx > 0 else float("inf")

    return alpha, beta, r2, se_beta


def _normal_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _p_value_two_sided(t_stat: float) -> float:
    """p-value bilateral usando aproximación normal (válida para n≥30)."""
    return 2.0 * (1.0 - _normal_cdf(abs(t_stat)))


def _qwk(pred: List[int], gt: List[int]) -> float:
    """Quadratic Weighted Kappa entre dos listas de enteros [1..5]."""
    n = len(pred)
    if n == 0:
        return 0.0

    niveles = [1, 2, 3, 4, 5]
    k = len(niveles)
    idx = {v: i for i, v in enumerate(niveles)}

    O = [[0] * k for _ in range(k)]
    for p, g in zip(pred, gt):
        pi = idx.get(p)
        gi = idx.get(g)
        if pi is not None and gi is not None:
            O[pi][gi] += 1

    O_n = [[O[i][j] / n for j in range(k)] for i in range(k)]
    fila = [sum(O_n[i][j] for j in range(k)) for i in range(k)]
    col = [sum(O_n[i][j] for i in range(k)) for j in range(k)]
    E = [[fila[i] * col[j] for j in range(k)] for i in range(k)]
    W = [[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)]

    num = sum(W[i][j] * O_n[i][j] for i in range(k) for j in range(k))
    den = sum(W[i][j] * E[i][j] for i in range(k) for j in range(k))

    return 1.0 - num / den if den > 0 else 0.0


def _calibrar(nivel: float, alpha: float, beta: float) -> int:
    return max(1, min(5, round(alpha + beta * nivel)))


# ═══════════════════════════════════════════════════════════════════════════════
# Validación cruzada temporal K-fold
# ═══════════════════════════════════════════════════════════════════════════════

def _cv_temporal(
    fechas: List[str],
    pred: List[float],
    gt: List[int],
    alpha: float,
    beta: float,
    k: int = K_FOLDS,
    shift_only: bool = False,
) -> Tuple[float, float]:
    """
    K-fold temporal con leave-one-fold-out correcto.

    Reestima coeficientes en cada fold usando solo datos de entrenamiento
    para evitar data leakage.

    Args:
        shift_only: si True, usa a_cv = mean_GT_train - mean_pred_train, b_cv = 1.0
                    (modelo shift-only por fold); si False, usa OLS completo.

    Retorna (QWK_sin_calibración, QWK_con_calibración) promediados sobre folds.
    """
    n = len(fechas)
    orden = sorted(range(n), key=lambda i: fechas[i])
    pred_s = [pred[i] for i in orden]
    gt_s = [gt[i] for i in orden]

    qwk_sin, qwk_con = [], []
    fold_size = n // k

    for fi in range(k):
        start = fi * fold_size
        end = start + fold_size if fi < k - 1 else n
        if end - start < 2:
            continue

        train_pred = pred_s[:start] + pred_s[end:]
        train_gt_f = [float(g) for g in gt_s[:start] + gt_s[end:]]

        if len(train_pred) < 4:
            continue

        if shift_only:
            mean_pred_t = sum(train_pred) / len(train_pred)
            mean_gt_t = sum(train_gt_f) / len(train_gt_f)
            a_cv = mean_gt_t - mean_pred_t
            b_cv = 1.0
        else:
            a_cv, b_cv, _, _ = _ols(train_pred, train_gt_f)

        test_sin = [max(1, min(5, round(p))) for p in pred_s[start:end]]
        test_con = [_calibrar(p, a_cv, b_cv) for p in pred_s[start:end]]
        test_gt_fold = [int(g) for g in gt_s[start:end]]

        qwk_sin.append(_qwk(test_sin, test_gt_fold))
        qwk_con.append(_qwk(test_con, test_gt_fold))

    if not qwk_sin:
        return 0.0, 0.0

    return sum(qwk_sin) / len(qwk_sin), sum(qwk_con) / len(qwk_con)


# ═══════════════════════════════════════════════════════════════════════════════
# Bootstrap CI 95% para α y β
# ═══════════════════════════════════════════════════════════════════════════════

def _bootstrap_ci(
    x: List[float], y: List[float], n_boot: int = N_BOOTSTRAP
) -> Dict:
    rng = random.Random(42)
    n = len(x)
    alphas, betas = [], []

    for _ in range(n_boot):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        xi = [x[i] for i in idx]
        yi = [y[i] for i in idx]
        try:
            a, b, _, _ = _ols(xi, yi)
            alphas.append(a)
            betas.append(b)
        except Exception:
            pass

    alphas.sort()
    betas.sort()
    lo = max(0, int(0.025 * len(alphas)))
    hi = min(len(alphas) - 1, int(0.975 * len(alphas)))

    return {
        "alpha_ci95": [round(alphas[lo], 4), round(alphas[hi], 4)],
        "beta_ci95": [round(betas[lo], 4), round(betas[hi], 4)],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Entrenamiento por región
# ═══════════════════════════════════════════════════════════════════════════════

def entrenar_calibracion(
    fechas: List[str],
    predichos: List[float],
    gt: List[int],
    region: str,
) -> Dict:
    """
    Ajusta calibración OLS para una región con validación estadística.

    Args:
        fechas: fechas ISO de cada par (para CV temporal)
        predichos: niveles predichos por el LLM (float o int)
        gt: ground truth EAWS (int, 1–5)
        region: 'alpes_swiss' | 'andes_chile'

    Returns:
        Dict con α, β, métricas y flag `calibracion_aplicable`.
    """
    n = len(predichos)
    base = {"region": region, "n": n, "calibracion_aplicable": False,
            "alpha": 0.0, "beta": 1.0}

    if n < N_MIN:
        base["razon_no_aplicar"] = f"n={n} < mínimo requerido {N_MIN}"
        logger.warning("[Calibrador] %s: n insuficiente (%d<%d)", region, n, N_MIN)
        return base

    x = [float(p) for p in predichos]
    y = [float(g) for g in gt]

    alpha, beta, r2, se_beta = _ols(x, y)

    t_stat = beta / se_beta if se_beta > 0 else float("inf")
    p_value = _p_value_two_sided(t_stat) if math.isfinite(t_stat) else 0.0

    ci = _bootstrap_ci(x, y)

    qwk_cv_sin, qwk_cv_con = _cv_temporal(fechas, x, [int(g) for g in y], alpha, beta)
    delta_qwk_cv = qwk_cv_con - qwk_cv_sin

    pred_round = [max(1, min(5, round(xi))) for xi in x]
    pred_cal = [_calibrar(xi, alpha, beta) for xi in x]
    gt_int = [int(yi) for yi in y]
    qwk_full_sin = _qwk(pred_round, gt_int)
    qwk_full_con = _qwk(pred_cal, gt_int)

    sesgo_antes = sum(x) / n - sum(y) / n
    sesgo_despues = sum(_calibrar(xi, alpha, beta) for xi in x) / n - sum(y) / n

    resultado = {
        **base,
        "alpha": round(alpha, 6),
        "beta": round(beta, 6),
        "r_squared": round(r2, 4),
        "t_stat_beta": round(t_stat, 4),
        "p_value_beta": round(p_value, 6),
        **ci,
        "qwk_cv_sin": round(qwk_cv_sin, 4),
        "qwk_cv_con": round(qwk_cv_con, 4),
        "delta_qwk_cv": round(delta_qwk_cv, 4),
        "qwk_full_sin": round(qwk_full_sin, 4),
        "qwk_full_con": round(qwk_full_con, 4),
        "sesgo_antes": round(sesgo_antes, 4),
        "sesgo_despues": round(sesgo_despues, 4),
        "n_pares": n,
    }

    # ─── Modelo shift-only (β=1.0 fijo) ──────────────────────────────────────
    # Corrección de sesgo sistemático sin escala. α = mean_GT - mean_pred.
    # Tiene sentido cuando el sesgo es claro y estable en el tiempo.
    # Gate adicional: |α_shift| ≥ 0.5 niveles (significación práctica).
    alpha_shift = sum(y) / n - sum(x) / n  # = mean_GT - mean_pred
    pred_shift = [_calibrar(xi, alpha_shift, 1.0) for xi in x]
    qwk_full_shift = _qwk(pred_shift, gt_int)
    qwk_cv_sin_shift, qwk_cv_con_shift = _cv_temporal(
        fechas, x, gt_int, alpha_shift, 1.0, shift_only=True
    )
    resultado["alpha_shift_only"] = round(alpha_shift, 4)
    resultado["qwk_full_shift_only"] = round(qwk_full_shift, 4)
    resultado["qwk_cv_shift_only"] = round(qwk_cv_con_shift, 4)
    resultado["sesgo_despues_shift"] = round(
        sum(pred_shift) / n - sum(y) / n, 4
    )

    # Gate shift-only: sesgo práctico ≥ 0.5 niveles + correlación significativa
    shift_aplicable = (abs(alpha_shift) >= 0.5 and p_value < P_UMBRAL)
    resultado["shift_only_aplicable"] = shift_aplicable

    gates = {
        "p_value_ok": p_value < P_UMBRAL,
        "beta_en_rango": BETA_MIN <= beta <= BETA_MAX,
        "mejora_qwk_cv": delta_qwk_cv >= DELTA_QWK_MIN,
    }
    resultado["gates"] = gates

    ols_ok = all(gates.values())

    # Selección de modo: OLS > shift-only > identidad
    if ols_ok:
        resultado["calibracion_aplicable"] = True
        resultado["calibracion_modo"] = "ols"
    elif shift_aplicable:
        resultado["calibracion_aplicable"] = True
        resultado["calibracion_modo"] = "shift_only"
        resultado["alpha"] = round(alpha_shift, 6)
        resultado["beta"] = 1.0
        logger.info(
            "[Calibrador] %s: shift-only APROBADO — α_shift=%.4f p=%.4f "
            "QWK_full_shift=%.4f sesgo_después=%.4f",
            region, alpha_shift, p_value, qwk_full_shift,
            resultado["sesgo_despues_shift"],
        )
    else:
        resultado["calibracion_aplicable"] = False
        resultado["calibracion_modo"] = "identidad"
        fallidos_ols = [k for k, v in gates.items() if not v]
        razones_shift = []
        if abs(alpha_shift) < 0.5:
            razones_shift.append(f"|α_shift|={abs(alpha_shift):.3f}<0.5")
        if p_value >= P_UMBRAL:
            razones_shift.append(f"p={p_value:.4f}>={P_UMBRAL}")
        resultado["razon_no_aplicar"] = (
            f"OLS rechazado ({fallidos_ols}); "
            f"shift-only rechazado ({', '.join(razones_shift)})"
        )

    if not ols_ok:
        fallidos = [k for k, v in gates.items() if not v]
        logger.warning(
            "[Calibrador] %s: OLS rechazado — %s | α=%.4f β=%.4f p=%.4f ΔQWK_cv=%+.4f",
            region, fallidos, alpha, beta, p_value, delta_qwk_cv,
        )
    else:
        resultado.pop("razon_no_aplicar", None)
        logger.info(
            "[Calibrador] %s: OLS APROBADO — α=%.4f β=%.4f p=%.4f R²=%.4f ΔQWK_cv=%+.4f",
            region, alpha, beta, p_value, r2, delta_qwk_cv,
        )

    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# Carga de datos desde BigQuery
# ═══════════════════════════════════════════════════════════════════════════════

def _cargar_pares_suiza(version_prefix: str = "v20") -> Tuple[List[str], List[float], List[int]]:
    """
    Pares (pred, GT) para H3 Suiza desde boletines_riesgo + slf_meteo_snowpack.
    GT = DEAPSnow RF2 dangerLevel (test set 2018-2020).

    Dos queries separadas (boletines_riesgo y slf_meteo_snowpack pueden estar
    en distintas ubicaciones BQ); el join se hace en Python.
    """
    from google.cloud import bigquery

    cliente = bigquery.Client(project=GCP_PROJECT)

    # Mapeo nombre_ubicacion → sector_id IMIS
    sector_ids = {
        "Interlaken":         4113,
        "Matterhorn Zermatt": 2223,
        "St Moritz":          6113,
    }
    sector_a_estacion = {v: k for k, v in sector_ids.items()}

    query_br = f"""
    SELECT
      nombre_ubicacion,
      CAST(DATE(fecha_emision) AS STRING) AS fecha_str,
      CAST(COALESCE(nivel_eaws_24h_raw, nivel_eaws_24h) AS FLOAT64) AS nivel_pred
    FROM `{GCP_PROJECT}.clima.boletines_riesgo`
    WHERE STARTS_WITH(version_prompts, '{version_prefix}')
      AND nombre_ubicacion IN ('Interlaken', 'Matterhorn Zermatt', 'St Moritz')
      AND nivel_eaws_24h IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY nombre_ubicacion, DATE(fecha_emision)
      ORDER BY fecha_emision DESC
    ) = 1
    ORDER BY fecha_str, nombre_ubicacion
    """

    sector_cond = " OR ".join(
        f"sector_id = {sid}" for sid in sector_ids.values()
    )
    query_gt = f"""
    SELECT
      sector_id,
      CAST(DATE(datum) AS STRING) AS fecha_str,
      CAST(ROUND(dangerLevel) AS INT64) AS nivel_gt
    FROM `{GCP_PROJECT}.validacion_avalanchas.slf_meteo_snowpack`
    WHERE ({sector_cond})
      AND dangerLevel IS NOT NULL AND dangerLevel BETWEEN 1 AND 5
    ORDER BY fecha_str, sector_id
    """

    try:
        br_rows = list(cliente.query(query_br).result())
        gt_rows = list(cliente.query(query_gt).result())

        # Construir dict GT: (estacion, fecha) → nivel_gt
        gt_dict: Dict[Tuple[str, str], int] = {}
        for row in gt_rows:
            estacion = sector_a_estacion.get(int(row["sector_id"]))
            if estacion:
                gt_dict[(estacion, str(row["fecha_str"]))] = int(row["nivel_gt"])

        # Emparejar
        fechas, pred, gt_out = [], [], []
        for row in br_rows:
            ub = str(row["nombre_ubicacion"])
            fstr = str(row["fecha_str"])
            nivel_gt = gt_dict.get((ub, fstr))
            if nivel_gt is not None:
                fechas.append(fstr)
                pred.append(float(row["nivel_pred"]))
                gt_out.append(nivel_gt)

        logger.info("[Calibrador] alpes_swiss: %d pares cargados", len(fechas))
        return fechas, pred, gt_out

    except Exception as e:
        logger.error("[Calibrador] alpes_swiss: error BQ — %s", e)
        return [], [], []


def _cargar_pares_andes(version_prefix: str = "v20") -> Tuple[List[str], List[float], List[int]]:
    """
    Pares (pred, GT) para H4 La Parva desde boletines_riesgo + snowlab_boletines.
    Emparejamiento por ventana temporal de ±7 días (igual que 08_validacion_snowlab.py).
    """
    from google.cloud import bigquery

    cliente = bigquery.Client(project=GCP_PROJECT)

    query_br = f"""
    SELECT
      nombre_ubicacion,
      CAST(DATE(fecha_emision) AS STRING) AS fecha_str,
      CAST(COALESCE(nivel_eaws_24h_raw, nivel_eaws_24h) AS FLOAT64) AS nivel_pred
    FROM `{GCP_PROJECT}.clima.boletines_riesgo`
    WHERE STARTS_WITH(version_prompts, '{version_prefix}')
      AND nombre_ubicacion IN (
        'La Parva Sector Alto', 'La Parva Sector Medio', 'La Parva Sector Bajo'
      )
      AND nivel_eaws_24h IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY nombre_ubicacion, DATE(fecha_emision)
      ORDER BY fecha_emision DESC
    ) = 1
    ORDER BY nombre_ubicacion, fecha_str
    """

    query_snow = f"""
    SELECT
      CAST(fecha_inicio_validez AS STRING) AS inicio,
      CAST(fecha_fin_validez   AS STRING) AS fin,
      CAST(nivel_alta  AS INT64) AS nivel_alta,
      CAST(nivel_media AS INT64) AS nivel_media,
      CAST(nivel_baja  AS INT64) AS nivel_baja
    FROM `{GCP_PROJECT}.validacion_avalanchas.snowlab_boletines`
    WHERE nivel_alta IS NOT NULL OR nivel_media IS NOT NULL OR nivel_baja IS NOT NULL
    ORDER BY inicio
    """

    mapa = {
        "La Parva Sector Alto":  "nivel_alta",
        "La Parva Sector Medio": "nivel_media",
        "La Parva Sector Bajo":  "nivel_baja",
    }

    try:
        import datetime

        br_rows = list(cliente.query(query_br).result())
        snow_rows = list(cliente.query(query_snow).result())

        fechas, pred, gt_out = [], [], []

        for br in br_rows:
            sector = str(br["nombre_ubicacion"])
            col_gt = mapa.get(sector)
            if col_gt is None:
                continue

            fecha_br = datetime.date.fromisoformat(str(br["fecha_str"]))
            mejor = None
            mejor_dist = float("inf")

            for sn in snow_rows:
                nivel_gt_val = sn[col_gt]
                if nivel_gt_val is None or not (1 <= nivel_gt_val <= 5):
                    continue
                inicio = datetime.date.fromisoformat(str(sn["inicio"]))
                fin = datetime.date.fromisoformat(str(sn["fin"]))
                ventana_inicio = inicio - datetime.timedelta(days=7)
                ventana_fin = fin + datetime.timedelta(days=7)
                if ventana_inicio <= fecha_br <= ventana_fin:
                    centro = inicio + datetime.timedelta(days=(fin - inicio).days // 2)
                    dist = abs((fecha_br - centro).days)
                    if dist < mejor_dist:
                        mejor_dist = dist
                        mejor = int(nivel_gt_val)

            if mejor is not None:
                fechas.append(str(br["fecha_str"]))
                pred.append(float(br["nivel_pred"]))
                gt_out.append(mejor)

        logger.info("[Calibrador] andes_chile: %d pares cargados", len(fechas))
        return fechas, pred, gt_out

    except Exception as e:
        logger.error("[Calibrador] andes_chile: error BQ — %s", e)
        return [], [], []


# ═══════════════════════════════════════════════════════════════════════════════
# Entrenamiento + serialización
# ═══════════════════════════════════════════════════════════════════════════════

def entrenar_y_guardar(
    version_prefix: str = "v20",
    output_path: str = COEF_PATH,
) -> Dict:
    """
    Entrena calibración para alpes_swiss y andes_chile; guarda JSON.

    Args:
        version_prefix: prefijo de version_prompts en BQ (default 'v20')
        output_path: ruta destino del JSON (default junto a este módulo)

    Returns:
        Dict con resultados por región
    """
    resultados: Dict[str, Dict] = {}

    loaders = {
        "alpes_swiss": _cargar_pares_suiza,
        "andes_chile": _cargar_pares_andes,
    }

    for region, loader in loaders.items():
        fechas, pred, gt = loader(version_prefix)
        if not fechas:
            resultados[region] = {
                "region": region,
                "calibracion_aplicable": False,
                "razon_no_aplicar": "sin_datos_bq",
            }
            continue
        resultados[region] = entrenar_calibracion(fechas, pred, gt, region)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(resultados, fh, indent=2, ensure_ascii=False)

    logger.info("[Calibrador] Coeficientes guardados en %s", output_path)
    return resultados


# ═══════════════════════════════════════════════════════════════════════════════
# Aplicación online
# ═══════════════════════════════════════════════════════════════════════════════

_coefs_cache: Optional[Dict] = None


def _cargar_coefs() -> Dict:
    global _coefs_cache
    if _coefs_cache is not None:
        return _coefs_cache

    if not os.path.exists(COEF_PATH):
        logger.debug("[Calibrador] coeficientes_calibracion.json no encontrado — identidad")
        _coefs_cache = {}
        return _coefs_cache

    try:
        with open(COEF_PATH, "r", encoding="utf-8") as fh:
            _coefs_cache = json.load(fh)
    except Exception as exc:
        logger.warning("[Calibrador] Error cargando coeficientes: %s — identidad", exc)
        _coefs_cache = {}

    return _coefs_cache


def aplicar_calibracion_regional(nivel: int, region: str) -> int:
    """
    Aplica calibración estadística al nivel predicho por el LLM.

    Si no hay coeficientes aprobados para la región, retorna el nivel original.

    Args:
        nivel: nivel EAWS predicho (int, 1–5)
        region: 'alpes_swiss' | 'andes_chile' | ...

    Returns:
        nivel calibrado (int, 1–5) o nivel original si sin calibración
    """
    coefs = _cargar_coefs()
    info = coefs.get(region)

    if info is None or not info.get("calibracion_aplicable", False):
        return nivel

    alpha = float(info.get("alpha", 0.0))
    beta = float(info.get("beta", 1.0))
    calibrado = _calibrar(float(nivel), alpha, beta)

    if calibrado != nivel:
        logger.debug(
            "[Calibrador] %s: nivel %d→%d (α=%.4f β=%.4f)",
            region, nivel, calibrado, alpha, beta,
        )

    return calibrado


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if "--entrenar" in sys.argv:
        version = "v20"
        for i, arg in enumerate(sys.argv):
            if arg == "--version" and i + 1 < len(sys.argv):
                version = sys.argv[i + 1]

        print(f"Entrenando calibración con pares version_prefix='{version}'...\n")
        resultados = entrenar_y_guardar(version_prefix=version)

        for region, res in resultados.items():
            aplicable = res.get("calibracion_aplicable", False)
            modo = res.get("calibracion_modo", "identidad")
            estado = f"APROBADA [{modo}] ✅" if aplicable else "RECHAZADA ❌"
            n_reg = res.get("n", res.get("n_pares", "?"))
            print(f"  {region} (n={n_reg}): {estado}")
            if "r_squared" in res:
                a_ols = res.get("alpha_ols", res.get("alpha", "?"))
                b_ols = res.get("beta_ols", res.get("beta", "?"))
                if modo == "shift_only":
                    a_ols = res.get("alpha", "?")  # sobrescrito a α_shift
                print(f"    OLS coef: α={a_ols}  β={b_ols}  R²={res.get('r_squared','?'):.4f}")
                print(f"    p(β)={res.get('p_value_beta','?'):.4f}  β_CI95={res.get('beta_ci95','?')}")
                print(f"    QWK sin→con (full):  {res.get('qwk_full_sin','?'):.4f} → {res.get('qwk_full_con','?'):.4f}")
                print(f"    QWK sin→con (CV):    {res.get('qwk_cv_sin','?'):.4f} → {res.get('qwk_cv_con','?'):.4f}  "
                      f"(ΔQWK_cv={res.get('delta_qwk_cv','?'):+.4f})")
                print(f"    Sesgo antes→después: {res.get('sesgo_antes','?'):+.4f} → {res.get('sesgo_despues','?'):+.4f}")
                print(f"    Gates OLS: {res.get('gates', {})}")
                if res.get("alpha_shift_only") is not None:
                    sh_ok = res.get("shift_only_aplicable", False)
                    print(f"    Shift-only: α_shift={res['alpha_shift_only']:+.4f}  "
                          f"QWK_full={res.get('qwk_full_shift_only','?'):.4f}  "
                          f"QWK_cv={res.get('qwk_cv_shift_only','?'):.4f}  "
                          f"sesgo_después={res.get('sesgo_despues_shift','?'):+.4f}  "
                          f"{'OK ✅' if sh_ok else 'rechazado ❌'}")
            if not aplicable:
                print(f"    Razón: {res.get('razon_no_aplicar', 'desconocida')}")
            print()

        print(f"Coeficientes guardados en: {COEF_PATH}")

    elif "--verificar" in sys.argv:
        coefs = _cargar_coefs()
        if not coefs:
            print("No hay coeficientes cargados (identidad activa)")
        else:
            for region, info in coefs.items():
                ap = info.get("calibracion_aplicable", False)
                print(f"  {region}: {'ACTIVA' if ap else 'INACTIVA'} "
                      f"α={info.get('alpha', 0):.4f} β={info.get('beta', 1):.4f}")

    else:
        print("Uso:")
        print("  python -m agentes.validacion.calibrador --entrenar [--version v20]")
        print("  python -m agentes.validacion.calibrador --verificar")
