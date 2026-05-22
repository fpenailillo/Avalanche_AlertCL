"""
Demo v24.0 — Medición del ajuste FIX-SAT-STORM + FIX-WN2-PINN.

Prueba los tres eventos de tormenta documentados en la validación Caro 2026
(Snowlab CAA, jun-ago 2024, La Parva) más tres días de calma para verificar
que no hay regresión.

Ejecutar:
    python agentes/scripts/demo_v24_ajuste_tormenta.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentes.subagentes.subagente_topografico.tools.tool_calcular_pinn import (
    ejecutar_calcular_pinn,
)
from agentes.subagentes.subagente_topografico.tools.tool_estabilidad_manto import (
    ejecutar_evaluar_estabilidad_manto,
)
from agentes.subagentes.subagente_meteorologico.tools.tool_ventanas_criticas import (
    ejecutar_detectar_ventanas_criticas,
)
from agentes.subagentes.subagente_integrador.tools.tool_clasificar_eaws import (
    ejecutar_clasificar_riesgo_eaws_integrado,
)

# ─── Parámetros topográficos fijos (La Parva Sector Alto, GLO-30) ─────────────
# Pendiente dominante zona inicio: 38° (pendientes 30-45° en La Parva 3000-3500m)
# Densidad manto existente: 280 kg/m³ (inicio invierno, nieve transformada ~2 sem)
# Índice metamorfismo: 1.1 (cristales en transformación, condiciones invernales)
TOPO_LA_PARVA = dict(
    gradiente_termico_C_100m=-0.65,
    densidad_kg_m3=280.0,
    indice_metamorfismo=1.1,
    energia_fusion_J_kg=120000.0,
    pendiente_grados=38.0,
    curvatura_vertical=-0.15,   # convexa — zona inicio favorable
)

# ─── Eventos a evaluar ────────────────────────────────────────────────────────
EVENTOS = [
    # Tormentas documentadas (Snowlab CAA, 2024)
    {
        "fecha": "2024-06-15",
        "nombre": "Tormenta extraordinaria",
        "snowlab_alto": 5,
        "era5_precip_mm": 0.4,
        "era5_precip_72h_mm": 1.8,
        "temperatura_C": -3.2,
        "viento_ms": 6.5,
        "nieve_nueva_wn2_cm": 62.0,   # HN3d Caro 2026: +62 cm en 3 días
        "alertas_sat": ["NEVADA_RECIENTE_INTENSA"],
        "tipo": "tormenta",
    },
    {
        "fecha": "2024-06-21",
        "nombre": "Post-tormenta alta",
        "snowlab_alto": 4,
        "era5_precip_mm": 0.1,
        "era5_precip_72h_mm": 0.5,
        "temperatura_C": -2.8,
        "viento_ms": 8.2,
        "nieve_nueva_wn2_cm": 8.0,    # HN3d: +3 cm (manto cargado, placas residuales)
        "alertas_sat": ["NEVADA_RECIENTE_MODERADA"],
        "tipo": "tormenta",
    },
    {
        "fecha": "2024-08-02",
        "nombre": "Tormenta moderada",
        "snowlab_alto": 3,
        "era5_precip_mm": 0.8,
        "era5_precip_72h_mm": 3.2,
        "temperatura_C": -1.9,
        "viento_ms": 5.0,
        "nieve_nueva_wn2_cm": 20.0,   # HN3d: +9 cm → WN2 estima ~20 cm
        "alertas_sat": ["NEVADA_RECIENTE_MODERADA"],
        "tipo": "tormenta",
    },
    # Días de calma (sin regresión)
    {
        "fecha": "2024-07-05",
        "nombre": "Calma — SD estable",
        "snowlab_alto": 1,
        "era5_precip_mm": 0.0,
        "era5_precip_72h_mm": 0.0,
        "temperatura_C": -2.0,
        "viento_ms": 1.5,
        "nieve_nueva_wn2_cm": 0.0,
        "alertas_sat": [],
        "tipo": "calma",
    },
    {
        "fecha": "2024-07-19",
        "nombre": "Calma — descenso SD",
        "snowlab_alto": 1,
        "era5_precip_mm": 0.0,
        "era5_precip_72h_mm": 0.0,
        "temperatura_C": -1.5,
        "viento_ms": 2.0,
        "nieve_nueva_wn2_cm": 0.0,
        "alertas_sat": [],
        "tipo": "calma",
    },
    {
        "fecha": "2024-08-23",
        "nombre": "Calma — manto estable",
        "snowlab_alto": 1,
        "era5_precip_mm": 0.0,
        "era5_precip_72h_mm": 0.0,
        "temperatura_C": -0.8,
        "viento_ms": 1.8,
        "nieve_nueva_wn2_cm": 0.0,
        "alertas_sat": [],
        "tipo": "calma",
    },
]


def evaluar_version(evento: dict, version: str) -> dict:
    """
    Evalúa un evento en tres versiones:
      v22 : sin fixes (ERA5 solo, PINN estático)
      v23 : solo FIX-SAT-STORM (señal satelital)
      v24 : FIX-SAT-STORM + FIX-WN2-PINN (señal satelital + forzante PINN)
    """
    usar_sat = version in ("v23", "v24")
    usar_pinn_wn2 = version == "v24"

    # ── S1: PINN ──────────────────────────────────────────────────────────────
    nieve_pinn = evento["nieve_nueva_wn2_cm"] if usar_pinn_wn2 else None
    pinn = ejecutar_calcular_pinn(
        **TOPO_LA_PARVA,
        temperatura_superficie_C=evento["temperatura_C"],
        nieve_nueva_cm=nieve_pinn if nieve_pinn else None,
    )
    estab_manto = ejecutar_evaluar_estabilidad_manto(
        estado_pinn=pinn["estado_manto"],
        factor_seguridad=pinn["factor_seguridad_mohr_coulomb"],
        riesgo_topografico="alto",
        alertas_topograficas=pinn["alertas_pinn"],  # incluye SURCHARGE_* de FIX-WN2-PINN
    )
    estab_topo = estab_manto["estabilidad_eaws"]

    # ── S2 satélite (simplificado) ────────────────────────────────────────────
    # En v22 no hay señal satelital; en v23/v24 la señal viene de alertas_sat
    # estab_sat = "poor" siempre como baseline (ViT sin evento activo)
    estab_sat = "poor"

    # ── S3: ventanas críticas ─────────────────────────────────────────────────
    alertas_sat = evento["alertas_sat"] if usar_sat else []
    ventanas = ejecutar_detectar_ventanas_criticas(
        temperatura_actual_C=evento["temperatura_C"],
        velocidad_viento_actual_ms=evento["viento_ms"],
        precipitacion_actual_mm=evento["era5_precip_mm"],
        precipitacion_72h_mm=evento["era5_precip_72h_mm"],
        nombre_ubicacion="La Parva Sector Alto",
        alertas_satelitales=alertas_sat,
    )

    # ── S5: clasificación EAWS ────────────────────────────────────────────────
    dias_bajo = 0 if evento["tipo"] == "tormenta" else 5
    eaws = ejecutar_clasificar_riesgo_eaws_integrado(
        estabilidad_topografica=estab_topo,
        factor_meteorologico=ventanas["factor_meteorologico_eaws"],
        ventanas_criticas_detectadas=ventanas["num_ventanas_criticas"],
        condiciones_meteo_disponibles=True,
        dias_consecutivos_nivel_bajo=dias_bajo,
        precipitacion_72h_corregida_mm=evento["era5_precip_72h_mm"],
        viento_kmh=evento["viento_ms"] * 3.6,
        nombre_ubicacion="La Parva Sector Alto",
        estabilidad_satelital=estab_sat,
    )

    return {
        "version": version,
        "fs": pinn["factor_seguridad_mohr_coulomb"],
        "estado_manto": pinn["estado_manto"],
        "estab_topo": estab_topo,
        "ventanas": ventanas["num_ventanas_criticas"],
        "factor_meteo": ventanas["factor_meteorologico_eaws"],
        "nivel": eaws["nivel_eaws_24h"],
        "nombre_nivel": eaws["nombre_nivel_24h"],
        "alertas_pinn": [a for a in pinn["alertas_pinn"] if "SURCHARGE" in a],
    }


def _sep(t=""):
    print(f"\n{'─'*70}")
    if t:
        print(f"  {t}")
        print(f"{'─'*70}")


def main():
    print("=" * 70)
    print("  AndesAI v24.0 — Comparativo de ajuste en 6 eventos (La Parva)")
    print("  FIX-SAT-STORM (v23) + FIX-WN2-PINN (v24) vs baseline v22")
    print("=" * 70)

    resultados = []

    for ev in EVENTOS:
        _sep(f"{ev['fecha']}  {ev['nombre']}  [Snowlab: {ev['snowlab_alto']}]")
        if ev["tipo"] == "tormenta":
            print(f"  ERA5: {ev['era5_precip_mm']} mm  |  WN2 nieve: {ev['nieve_nueva_wn2_cm']} cm/24h"
                  f"  |  Alertas S2: {ev['alertas_sat'] or '—'}")
        else:
            print(f"  Calma confirmada — sin precipitación, sin señal satelital")

        print(f"\n  {'Versión':<8} {'FS':>6} {'Estado PINN':<16} {'Estab.':>7}"
              f" {'Ventanas':>9} {'Factor':<22} {'EAWS':>4}")
        print(f"  {'─'*80}")

        fila = {"fecha": ev["fecha"], "nombre": ev["nombre"],
                "tipo": ev["tipo"], "snowlab": ev["snowlab_alto"]}

        for ver in ("v22", "v23", "v24"):
            r = evaluar_version(ev, ver)
            marcador = ""
            if ver == "v24" and ev["tipo"] == "tormenta":
                delta = r["nivel"] - ev["snowlab_alto"]
                marcador = f"  Δ={delta:+d}"
            print(
                f"  {ver:<8} {r['fs']:>6.3f} {r['estado_manto']:<16} {r['estab_topo']:>7}"
                f" {r['ventanas']:>9} {r['factor_meteo']:<22} {r['nivel']:>4}  {r['nombre_nivel']}{marcador}"
            )
            if r["alertas_pinn"]:
                print(f"           ↳ PINN: {', '.join(r['alertas_pinn'])}")
            fila[ver] = r["nivel"]

        resultados.append(fila)

    # ── Tabla resumen ──────────────────────────────────────────────────────────
    _sep("TABLA RESUMEN")
    tormentas = [r for r in resultados if r["tipo"] == "tormenta"]
    calmas    = [r for r in resultados if r["tipo"] == "calma"]

    print(f"\n  {'Fecha':<12} {'Evento':<25} {'GT':>3}  {'v22':>4} {'v23':>4} {'v24':>4}  {'Δ v22':>6} {'Δ v24':>6}")
    print(f"  {'─'*75}")
    for r in tormentas:
        print(f"  {r['fecha']:<12} {r['nombre']:<25} {r['snowlab']:>3}"
              f"  {r['v22']:>4} {r['v23']:>4} {r['v24']:>4}"
              f"  {r['v22']-r['snowlab']:>+6} {r['v24']-r['snowlab']:>+6}")
    print(f"  {'─'*75}")
    for r in calmas:
        ok22 = "✅" if r["v22"] == r["snowlab"] else "❌"
        ok24 = "✅" if r["v24"] == r["snowlab"] else "❌"
        print(f"  {r['fecha']:<12} {r['nombre']:<25} {r['snowlab']:>3}"
              f"  {r['v22']:>4} {r['v23']:>4} {r['v24']:>4}"
              f"  {ok22}        {ok24}")

    # ── Métricas ───────────────────────────────────────────────────────────────
    _sep("MÉTRICAS DE AJUSTE (tormentas, Sector Alto)")
    import statistics

    for ver, lbl in [("v22", "v22.0 baseline"), ("v23", "v23.0 FIX-SAT-STORM"),
                     ("v24", "v24.0 SAT+PINN")]:
        deltas = [r[ver] - r["snowlab"] for r in tormentas]
        mae   = statistics.mean(abs(d) for d in deltas)
        sesgo = statistics.mean(deltas)
        print(f"  {lbl:<28}  MAE={mae:.2f}  Sesgo={sesgo:+.2f}  "
              f"Δ individual: {' '.join(f'{d:+d}' for d in deltas)}")

    print()
    print("  Ground truth: Snowlab CAA La Parva (Domingo Valdivieso Ducci)")
    print("  Nota: v24 no alcanza Snowlab nivel 5 (techo = matriz poor/poor + frec.muy alta)")
    print("        Para nivel 5 se necesita estab_sat=very_poor (ViT bajo tormenta activa)")


if __name__ == "__main__":
    main()
