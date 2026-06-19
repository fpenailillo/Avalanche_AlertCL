"""Run de prueba B1: 1 boletín suizo 2023-24 con Qwen+WN2 para validar el pipeline."""
import os, sys, traceback
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentes.orquestador.agente_principal import OrquestadorAvalancha
from agentes.salidas.almacenador import guardar_boletin

try:
    orq = OrquestadorAvalancha()
    r = orq.generar_boletin(
        nombre_ubicacion="Interlaken",
        fecha_referencia=datetime.fromisoformat("2024-01-16T12:00:00+00:00"),
    )
    g = guardar_boletin(r)
    print(f"OK Interlaken 2024-01-16 → nivel={r.get('nivel_eaws_24h')} guardado_bq={g.get('guardado_bigquery')}")
except Exception:
    print("ERROR EN PIPELINE B1:")
    traceback.print_exc()
