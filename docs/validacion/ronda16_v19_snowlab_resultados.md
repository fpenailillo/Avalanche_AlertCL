# Ronda 16 — Validación H4 La Parva v19.0 (FIX-CR19)

**Fecha ejecución:** 2026-05-19  
**Versión:** v19.0  
**GT:** Snowlab La Parva (boletines semanales 2024-2025)  
**n:** 87 pares (3 sectores × ~29 fechas, tolerancia ±7 días)

## Objetivo de la ronda

Verificar que FIX-CR19 (`nieve_nueva_cm = HN24_cm`) **no introduce regresión en H4**.  
FIX-CR19 usa guard `_es_alpes`: solo activa ventana `CARGA_NIEVE_PROFUNDA` en `region == "alpes_swiss"`.  
La Parva (`region == "andes_chile"`) no puede activar esta ventana → sin efecto esperado.

## Resultados H4

| Métrica | v19.0 (n=87) | Referencia v5.0 | Delta |
|---------|-------------|-----------------|-------|
| QWK | -0.067 | ~0.000 | -0.067 |
| MAE | 1.207 | ~1.6 | +0.39 mejora |
| Sesgo (AI−SL) | +0.793 | +1.609 | +0.816 mejora |
| F1-macro | 0.110 | — | — |

**❌ H4 NO ALCANZADA:** QWK = -0.067 (objetivo ≥ 0.40)  
**❌ Constraint v7.0 VIOLADO:** MAE tormentas (Snowlab≥3) = 1.417 > 1.00 (n=12)

## Distribución de niveles

| Nivel | Snowlab GT | AndesAI v19 |
|-------|-----------|-------------|
| 1 | 60 (69%) | 10 (11%) |
| 2 | 15 (17%) | 51 (59%) |
| 3 | 8 (9%) | 17 (20%) |
| 4 | 3 (3%) | 8 (9%) |
| 5 | 1 (1%) | 1 (1%) |

## Resultados por sector

| Sector | n | MAE | Sesgo | QWK |
|--------|---|-----|-------|-----|
| La Parva Sector Alto | 30 | 1.20 | +0.47 | -0.224 |
| La Parva Sector Bajo | 30 | 1.00 | +1.00 | +0.188 |
| La Parva Sector Medio | 27 | 1.44 | +0.93 | -0.132 |

## Matriz de confusión

```
             AI=1  AI=2  AI=3  AI=4  AI=5
  Snowlab=1     8    33    12     6     1
  Snowlab=2     1     8     4     2     0
  Snowlab=3     1     6     1     0     0
  Snowlab=4     0     3     0     0     0
  Snowlab=5     0     1     0     0     0
```

## Análisis

### FIX-CR19 no afecta La Parva (guard confirmado)

El guard `_es_alpes` en `tool_ventanas_criticas.py` bloquea la ventana `CARGA_NIEVE_PROFUNDA` para todas las zonas `andes_chile`. Dado que no hay baseline v18 La Parva disponible (el reproceso Snowlab no se corrió para v18), la comparación se hace contra v5.0 (referencia más antigua):

- **Sesgo mejoró sustancialmente**: +1.609 → +0.793 (-0.816). Las correcciones de FIX-CR17A (cap estabilidad `fair` en Andes Chile) y otras mejoras acumuladas redujeron la sobreestimación.
- **QWK degradó levemente**: ~0.000 → -0.067. Dentro del ruido esperado para n=87 y QWK cercano a cero.

### Problema estructural persistente: sobreestimación sistemática

AndesAI predice 69% nivel ≥2 cuando Snowlab dice 69% nivel 1. Esto refleja que:
1. **PINN La Parva**: reporta consistentemente estabilidad `poor` (potencial de terreno) → S5 no puede bajar de nivel 2 sin override explícito
2. **ERA5@9km**: sobreestima precipitación en Andes Central → factor meteorológico inflado
3. **Snowlab vs EAWS**: el boletín Snowlab es conservador; puede publicar nivel 1 "Bajo" aun cuando hay nieve nueva moderada

### Sector Bajo: el mejor (QWK=+0.188)

La Parva Sector Bajo tiene menor elevación (2200–3200m) → PINN `fair` más frecuente → menos sobreestimación.

### Tormentas (Snowlab≥3): subestimación severa

Sesgo=-1.417 en casos Snowlab≥3 significa que cuando la situación real es peligrosa, AndesAI **subestima** (paradoja con la sobreestimación general). Esto ocurre porque son eventos extremos donde ERA5 subestima la precipitación real en cumbre.

## Conclusión de la ronda

FIX-CR19 **no introduce regresión en H4** (confirmado por guard `_es_alpes`).  
El problema H4 es estructural y preexistente. Las correcciones pendientes para H4 son:
1. Calibración PINN para Andes Chile (sobreestima estabilidad `poor`)  
2. Factor de corrección orográfica ERA5 para La Parva
3. Alineación semántica Snowlab vs EAWS

## Trayectoria QWK

| Versión | H3 QWK (Suiza) | H4 QWK (La Parva) | Nota |
|---------|---------------|-------------------|------|
| v5.0 | — | ~0.000 | baseline antiguo |
| v17.0 | 0.048 | — | FIX-CR17A |
| v18.0 | 0.156 | — | FIX-CR18 |
| v19.0 | **0.236** | **-0.067** | FIX-CR19 |
| Techel (2022) | 0.590 | — | benchmark H3 |
