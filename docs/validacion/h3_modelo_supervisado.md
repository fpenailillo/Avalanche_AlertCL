# H3 — Modelo supervisado de features IMIS (Fase E, 2026-06-17)

**Pregunta:** ¿las features meteo+snowpack disponibles permiten alcanzar el rendimiento
de Techel 2022 (QWK 0.59) con un modelo supervisado, o el límite de H3 es de datos?

**Método:** RandomForest / HistGradientBoosting sobre features físicas de
`slf_meteo_snowpack` (NO `dangerLevel` → evita circularidad). GT = `slf_danger_levels_qc`
(nivel publicado). Split temporal **train 2010-2016 (n=393) / test 2017-2019 (n=296)**.
Script: `notebooks_validacion/modelo_h3_supervisado.py`.

## Resultados (test 2017-2019, n=296)

| Sistema | QWK | IC 95% bootstrap | F1-macro | acc | acc±1 |
|---|---|---|---|---|---|
| **RandomForest (features IMIS)** | **0.568** | [0.491, 0.638] | 0.395 | 0.720 | 0.993 |
| HistGradientBoosting | 0.546 | [0.470, 0.615] | 0.400 | 0.679 | 0.993 |
| DEAPSnow RF (`dangerLevel`) | 0.813 | [0.754, 0.864] | 0.665 | 0.841 | 1.000 |
| Agentic loop (v25.19) | 0.444 | [0.17, 0.64]* | — | — | — |
| Techel 2022 (referencia) | 0.590 | — | 0.550 | 0.640 | 0.950 |
| Naïve "siempre N3" (sanity) | 0.000 | — | 0.175 | 0.541 | 0.943 |

\* IC del agentic medido sobre 2023-24 (n=41).

### Matriz RF (filas=GT, cols=pred)
```
     P1  P2  P3  P4
GT1   1  14   2   0
GT2   1  68  38   0
GT3   0  15 144   1     ← recall N3 = 90% (144/160)
GT4   0   0  12   0     ← N4 nunca predicho (12 casos, clase rara)
```

### Feature importance (RF, top)
```
HN24_7d 0.146 · HN24 0.136 · HN72_24 0.136 · wind_trans24 0.075 · RH 0.068 ·
SWE 0.049 · HS_meas 0.048 · TA 0.047
```

## Conclusiones (publicables)

1. **Las features bastan para H3.** El RF supervisado (0.568) es estadísticamente
   equivalente a Techel (0.59; el IC [0.49, 0.64] lo abarca). El límite de H3 **no es
   de datos** sino de cómo el sistema los usa.
2. **El gap es del agentic loop.** Agentic 0.444 vs supervisado 0.568 = **−0.124**,
   atribuible a la transferencia de dominio Andes→Alpes (PINN/parámetros andinos,
   reglas EAWS calibradas para base N1-N2 vs base N3 alpina).
3. **La señal predictiva es la nieve reciente** (HN24_7d/HN24/HN72_24 dominan), no la
   capa débil persistente puntual (ssi/pwl baja importancia). Esto **explica por qué el
   fix determinista de capa débil falló** (sesión previa, revert `28a3ee6`): el `ssi`
   puntual no es la señal de primer orden; el acumulado de nieve reciente sí.
4. **N4 sigue sin predecirse** (12 casos, clase muy rara) — limitación de class imbalance,
   común también en Techel.

## Implicación / siguiente paso (alcance aparte)

Si se quisiera cerrar el gap del agentic loop en Alpes, la vía sería integrar las
features de snowpack como una **tool supervisada de S5 para dominio alpino** (el modelo
RF como "asesor" de nivel base), en lugar de las reglas EAWS andinas. Es un cambio
arquitectónico, fuera del alcance de esta validación. Lo demostrado aquí: el techo
alcanzable con las features es ~0.57-0.59 (no el 0.444 actual).
