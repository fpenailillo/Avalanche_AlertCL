"""
Verificación del artefacto de persistencia rota en validación H4.

Hipótesis: en el reproceso con fechas salteadas, FIX-POST-STORM-PERSIST
(nivel_hoy ≥ nivel_ayer-1) no puede actuar porque no existe el boletín del
día anterior. Procesando días CONSECUTIVOS alrededor de una tormenta, el
descenso progresivo debería reproducir el comportamiento operacional y subir
el nivel del día post-tormenta (2024-06-15, GT=5) de N1 a ~N4.

Uso:
    SUBAGENTES_PROVEEDOR=qwen3 USE_WEATHERNEXT2=true VALIDACION_VERSION=25.18 \
      python3 notebooks_validacion/verificar_artefacto_persistencia.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentes.orquestador.agente_principal import OrquestadorAvalancha
from agentes.salidas.almacenador import guardar_boletin

SECTOR = "La Parva Sector Alto"
# Cadena consecutiva: 06-13 (pre), 06-14 (tormenta 60cm), 06-15 (post, GT=5)
FECHAS = ["2024-06-13", "2024-06-14", "2024-06-15"]

print(f"Verificando cadena de persistencia para {SECTOR}")
print("Esperado: 06-14 alto (tormenta), 06-15 hereda descenso (ayer-1) → N≥4")
print("=" * 60)

for fecha in FECHAS:
    orq = OrquestadorAvalancha()
    fref = datetime.fromisoformat(f"{fecha}T12:00:00+00:00")
    r = orq.generar_boletin(nombre_ubicacion=SECTOR, fecha_referencia=fref)
    nivel = r.get("nivel_eaws_24h")
    factor = r.get("factor_meteorologico")
    guardar_boletin(r)  # guardar para que el día siguiente lo vea como "ayer"
    print(f"  {fecha}  nivel={nivel}  factor={factor}")

print("=" * 60)
print("Si 06-15 pasó de N1 (sin cadena) a N≥4 (con cadena) → artefacto confirmado.")
