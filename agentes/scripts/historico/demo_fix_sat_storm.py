"""
Demo FIX-SAT-STORM — Comparativo antes/después.

Simula la tormenta del 15 de junio de 2024 en La Parva (HN3d +62 cm,
Snowlab CAA nivel 5) que AndesAI v22.0 predijo como nivel 2 (ERA5=0mm).

Ejecutar:
    python agentes/scripts/demo_fix_sat_storm.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentes.subagentes.subagente_meteorologico.tools.tool_ventanas_criticas import (
    ejecutar_detectar_ventanas_criticas,
)
from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

# ─── Condiciones de la tormenta 2024-06-15 en La Parva ───────────────────────
# ERA5 reportó precipitación ~0 mm (subestimación convectiva conocida).
# Satélite habría visto: NDSI delta +20-30% por acumulación de 62 cm en 3 días.
# Temperatura en superficie: -3°C (evento invernal típico).
CONDICIONES_TORMENTA = {
    "temperatura_actual_C": -3.2,
    "velocidad_viento_actual_ms": 6.5,
    "precipitacion_actual_mm": 0.4,   # ERA5 subestimado
    "precipitacion_72h_mm": 1.8,      # ERA5 acumulado subestimado
    "nombre_ubicacion": "La Parva Sector Alto",
    "ciclo_fusion_congelacion": False,
    "dias_alto_riesgo": 0,
}

# Condiciones de calma para contrastar
CONDICIONES_CALMA = {
    "temperatura_actual_C": -1.5,
    "velocidad_viento_actual_ms": 2.0,
    "precipitacion_actual_mm": 0.0,
    "precipitacion_72h_mm": 0.0,
    "nombre_ubicacion": "La Parva Sector Alto",
    "ciclo_fusion_congelacion": False,
    "dias_alto_riesgo": 0,
}

# Señales satelitales simuladas para la tormenta
# (NDSI delta +62cm SD en 3 días → delta_pct_nieve_24h ≈ +25%)
ALERTAS_SATELITALES_TORMENTA = ["NEVADA_RECIENTE_INTENSA"]
ALERTAS_SATELITALES_CALMA: list = []


def _sep(titulo: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print("=" * 60)


def analizar_escenario(nombre: str, condiciones: dict, alertas_sat: list) -> dict:
    """Ejecuta ventanas + clasificación EAWS y devuelve resultado."""
    ventanas = ejecutar_detectar_ventanas_criticas(
        **condiciones, alertas_satelitales=alertas_sat
    )

    eaws = ejecutar_clasificar_riesgo_eaws_integrado(
        estabilidad_topografica="poor",
        factor_meteorologico=ventanas["factor_meteorologico_eaws"],
        ventanas_criticas_detectadas=ventanas["num_ventanas_criticas"],
        condiciones_meteo_disponibles=True,
        dias_consecutivos_nivel_bajo=3,
        precipitacion_72h_corregida_mm=condiciones.get("precipitacion_72h_mm", 0),
        viento_kmh=(condiciones.get("velocidad_viento_actual_ms", 0)) * 3.6,
        nombre_ubicacion=condiciones.get("nombre_ubicacion"),
        estabilidad_satelital="poor",
    )
    return {"ventanas": ventanas, "eaws": eaws}


def main():
    _sep("ESCENARIO 1 — TORMENTA SIN FIX (ERA5 solo, v22.0)")
    print("Condiciones ERA5: precip=0.4mm, viento=6.5m/s, T=-3.2°C")
    print("Señales satelitales: NINGUNA (v22.0 no pasaba alertas_satelitales)")

    sin_fix = analizar_escenario(
        "TORMENTA sin FIX",
        CONDICIONES_TORMENTA,
        alertas_sat=[],   # sin señal satelital = comportamiento v22.0
    )
    vt = sin_fix["ventanas"]
    print(f"\nVentanas críticas: {vt['num_ventanas_criticas']}")
    for v in vt["ventanas_criticas"]:
        print(f"  [{v['severidad'].upper()}] {v['tipo']}: {v['descripcion'][:60]}...")
    print(f"Factor meteorológico: {vt['factor_meteorologico_eaws']}")
    print(f"\n>>> NIVEL EAWS PREDICHO: {sin_fix['eaws'].get('nivel_eaws_24h')} — {sin_fix['eaws'].get('nombre_nivel_24h')} <<<")
    print(f"    (Snowlab real: 5 — Muy Alto)")

    _sep("ESCENARIO 2 — TORMENTA CON FIX-SAT-STORM (v23.0)")
    print("Condiciones ERA5: precip=0.4mm, viento=6.5m/s, T=-3.2°C  (igual)")
    print("Señales satelitales: NEVADA_RECIENTE_INTENSA (delta_pct>20%)")

    con_fix = analizar_escenario(
        "TORMENTA con FIX",
        CONDICIONES_TORMENTA,
        alertas_sat=ALERTAS_SATELITALES_TORMENTA,
    )
    vt2 = con_fix["ventanas"]
    print(f"\nVentanas críticas: {vt2['num_ventanas_criticas']}")
    for v in vt2["ventanas_criticas"]:
        print(f"  [{v['severidad'].upper()}] {v['tipo']}: {v['descripcion'][:60]}...")
    print(f"Factor meteorológico: {vt2['factor_meteorologico_eaws']}")
    print(f"\n>>> NIVEL EAWS PREDICHO: {con_fix['eaws'].get('nivel_eaws_24h')} — {con_fix['eaws'].get('nombre_nivel_24h')} <<<")
    print(f"    (Snowlab real: 5 — Muy Alto)")

    _sep("ESCENARIO 3 — CALMA CON FIX (verificación sin regresión)")
    print("Condiciones: sin precipitación, sin nieve satelital")
    print("Señales satelitales: NINGUNA")

    calma = analizar_escenario(
        "CALMA con FIX",
        CONDICIONES_CALMA,
        alertas_sat=ALERTAS_SATELITALES_CALMA,
    )
    vt3 = calma["ventanas"]
    print(f"\nVentanas críticas: {vt3['num_ventanas_criticas']}")
    print(f"Factor meteorológico: {vt3['factor_meteorologico_eaws']}")
    print(f"\n>>> NIVEL EAWS PREDICHO: {calma['eaws'].get('nivel_eaws_24h')} — {calma['eaws'].get('nombre_nivel_24h')} <<<")
    print(f"    (Snowlab real: 1 — Baja)")

    _sep("ESCENARIO 4 — TECHO TEÓRICO (S1+S2 very_poor, frecuencia=many)")
    print("Hipotético: S1 PINN → very_poor, S2 ViT → very_poor, frec=many, tam=4")
    print("(Requiere datos satelitales de alta frecuencia + PINN calibrado con carga nival)")

    techo = ejecutar_clasificar_riesgo_eaws_integrado(
        estabilidad_topografica="very_poor",
        factor_meteorologico="NEVADA_RECIENTE",
        ventanas_criticas_detectadas=2,
        condiciones_meteo_disponibles=True,
        dias_consecutivos_nivel_bajo=0,
        precipitacion_72h_corregida_mm=15.0,
        viento_kmh=35.0,
        nombre_ubicacion="La Parva Sector Alto",
        estabilidad_satelital="very_poor",
        frecuencia_topografica="many",
        tamano_eaws=4,
    )
    print(f"\n>>> NIVEL EAWS PREDICHO: {techo.get('nivel_eaws_24h')} — {techo.get('nombre_nivel_24h')} <<<")
    print(f"    (Snowlab real: 5 — Muy Alto)")

    _sep("RESUMEN COMPARATIVO")
    print(f"{'Escenario':<44} {'Factor':<25} {'Ventanas':>8} {'EAWS':>5}  {'Nombre'}")
    print("-" * 96)
    filas = [
        ("Tormenta v22.0 (sin fix, ERA5 solo)",
         sin_fix['ventanas']['factor_meteorologico_eaws'],
         sin_fix['ventanas']['num_ventanas_criticas'],
         sin_fix['eaws'].get('nivel_eaws_24h'),
         sin_fix['eaws'].get('nombre_nivel_24h')),
        ("Tormenta v23.0 (FIX-SAT-STORM)",
         con_fix['ventanas']['factor_meteorologico_eaws'],
         con_fix['ventanas']['num_ventanas_criticas'],
         con_fix['eaws'].get('nivel_eaws_24h'),
         con_fix['eaws'].get('nombre_nivel_24h')),
        ("Calma v23.0 (verificar sin regresión)",
         calma['ventanas']['factor_meteorologico_eaws'],
         calma['ventanas']['num_ventanas_criticas'],
         calma['eaws'].get('nivel_eaws_24h'),
         calma['eaws'].get('nombre_nivel_24h')),
        ("Techo teórico (very_poor + many + tam=4)",
         "NEVADA_RECIENTE",
         2,
         techo.get('nivel_eaws_24h'),
         techo.get('nombre_nivel_24h')),
    ]
    for nombre, factor, ventanas, nivel, nombre_nivel in filas:
        print(f"{nombre:<44} {factor:<25} {ventanas:>8} {str(nivel):>5}  {nombre_nivel}")

    print()
    print("Ground truth Snowlab 2024-06-15: NIVEL 5 — Muy Alto")
    print()
    print("Análisis de la brecha residual:")
    print("  v23.0 mejora: 1→2 (brecha: -3 niveles → -2 niveles respecto de Snowlab 4-5)")
    print("  Limitante: S1 PINN sin forzante de carga nival real → estabilidad_topo=poor (no very_poor)")
    print("             S2 ViT sin datos temporales de alta frecuencia → estado=poor")
    print("  Para cerrar la brecha restante: mejorar S1 con WN2 nieve_24h_cm_p50 como forzante")
    print("  o afinar el ViT para detectar cambios rápidos de carga → very_poor durante tormenta")


if __name__ == "__main__":
    main()
