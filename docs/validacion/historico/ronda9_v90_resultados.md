# Ronda 9 — Validación v9.0 (FIX-CR7A-REGIONAL)

**Fecha:** 2026-05-11  
**Versión:** v9.0 (FIX-CR7A-REGIONAL en `tool_clasificar_eaws.py`)  
**Alcance del reproceso:** Solo Suiza (30 runs — 3 estaciones × 10 fechas)  
**H4 sin cambio:** La Parva no se reprocesó; resultados H4 = v8.0

---

## Fix implementado (v9.0)

**FIX-CR7A-REGIONAL:** Diferencia `condiciones_meteo_disponibles` por región geográfica a nivel de tool:

```python
_region_meteo = _obtener_region(nombre_ubicacion) if nombre_ubicacion else "andes_chile"
if _region_meteo == "andes_chile" and condiciones_meteo_disponibles is True:
    condiciones_meteo_disponibles = False  # forzado — sin mediciones reales
```

- **La Parva / Andes Chile:** `condiciones_meteo_disponibles` siempre → `False` (sin estaciones reales en `condiciones_actuales`). EAWS Paso 1 no se activa.
- **Alpes / Suiza:** respeta el valor que entrega S5 (ERA5 válido como proxy). EAWS Paso 1 puede activarse cuando S5 pasa `True`.

---

## Resultados H1/H3 — Swiss SLF (n=24 pares)

| Métrica | v7.5 R7 | v8.0 R8 | **v9.0 R9** | Objetivo |
|---------|---------|---------|-------------|---------|
| QWK | +0.103 | −0.073 | **+0.049** | ≥ 0.59 |
| F1-macro | — | 0.156 | **0.288** | ≥ 0.75 |
| Sesgo | — | −0.88 | **−0.71** | — |
| Accuracy exacta | — | — | 0.417 | — |
| Accuracy ±1 | — | — | 0.792 | — |

### Estado

- **H1 ❌** F1-macro 0.288 vs objetivo ≥ 0.75
- **H3 ❌** QWK +0.049 vs objetivo ≥ 0.59

### Evolución QWK H3

```
v7.5 (R7): +0.103  ← mejor hasta ahora
v8.0 (R8): −0.073  ← regresión (FIX-CR7A global afectó Suiza)
v9.0 (R9): +0.049  ← recuperación parcial (+0.122 vs v8.0)
```

FIX-CR7A-REGIONAL recuperó la mitad de la regresión de v8.0, pero no llega al nivel de v7.5.

### Distribución de predicciones v9.0

| Nivel | SLF GT | AndesAI v8.0 | AndesAI v9.0 |
|-------|--------|--------------|--------------|
| 1 | 12.5% | 62.5% | **50.0%** |
| 2 | 54.2% | 25.0% | **37.5%** |
| 3 | 20.8% | 12.5% | **12.5%** |
| 4 | 12.5% | 0.0% | **0.0%** |

v9.0 desplaza nivel-1 de 62.5% a 50%: la corrección es real pero insuficiente. El sistema sigue sobreprediciendo nivel 1 en Suiza.

### Desglose por estación v9.0

| Estación | Fecha | Nuestro | SLF | Dif |
|----------|-------|---------|-----|-----|
| Interlaken | 2023-12-01 | 3 | 4 | −1 |
| Interlaken | 2023-12-15 | 1 | 3 | −2 |
| Interlaken | 2024-01-01 | 2 | 3 | −1 |
| Interlaken | 2024-01-15 | 1 | 2 | −1 |
| Interlaken | 2024-02-01 | 1 | 2 | −1 |
| Interlaken | 2024-02-15 | 2 | 2 | 0 |
| Interlaken | 2024-03-01 | 1 | 3 | −2 |
| Interlaken | 2024-03-15 | 3 | 2 | +1 |
| Interlaken | 2024-04-01 | 1 | 3 | −2 |
| Interlaken | 2024-04-15 | 1 | 1 | 0 |
| Matterhorn Zermatt | 2023-12-01 | 3 | 3 | 0 |
| Matterhorn Zermatt | 2024-01-01 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2024-02-01 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2024-02-15 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2024-03-01 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2024-03-15 | 2 | 2 | 0 |
| Matterhorn Zermatt | 2024-04-01 | 1 | 4 | −3 |
| St Moritz | 2024-01-01 | 1 | 2 | −1 |
| St Moritz | 2024-01-15 | 1 | 2 | −1 |
| St Moritz | 2024-02-01 | 2 | 1 | +1 |
| St Moritz | 2024-02-15 | 2 | 2 | 0 |
| St Moritz | 2024-03-15 | 1 | 2 | −1 |
| St Moritz | 2024-04-01 | 1 | 4 | −3 |
| St Moritz | 2024-04-15 | 1 | 1 | 0 |

---

## Resultados H4 — Snowlab La Parva (sin cambio, igual a v8.0)

No se reprocesó La Parva con v9.0 (reproceso `--solo-suiza`).  
FIX-CR7A-REGIONAL no cambia el comportamiento de La Parva (ya forzaba `False` desde v8.0).  
Los resultados de H4 son idénticos a v8.0:

| Métrica | v8.0 R8 | Objetivo |
|---------|---------|---------|
| QWK | +0.028 | ≥ 0.05 |
| MAE | 0.828 | ≤ 1.00 ✅ |
| Sesgo | +0.299 | ≤ +0.60 ✅ |
| % nivel 1-2 | 85.1% | ≥ 65% ✅ |
| MAE tormentas | 1.667 | ≤ 1.00 ❌ |

---

## Diagnóstico post-Ronda 9

### ¿Por qué v9.0 no recupera completamente v7.5?

v7.5 (QWK=+0.103) usaba `condiciones_meteo_disponibles` sin los fixes CR-7 → algunos runs suizos llegaban a nivel 2–3 por caminos distintos. La cadena de fixes cambió el comportamiento global.

**Causa principal de sobrepredicción nivel 1 en Suiza (v9.0):**

El sesgo negativo persistente (−0.71) y 50% nivel-1 sugieren que S5 en Suiza sigue interpretando la mayoría de situaciones como estables, incluso con ERA5 disponible. Posibles causas:

1. **Umbrales S3 (pronóstico):** `detectar_ventanas_criticas` requiere triggers EAWS simultáneos que ERA5 raramente activa en las fechas de evaluación → `num_ventanas_criticas` siempre 0 → matriz conservadora → nivel 1–2.
2. **S1 (topográfico):** En Alpes el sistema quizás marca `estabilidad_topografica="good"` con demasiada frecuencia → baja probabilidad de avalancha → nivel 1.
3. **Matterhorn Zermatt 2024-04-01 y St Moritz 2024-04-01:** Ambos predicen nivel 1 cuando SLF = 4 (diferencia de 3 niveles). Eventos de primavera tardía (posiblemente avalanchas de deshielo/wet snow) que ERA5 no detecta.

### Opciones v10.0

| Opción | Impacto esperado H3 | Riesgo H4 |
|--------|--------------------|---------:|
| A. Reducir umbral `ventanas_criticas` en Alpes (IMIS/ERA5 combinado) | Moderado (+0.05–+0.10 QWK) | Bajo |
| B. Prompt S1 reforzado para primavera tardía Alpes (wet snow) | Alto en eventos nivel 3–4 | Bajo |
| C. Ajuste matriz EAWS para Alpes (factor estacional) | Moderado-alto | Medio |
| D. Usar datos IMIS directos en Suiza (in situ) | Alto (datos reales) | Ninguno |

---

## Resumen consolidado de versiones

| Ronda | Versión | QWK H3 | QWK H4 | MAE H4 | Sesgo H4 |
|-------|---------|--------|--------|--------|----------|
| R3 | v4.0 | +0.162 | −0.006 | 2.138 | +2.023 |
| R4 | v5.0 | +0.143 | −0.000 | 1.724 | +1.609 |
| R5 | v6.2 | −0.031 | −0.031 | 1.230 | +0.885 |
| R7 | v7.5 | +0.103 | −0.139 | 1.448 | +1.011 |
| R8 | v8.0 | −0.073 | +0.028 | 0.828 | +0.299 |
| **R9** | **v9.0** | **+0.049** | **(=v8.0)** | **(=v8.0)** | **(=v8.0)** |
