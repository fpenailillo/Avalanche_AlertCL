"""
Registro de Versiones de Prompts — Sistema Multi-Agente Avalanchas

Permite rastrear qué versión exacta de cada prompt se usó para generar
un boletín. Fundamental para reproducibilidad académica (tesina).

Cada prompt se identifica por:
- componente: nombre del subagente o módulo
- version: semver (e.g. "3.1.0")
- hash_sha256: hash del contenido para verificar integridad

Uso:
    from agentes.prompts.registro_versiones import (
        obtener_version_actual,
        verificar_integridad,
        REGISTRO_PROMPTS
    )

    version = obtener_version_actual()  # "v3.1"
    ok = verificar_integridad()         # True si todos los hashes coinciden
"""

import hashlib
import importlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Registro central de prompts ────────────────────────────────────────────
# Actualizar este registro cada vez que se modifique un prompt.
# El hash se genera con _calcular_hash() sobre el contenido del prompt.
#
# Para regenerar hashes después de editar un prompt:
#   python -m agentes.prompts.registro_versiones --actualizar-hashes

REGISTRO_PROMPTS = {
    "orquestador": {
        "modulo": "agentes.orquestador.prompts",
        "variable": "SYSTEM_PROMPT",
        "version": "3.1.0",
        "descripcion": "FIX-S3: FUSION_ACTIVA → FUSION_ACTIVA_CON_CARGA en mapping estabilidad",
        "hash_sha256": "1e7e2fd35c00e9b5",
    },
    "topografico": {
        "modulo": "agentes.subagentes.subagente_topografico.prompts",
        "variable": "SYSTEM_PROMPT_TOPOGRAFICO",
        "version": "8.1.0",
        "descripcion": "v8.1: FIX-PINN-WN2-P95 — usar p95 si p50==0 (ensemble disperso en tormentas)",
        "hash_sha256": "349d8ac7c25bb680",
    },
    "satelital": {
        "modulo": "agentes.subagentes.subagente_satelital.prompts",
        "variable": "SYSTEM_PROMPT_SATELITAL",
        "version": "4.1.0",
        "descripcion": "v4.1: paso 6 obligatorio analizar_via_earth_ai + sección EARTH AI en salida (FIX-EARTH-AI-PROMPT)",
        "hash_sha256": "3bf6c40e5ad4f451",
    },
    "meteorologico": {
        "modulo": "agentes.subagentes.subagente_meteorologico.prompts",
        "variable": "SYSTEM_PROMPT_METEOROLOGICO",
        "version": "5.3.0",
        "descripcion": "v5.3: FIX-WN2-TRIGGERS (H) — S3 pasa wn2_heavy_snow/storm_slab/wind_strong a detectar_ventanas_criticas",
        "hash_sha256": "971c1fcb276cdcb7",
    },
    "nlp": {
        "modulo": "agentes.subagentes.subagente_nlp.prompts",
        "variable": "SYSTEM_PROMPT_NLP",
        "version": "3.1.0",
        "descripcion": "Análisis relatos Andeshandbook, índice riesgo histórico + guía conversión frecuencias",
        "hash_sha256": "ba1f7309d30ba8bd",
    },
    "integrador": {
        "modulo": "agentes.subagentes.subagente_integrador.prompts",
        "variable": "SYSTEM_PROMPT_INTEGRADOR",
        "version": "10.2.0",
        "descripcion": "v10.2: FIX-CR18-CH-1 — eliminar ref a obtener_condiciones_actuales_meteo (no tool de S5); añadir instrucción viento_kmh",
        "hash_sha256": "98dacfa68aa412cc",
    },
}

# Versión global del conjunto de prompts (se incrementa cuando cambia cualquiera)
# v25.0: FIX-STORM-EXTREME + FIX-SAT-STORM + FIX-WN2-PINN + fixes ultrareview 001/002/004/009/015/017:
#   FIX-STORM-FREQ-WN2: very_poor + NEVADA_RECIENTE + ventanas≥1 en Andes Chile → frecuencia=many (Schweizer 2003).
#   FIX-WN2-SIZE-ANDES: nieve_nueva_cm_wn2 parametriza tamano avalancha (Techel 2022: 25→D3, 40→D4, 60→D5).
#   FIX-SAT-STORM: NDSI delta>20% → NEVADA_SATELITAL_CONFIRMADA propaga a ventanas_criticas (rompe gate calma).
#   FIX-WN2-PINN: surcharge Mohr-Coulomb cuando nieve_nueva_cm_wn2≥20 → estabilidad very_poor en tormenta extrema.
#   bug_001: claves IMIS alineadas (HS_meas_cm, TA_c; eliminar VW_max_ms silencioso).
#   bug_002: propagar tools_llamadas de cache en modo solo_s5 (~15 columnas BQ que quedaban NULL).
#   bug_009: umbral redistribución nieve Alpes 3→8 m/s (Schmidt 1980; diferenciado del umbral detección ERA5).
#   bug_015: COALESCE(nivel_eaws_24h_raw, nivel_eaws_24h) en calibrador evita doble calibración desde v21.
#   bug_017: timezone-aware fecha_local en WN2 (Europe/Zurich vs America/Santiago según longitud).
# v22.0: FIX-WIND-UNITS (bug_021) + FIX-CR10B-RECAL:
#   FIX-WIND-UNITS: normalizar velocidad_viento km/h→m/s en ConsultorBigQuery.obtener_condiciones_actuales.
#     Causa raíz: todas las rutas de ingesta guardan km/h, pero consumers asumían m/s.
#     Fix: /3.6 al leer BQ; los ×3.6 downstream (fuente_open_meteo, tool_clima_reciente,
#     almacenador) ya producen km/h correctos.
#   FIX-CR10B-RECAL: recalibrar umbral viento Alpes tras corrección de unidades.
#     Análisis 30 pares DEAPSnow 2018-2020: ratio IMIS/ERA5 ≈ 1.0 (estaciones valle,
#     no cresta); max ERA5 = 5.22 m/s → umbral 7 m/s apagaba toda señal.
#     Nuevo umbral: 3.0 m/s (activa 4/30 días, 100% GT≥3, sin falsos positivos).
#     No afecta Andes Chile (_umbral_viento_fuerte = 10.0 m/s sin cambio).
# v21.0: FIX-CALIB-REG (D): calibración estadística post-LLM por región.
# v18.0: FIX-CR18-CH-1/2/3 — fixes H3 Suiza:
#   CH-1 (prompt): S5 no intenta llamar obtener_condiciones_actuales_meteo (no registrada en S5);
#         añadir instrucción de pasar siempre viento_kmh.
#   CH-2 (tool): umbral ventanas_criticas >=2 para boost frecuencia en Alpes+NEVADA_RECIENTE (vs >=3 global).
#   CH-3 (tool): tamano mínimo 3 en Alpes con NEVADA_RECIENTE + >=2 ventanas (tormenta masiva D3+).
#   No afecta Andes Chile (guards region=alpes_swiss).
# v17.0: FIX-CR17A — cap estabilidad base en 'fair' (Andes + factor neutro + sin ventanas).
#   El PINN siempre da 'poor' en La Parva (terreno potencial). Sin trigger meteo
#   la estabilidad activa es 'fair' → matriz EAWS ≤ nivel 2. No afecta Alpes.
# v15.5: REVERT FIX-CR16A — restaurar fallback precip_efectiva global (CR-10A).
#   FIX-CR16A (v16.0) empeoró sesgo +0.770→+1.023 y QWK +0.022→-0.065.
# v15.0: Integración WeatherNext 2 — nueva tool obtener_pronostico_wn2_ventanas.
#   Fuente: BigQuery Analytics Hub climas-chileno.weathernext_2.weathernext_2_0_0.
#   Enriquecimiento: ventanas 6h, ensemble 64 miembros, probable_avalanche_problem,
#   4 alertas booleanas (heavy_snow/storm_slab/wet_snow/wind_strong).
#   Persistencia: 6 nuevos campos wn2_* en boletines_riesgo.
# v14.3: Experimento limpio — mismo código que v14.0 (sin CR-14B).
#   Fix timeout: ThreadPoolExecutor → multiprocessing.Process con .terminate() real.
#   120 runs desde cero para verificar reproducibilidad H3 QWK≈0.24 + H4 QWK≈0.028.
# v14.2: Re-run parcial (noche, lento, mezclado con v14.1 CR-14B). Descartado.
# v14.0: Redesign validación suiza → DEAPSnow test set 2018-2020.
#   Backfill IMIS (TA, VW, HN24, RH) en condiciones_actuales para 30 fechas per-estación.
# v19.0: FIX-CR19 — nieve_nueva_cm = HN24_cm (IMIS) en condiciones_actuales:
#   consultor_bigquery: SELECT datos_json_crudo; parsear nieve_nueva_cm desde HN24_cm.
#   tool_condiciones_actuales: surfacear nieve_nueva_cm al LLM; alerta CARGA_NIEVE_EXTREMA_30CM.
#   tool_ventanas_criticas: param nieve_nueva_cm_imis; ventana CARGA_NIEVE_PROFUNDA
#   cuando HN24>=25cm en Alpes (2a ventana -> activa CH-2/CH-3). Guard _es_alpes.
# v21.0: FIX-CALIB-REG (D): calibración estadística post-LLM por región.
#   alpes_swiss: shift-only aprobado (α=+0.70, β=1.0, p=0.026, QWK_cv 0.191→0.250).
#     Mapa: nivel 1→2, 2→3, 3→4, 4→5. QWK full 0.264→0.353 (objetivo ≥0.35 cumplido).
#   andes_chile: identidad — shift-only rechazado (|α|=0.40<0.50). Ya cumple objetivo ≥0.15.
#   Infraestructura: calibrador.py, coeficientes_calibracion.json, tool_clasificar_eaws (+raw),
#     almacenador (+nivel_eaws_24h_raw), schema_boletines.json.
# v20.0: FIX-VAL-FRAMEWORK (G): cache S1-S4 + --solo-s5 (3.5h → ~4 min por validación).
#   FIX-LLM-DETER (C): temperature=0.0 en todos los LLM clients (seed eliminado — Databricks rechaza).
#   FIX-HN24-PROMO (A): HN24 → precip_efectiva en Alpes cuando supera ERA5.
#   FIX-IMIS-EXT (F): extracción extendida HS/TA/VW/VW_max desde JSON IMIS.
#   FIX-HN24-SIZE (B): graduación tamaño D3/D4/D5 por HN24 en Alpes (reemplaza CH-3 binario).
#   FIX-CR7A-REFACTOR (E): compuerta condicional Andes — reemplaza bloqueo absoluto CR-7A
#     por gate basado en señales de calma (factor neutro+vc=0+p72h<5mm+viento<30+dias_bajo>=2).
#   FIX-WN2-TRIGGERS (H): alertas WN2 ensemble → ventanas deterministas (NEVADA_WN2_CONFIRMADA,
#     PLACA_VIENTO_WN2, VIENTO_WN2_FUERTE). Guard disponible=False en retroactivo.
#
# v25.1 (FIX-CR17A-ATENUACION):
#   FIX-CR17A-ATENUACION: reemplaza cap duro v17.0 en Andes Chile por atenuación graduada.
#     very_poor→poor (1 paso); poor→fair solo con ESTABLE + dias_bajo≥3 (calma absoluta).
#     poor + CICLO_DIURNO_NORMAL → mantener poor → habilita poor×some×3 → nivel 3.
#   FIX-CICLO-CALMA: separa CICLO_DIURNO_NORMAL de ESTABLE en calma sostenida (dias_bajo≥4).
#     Activa calma sostenida solo con ESTABLE/""; ciclo térmico activo no es calma real.
#   Resultado validación H4 v25.1 (n=87): QWK=+0.008 (+0.088 vs v25.0). Techo ≤2 persiste.
#   Causa raíz: PINN retornaba FS constante por sector (sin WN2). FIX-CR17A sin efecto.
#
# v25.2 (FIX-PINN-WN2):
#   FIX-PINN-WN2: cerrar el path WN2 → S1 → PINN → CR17A → EAWS nivel ≥3.
#     Causa raíz identificada con datos BQ (17 boletines v25.1 La Parva GT≥3):
#     TOOL_PRONOSTICO_WN2_VENTANAS solo estaba registrada en S3, no en S1.
#     Qwen3 no podía invocarla desde S1 aunque el prompt lo indicara.
#     WN2 ensemble tiene señal retroactiva para todas las fechas GT≥3
#     (prec_6h_max 10-41 mm, confirmado query BQ weathernext_2_0_0).
#   Cambios:
#     1. subagente_topografico/agente.py: registra TOOL_PRONOSTICO_WN2_VENTANAS en S1.
#     2. tool_calcular_pinn.py: fallback determinista — si nieve_nueva_cm no viene del LLM
#        y USE_WEATHERNEXT2=true y nombre_ubicacion provisto, consulta WN2 directamente.
#        Acepta nombre_ubicacion + fecha_objetivo como params opcionales del schema.
#     3. subagente_topografico/prompts.py: cambia "opcionalmente" → "OBLIGATORIO".
#
# v25.3 (FIX-PINN-WN2-P95):
#   Causa raíz adicional (data-driven, observada en reproceso v25.2):
#     nieve_24h_cm_p50_corr = 0.0 para todas las fechas GT≥3 — el percentil p50 del
#     ensemble de 64 miembros WN2 es 0 porque <50% de miembros predicen precipitación
#     para eventos de tormenta con alta incertidumbre. La señal existe en p95 (10-41 mm).
#   Cambios:
#     1. tool_calcular_pinn.py: fallback usa p95 cuando p50==0 y p95>0 (ensemble disperso).
#        Metodológicamente: p95 = escenario de planificación (tail-risk EAWS).
#        fuente_nieve_nueva distingue "wn2_fallback_determinista_p50" vs "_p95".
#     2. subagente_topografico/prompts.py v8.1: instrucción LLM de usar p95 si p50==0.
#     3. reprocesar_retroactivo.py: añade flag --force para reescribir boletines existentes.
#
# v25.4 (FIX-WN2-3D):
#   Causa raíz confirmada con análisis data-driven (perfil datos + Caro 2026 Río Maipo):
#     GT=5 (2024-06-15): la tormenta ocurrió jun 12-14 (HN3d=87cm en Farellones DGA 2452m).
#     El día del boletín (jun 15) no hubo nueva precipitación → p50=0, p95≈0 en WN2.
#     El peligro persiste por placas de tormenta ya formadas (Schweizer et al. 2003).
#     WN2 ventana 24h = correcto para el día, pero no captura la carga acumulada del storm.
#   Solución: ampliar la ventana de consulta WN2 a 3 días previos al boletín (t-2, t-1, t).
#   El CTE diario_3d (mejor init por ventana via rn=1) suma p95 corr de los 3 días.
#   El init_date_start se extiende 5 días atrás para que esos runs estén disponibles.
#   Prioridad fallback en tool_calcular_pinn.py: p50_24h → p95_24h → p95_3d.
#   Validación oracle (Caro DGA offline): AUC=1.000 para HN3d vs GT≥3 en 14 fechas 2024.
#   Cambios:
#     1. fuente_weathernext2.py: CTE diario_3d + param @fecha_obj + init 5d atrás.
#     2. tool_calcular_pinn.py: prioridad p50→p95→p95_3d; fuente_nieve distingue "p95_3d".
#
# v25.5 (FIX-WN2-THRESHOLD):
#   Causa raíz: WN2 ensemble siempre devuelve nieve_24h_cm_p50_corr > 0 por ruido numérico
#     (~0.1-0.5 cm), incluso en días completamente despejados. Para 2024-06-15 (GT=5):
#     p50=0.13 cm (ruido) → condición `val_p50 > 0` TRUE → surcharge=2 N/m² → FS=1.81 (sin cambio).
#     La ventana 3d (173.6 cm) nunca se evaluaba porque p50>0 siempre.
#   Solución: umbral mínimo 5 cm (Schweizer 2003: HN24h < 5 cm no genera placas de tormenta).
#     Condición cambia de `> 0` a `>= 5` para p50 y p95.
#   Diagnóstico confirmado con query BQ: Jun 13 p95=30-35 cm/slot × 4 slots = señal fuerte.
#     Con threshold: p50=0.13 < 5 → skip; p95=2.42 < 5 → skip; 3d=173.6 >= 5 → usa 3d.
#     Resultado esperado: FS=1.566, SURCHARGE_NIEVE_EXTREMA_174cm → riesgo_falla="alto" → INESTABLE.
#   Cambios:
#     1. tool_calcular_pinn.py: _MIN_NIEVE_CM=5.0 para filtrar ruido p50/p95/3d.
#     2. test_fix_pinn_wn2.py: nuevo test_fallback_wn2_p50_ruido_usa_p95_3d (caso real 2024-06-15).
#
# v25.6 (FIX-WN2-LLM-OVERRIDE):
#   Causa raíz adicional (observada en tracer 2024-06-15 con USE_WEATHERNEXT2=true):
#     El LLM llama obtener_pronostico_wn2_ventanas (83 ventanas), extrae nieve_24h_cm_p95_corr
#     y lo pasa como nieve_nueva_cm=4.3 cm al PINN. Como 4.3 != None, la condición
#     `nieve_nueva_cm is None` era False → fallback 3d nunca se activaba.
#     Resultado: surcharge=42 N/m², FS=1.81, estado=ESTABLE (igual que sin WN2).
#   Solución: ampliar condición a `nieve_nueva_cm is None or nieve_nueva_cm < _MIN_NIEVE_CM`.
#     Si el LLM extrae un valor de 24h pequeño (< 5 cm), el fallback lo sobreescribe
#     con el valor 3d cuando éste tiene señal (>= 5 cm). Si no hay señal >= 5 cm en
#     ninguna ventana, se mantiene el valor que pasó el LLM (even if small).
#   Cambios:
#     1. tool_calcular_pinn.py: condición fallback ampliada a `or nieve_nueva_cm < 5`.
#     2. test_fix_pinn_wn2.py: nuevo test_fallback_wn2_llm_valor_pequeno_usa_p95_3d.
VERSION_GLOBAL = "25.6"


def _calcular_hash(contenido: str) -> str:
    """Calcula SHA-256 del contenido de un prompt (sin espacios trailing)."""
    normalizado = contenido.strip()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()[:16]


def _cargar_prompt(componente: str) -> Optional[str]:
    """Carga dinámicamente el contenido de un prompt desde su módulo."""
    info = REGISTRO_PROMPTS.get(componente)
    if not info:
        return None

    try:
        modulo = importlib.import_module(info["modulo"])
        return getattr(modulo, info["variable"], None)
    except (ImportError, AttributeError) as e:
        logger.warning(f"No se pudo cargar prompt '{componente}': {e}")
        return None


def obtener_version_actual() -> str:
    """
    Retorna la versión global del conjunto de prompts.

    Se usa para guardar en el campo `version_prompts` de BigQuery,
    permitiendo rastrear qué prompts generaron cada boletín.
    """
    return f"v{VERSION_GLOBAL}"


def obtener_versiones_detalladas() -> dict:
    """
    Retorna un diccionario con la versión y hash de cada componente.

    Útil para auditoría y debugging.
    """
    resultado = {
        "version_global": obtener_version_actual(),
        "componentes": {}
    }

    for componente, info in REGISTRO_PROMPTS.items():
        contenido = _cargar_prompt(componente)
        hash_actual = _calcular_hash(contenido) if contenido else "NO_DISPONIBLE"

        resultado["componentes"][componente] = {
            "version": info["version"],
            "hash_actual": hash_actual,
            "hash_registrado": info["hash_sha256"],
            "integridad_ok": (
                info["hash_sha256"] is None or  # Sin hash registrado = OK
                hash_actual == info["hash_sha256"]
            ),
            "descripcion": info["descripcion"],
        }

    return resultado


def verificar_integridad() -> bool:
    """
    Verifica que los prompts actuales coincidan con los hashes registrados.

    Retorna True si todos los prompts con hash registrado coinciden.
    Prompts sin hash registrado (hash_sha256=None) se omiten.
    """
    todos_ok = True

    for componente, info in REGISTRO_PROMPTS.items():
        if info["hash_sha256"] is None:
            continue

        contenido = _cargar_prompt(componente)
        if contenido is None:
            logger.error(f"Prompt '{componente}' no se pudo cargar")
            todos_ok = False
            continue

        hash_actual = _calcular_hash(contenido)
        if hash_actual != info["hash_sha256"]:
            logger.warning(
                f"Hash de '{componente}' no coincide: "
                f"esperado={info['hash_sha256']}, actual={hash_actual}. "
                f"El prompt fue modificado sin actualizar el registro."
            )
            todos_ok = False

    return todos_ok


def registrar_hashes_actuales() -> dict:
    """
    Calcula y registra los hashes SHA-256 de todos los prompts actuales.

    Actualiza REGISTRO_PROMPTS in-memory. Para persistir los cambios,
    ejecutar como script: python -m agentes.prompts.registro_versiones --actualizar-hashes
    """
    hashes = {}
    for componente in REGISTRO_PROMPTS:
        contenido = _cargar_prompt(componente)
        if contenido:
            h = _calcular_hash(contenido)
            REGISTRO_PROMPTS[componente]["hash_sha256"] = h
            hashes[componente] = h
        else:
            hashes[componente] = None
            logger.warning(f"No se pudo cargar prompt '{componente}' para hash")

    return hashes


# ─── CLI para gestión de hashes ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--actualizar-hashes" in sys.argv:
        print("Calculando hashes de prompts actuales...\n")
        hashes = registrar_hashes_actuales()
        print("Actualizar REGISTRO_PROMPTS con estos hashes:\n")
        for comp, h in hashes.items():
            version = REGISTRO_PROMPTS[comp]["version"]
            print(f'    "{comp}": {{"hash_sha256": "{h}", "version": "{version}"}},')
        print(f"\nVERSION_GLOBAL = \"{VERSION_GLOBAL}\"")

    elif "--verificar" in sys.argv:
        print("Verificando integridad de prompts...\n")
        detalles = obtener_versiones_detalladas()
        print(f"Versión global: {detalles['version_global']}\n")
        for comp, info in detalles["componentes"].items():
            estado = "✅" if info["integridad_ok"] else "❌"
            print(f"  {estado} {comp} v{info['version']} hash={info['hash_actual']}")
        ok = verificar_integridad()
        print(f"\nIntegridad global: {'✅ OK' if ok else '❌ FALLÓ'}")

    else:
        detalles = obtener_versiones_detalladas()
        print(f"Versión global: {detalles['version_global']}\n")
        for comp, info in detalles["componentes"].items():
            print(f"  {comp}: v{info['version']} — {info['descripcion']}")
        print(f"\nUso:")
        print(f"  python -m agentes.prompts.registro_versiones --actualizar-hashes")
        print(f"  python -m agentes.prompts.registro_versiones --verificar")
