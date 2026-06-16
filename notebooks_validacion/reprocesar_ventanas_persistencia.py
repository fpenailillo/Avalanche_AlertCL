"""
Reproceso con ventana consecutiva para fechas post-tormenta afectadas por el
artefacto de persistencia rota (FIX-POST-STORM-PERSIST no actúa sin la cadena
de días previos en el reproceso salteado).

Para cada fecha de validación del Grupo A (post-tormenta), procesa los K días
previos consecutivos + la fecha, en orden cronológico por sector, de modo que
_obtener_nivel_ayer() encuentre el nivel del día anterior y aplique el descenso
gradual (nivel_hoy ≥ nivel_ayer-1), reproduciendo el comportamiento operacional.

Solo Grupo A: la cadena corrige post-tormenta. El Grupo B (GT=2 calmo sin
tormenta) es diferencia de definición de terreno y no se toca.

Uso:
    SUBAGENTES_PROVEEDOR=qwen3 USE_WEATHERNEXT2=true VALIDACION_VERSION=25.18 \
      python3 notebooks_validacion/reprocesar_ventanas_persistencia.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentes.orquestador.agente_principal import OrquestadorAvalancha
from agentes.salidas.almacenador import guardar_boletin

K_DIAS_PREVIOS = 4  # días consecutivos antes de la fecha objetivo (cadena de persistencia)

# Grupo A: fechas post-tormenta con sus sectores afectados (GT≥2→AI=1 por cadena rota)
VENTANAS = [
    ("2024-06-15", ["La Parva Sector Alto", "La Parva Sector Medio", "La Parva Sector Bajo"]),
    ("2024-06-28", ["La Parva Sector Alto", "La Parva Sector Medio", "La Parva Sector Bajo"]),
    ("2025-06-14", ["La Parva Sector Alto", "La Parva Sector Medio", "La Parva Sector Bajo"]),
    ("2025-06-21", ["La Parva Sector Alto", "La Parva Sector Medio"]),
    ("2025-07-25", ["La Parva Sector Bajo"]),
]


def dias_ventana(fecha_obj: str, k: int) -> list[str]:
    f = datetime.fromisoformat(fecha_obj)
    return [(f - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(k, -1, -1)]


def main():
    total = sum((K_DIAS_PREVIOS + 1) * len(secs) for _, secs in VENTANAS)
    print(f"Reproceso ventanas persistencia — {total} runs (K={K_DIAS_PREVIOS} días previos)")
    print("=" * 60)
    hecho = 0
    for fecha_obj, sectores in VENTANAS:
        dias = dias_ventana(fecha_obj, K_DIAS_PREVIOS)
        for sector in sectores:
            # procesar cronológicamente para construir la cadena de persistencia
            for fecha in dias:
                orq = OrquestadorAvalancha()
                fref = datetime.fromisoformat(f"{fecha}T12:00:00+00:00")
                try:
                    r = orq.generar_boletin(nombre_ubicacion=sector, fecha_referencia=fref)
                    guardar_boletin(r)
                    nivel = r.get("nivel_eaws_24h")
                    marca = " ←OBJETIVO" if fecha == fecha_obj else ""
                    hecho += 1
                    print(f"  [{hecho}/{total}] {sector} {fecha} → N{nivel}{marca}")
                except Exception as exc:
                    hecho += 1
                    print(f"  [{hecho}/{total}] {sector} {fecha} → ERROR: {str(exc)[:80]}")
    print("=" * 60)
    print("Completado. Re-medir: python3 notebooks_validacion/08_validacion_snowlab.py --version v25.18")


if __name__ == "__main__":
    main()
