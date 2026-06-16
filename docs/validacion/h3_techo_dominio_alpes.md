# H3 — Techo por gap de dominio Andes→Alpes (v25.18, 2026-06-16)

**Hipótesis H3:** QWK comparable a Techel et al. (2022), umbral ≥ 0.59.
**Resultado:** QWK = **0.268** (n=38, Suiza 2023-24, GT `slf_danger_levels_qc`).
**Estado:** NO alcanzada — limitada estructuralmente por el gap de dominio, no por calibración.

## Progresión (mejor cifra histórica en Suiza)

| Versión | GT | QWK H3 | n | Sesgo |
|---------|----|----|---|-------|
| v25.11 Qwen | IMIS DEAPSnow 2018-19 | 0.040 | 29 | +0.83 |
| v26.0 Gemini | IMIS DEAPSnow 2018-19 | 0.101 | 28 | +1.00 |
| v25.18 Qwen (calibrado +0.7 obsoleto) | slf_danger_levels_qc 2023-24 | 0.229 | 38 | +0.58 |
| v25.18 Qwen (recalibrado identidad, B2) | slf_danger_levels_qc 2023-24 | 0.268 | 38 | −0.42 |
| **v25.19 Qwen (FIX-STORM/SIZE-ALPES)** | **slf_danger_levels_qc 2023-24** | **0.444** | 41 | −0.20 |

La mejora (0.04/0.10 → **0.444**) proviene de: GT correcto (niveles QC publicados, el de Techel), WN2 histórico (2022+) como señal meteo, recalibración (eliminar shift +0.7 obsoleto), y **FIX-STORM/SIZE-ALPES** (extender graduación WN2 de tamaño/frecuencia a Alpes sin IMIS → captura días de tormenta). Aun así no cruza 0.59.

### Matriz v25.19 (n=41)
```
      AI2  AI3  AI4  AI5
GT2   17    0    0    0    ← 17/17 aciertos (días tranquilos)
GT3   12    2    0    2    ← 12 subestimados (capa persistente, gap dominio) + 2 sobre N5
GT4    2    1    0    2
```
El fix captura tormentas (GT=3-4 antes en N2 ahora suben). Residual: (a) ~4 casos sobreestiman a N5 en tormenta (Zermatt; capar N5→N4 da QWK 0.431/acc 0.51 — intercambiable con n pequeño); (b) **12 casos GT=3→N2 son días sin tormenta = capa débil persistente**, el techo real (gap de dominio, sin datos IMIS de snowpack).

## La calibración existente era contraproducente (corregido en B2)

El coeficiente `alpes_swiss` tenía un shift **α=+0.7** entrenado cuando el modelo *subestimaba* (sesgo histórico −0.7). Con los fixes v25.18 el modelo ya no subestima, así que ese shift empujaba sistemáticamente N2→N3:

| | QWK | Sesgo | Distribución |
|--|-----|-------|--------------|
| Calibrado (+0.7, obsoleto) | 0.229 | +0.58 | colapsa a N3 |
| **Identidad (crudo, recalibrado)** | **0.268** | −0.42 | colapsa a N2 |

Re-entrenado con los 38 pares v25.18, el calibrador **rechaza toda calibración** para `alpes_swiss` (OLS no mejora en CV; shift óptimo +0.42 < umbral 0.5) → aplica **identidad**. Se elimina el +0.7 dañino.

## El techo: discriminación limitada en Alpes (matriz cruda)

```
       AI=2  AI=3        (el modelo solo emite N2-N3; nunca N1/N4/N5)
GT=1     2    0
GT=2    15    1     ← acierta GT=2 (15/16)
GT=3    12    3     ← subestima GT=3 (12/15 → N2)
GT=4     2    3     ← nunca alcanza N4
```

El modelo **comprime toda la variación en N2-N3**: acierta los días tranquilos (GT=2) pero no separa GT=3 de GT=2, y nunca emite N4. La calibración (shift/escala) **no puede crear discriminación que no existe** — solo mueve o estira una distribución ya colapsada.

## Causa raíz (gap de dominio, documentado)

El sistema fue calibrado en topografía andina:
- **PINN**: métricas de fricción/cohesión de La Parva/Valle Nevado (roca volcánica); difieren del granito alpino.
- **Parámetros EAWS y umbrales**: ajustados para el régimen andino.
- **ERA5 @9km**: subrepresenta la orografía alpina, más compleja.

En los Alpes, el SLF reporta N2-N4 en condiciones que en Andes serían N1-N2; el modelo no transfiere esa escala. Es el mismo gap descrito en rondas previas (R3-R5).

## Conclusión

- **H3 no es alcanzable (≥0.59) solo con calibración ni con más datos.** Requeriría recalibrar el modelo físico base para el dominio alpino (fricción granito, umbrales por región) o entrenar con datos alpinos — fuera del alcance actual.
- **Resultado publicable:** cuantifica la transferencia de dominio Andes→Alpes. El sistema, sin reentrenamiento alpino, alcanza QWK 0.27 y accuracy ±1 = 0.95 (errores de ≤1 nivel), partiendo de un dominio físico distinto.
- **Acción aplicada:** calibración `alpes_swiss` desactivada (identidad), que reflejaba un sesgo ya inexistente.

Misma fuente y rango se usan ahora en `agentes/validacion/calibrador.py::_cargar_pares_suiza` (slf_danger_levels_qc 2023-24) para mantener coherencia calibración↔validación (`07_validacion_slf_suiza.py --qc-2324`).
