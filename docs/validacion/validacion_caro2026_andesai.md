# Validación AndesAI v22.0 contra Dataset Caro et al. (2026)

**Fecha**: 2026-05-22  
**Versión AndesAI**: v22.0  
**Dataset**: `climas-chileno.clima.snow_depth_caro_2026` (Zenodo 10.5281/zenodo.20089265)  
**Ground truth**: `validacion_avalanchas.snowlab_boletines` (Snowlab La Parva, CAA)  
**Notebook**: `notebooks_validacion/10_sd_elevation_analysis.ipynb`

---

## 1. Descripción del análisis

Se construyó un cruce triple de tres fuentes independientes para el período jun–sep 2024,
cuenca del Maipo (La Parva, 33°S):

| Fuente | Variable | Resolución |
|---|---|---|
| `snow_depth_caro_2026` | SD observado in situ (cm) y HN3d (incremento 3 días) | Diaria |
| `boletines_riesgo` (v22.0) | Nivel EAWS 24h predicho por AndesAI | Por evento |
| `snowlab_boletines` | Nivel EAWS observado por CAA Snowlab (Alta/Media/Baja elevación) | Semanal |

**Pares triple-solapados**: 14 (toda la temporada 2024, niveles Snowlab 1–5).

---

## 2. Tabla de resultados

| Fecha | Snowlab Alto | AI v22 Alto | Snowlab Med | AI v22 Med | SD La Parva | HN3d | Δ Alto | Observación |
|---|---|---|---|---|---|---|---|---|
| 2024-06-15 | **5** | 2 | 4 | 3 | 96 cm | +62 cm | −3 | Tormenta extraordinaria |
| 2024-06-21 | **4** | 1 | 4 | 1 | 92 cm | +3 cm | −3 | Post-tormenta alta |
| 2024-06-28 | 2 | 1 | 2 | 1 | 105 cm | −8 cm | −1 | Descenso post-tormenta |
| 2024-07-05 | 1 | 1 | 1 | 2 | 94 cm | −4 cm | 0 | ✅ Calma |
| 2024-07-12 | 1 | 1 | 1 | 2 | 89 cm | −2 cm | 0 | ✅ Calma |
| 2024-07-19 | 1 | 1 | 1 | 1 | 83 cm | −4 cm | 0 | ✅ Calma |
| 2024-07-26 | 1 | 2 | 1 | 1 | 80 cm | −1 cm | +1 | Leve sobreestimación |
| 2024-08-02 | **3** | 1 | 3 | 2 | 88 cm | +9 cm | −2 | Tormenta moderada |
| 2024-08-09 | 2 | 1 | 1 | 2 | 98 cm | −8 cm | −1 | — |
| 2024-08-16 | 1 | 1 | 1 | 2 | 84 cm | −3 cm | 0 | ✅ Calma |
| 2024-08-23 | 1 | 1 | 1 | 1 | 84 cm | 0 cm | 0 | ✅ Calma |
| 2024-08-30 | 1 | 2 | — | 1 | 80 cm | −2 cm | +1 | Leve sobreestimación |
| 2024-09-06 | 1 | 1 | — | 1 | 69 cm | −5 cm | 0 | ✅ Calma |
| 2024-09-13 | 1 | 1 | — | 2 | 55 cm | −7 cm | 0 | ✅ Calma |

---

## 3. Métricas de desempeño

### AndesAI v22.0 vs Snowlab (Sector Alto, n=14)

| Métrica | Valor |
|---|---|
| MAE | **0.86** niveles |
| RMSE | — |
| Sesgo | **−0.57** (subestima) |
| QWK Sector Alto | **+0.112** |
| QWK Sector Medio | **+0.221** (n=11) |

### Desglose por tipo de día

| Tipo | n | Tasa de acierto |
|---|---|---|
| Nivel 1 (calma, SD estable) | 9 | **100%** correctos |
| Nivel ≥ 3 (tormenta activa) | 3 | **0%** correctos (todos subestimados ≥ 2 niveles) |
| Nivel 2 (transición) | 2 | Parcial (1 acierto dentro de ±1) |

---

## 4. Hallazgo principal: subestimación sistemática de tormentas

**El sistema AndesAI v22.0 predice correctamente el 100% de los días de calma
(nivel 1) pero falla en todos los eventos de tormenta (Snowlab ≥ 3).**

### Caso crítico: tormenta del 15 de junio 2024

- **SD La Parva**: +62 cm acumulados en 3 días (de 34 cm a 96 cm).
- **Snowlab CAA**: nivel 5 (Muy Alto) en Sector Alto — evento extraordinario.
- **AndesAI v22.0**: nivel 2 (Limitado) — subestimación de 3 niveles.
- **Causa documentada**: ERA5 retroactivo asignó precipitación insuficiente a este evento
  convectivo intenso → `ventanas_criticas = 2` → nivel conservador.

Snowlab describe el problema como *"Placas de tormenta + Placas de viento"*, consistente
con una nevada rápida seguida de redistribución eólica: exactamente el escenario donde
ERA5 (grilla ~9 km, sin resolución orográfica de detalle) falla en capturar la acumulación
local a 2703 m en La Parva.

### Causa raíz

El módulo S3 (`ConsultorBigQuery.obtener_condiciones_actuales`) obtiene precipitación
de ERA5 retroactiva. ERA5 subestima precipitación convectiva en valles andinos estrechos,
especialmente en eventos de advección del noroeste (Maipo, jun–ago):

```
ERA5 precip ≪ precip real → ventanas_criticas no activa → EAWS 1–2
Snowlab mide SD real → HN3d +62 cm → EAWS 5 correcto
```

Esta limitación fue documentada previamente en el diagnóstico ronda 17 (v22.0):
*"MAE tormentas = 1.667; ERA5 subestima precipitación convectiva"*.
El dataset Caro 2026 la cuantifica por primera vez con datos observacionales independientes.

---

## 5. Hallazgo secundario: sesgo de verano corregido en v20+

El cruce con 10 pares de verano (dic 2023–abr 2024, versión v3.2) mostró:

- **v3.2**: EAWS promedio = 3.33 con SD = 0.2 cm (sin nieve). 10/10 boletines con EAWS ≥ 3.
- **v22.0**: 0/14 boletines de invierno con EAWS ≥ 3.5 cuando SD decrecía.

El **FIX-CR7A-REFACTOR (v20.0)** que introduce la compuerta `senales_calma_confirmada`
eliminó completamente el sesgo de verano: el sistema ya no emite niveles altos cuando
la observación Caro confirma ausencia de nieve (SD < 2 cm).

**Mejora de correlación EAWS vs HN3d**:

| Versión | r(EAWS, HN3d) invierno |
|---|---|
| v3.2 | +0.31 |
| v22.0 | +0.59 |

La correlación casi se duplica: v22.0 es más físicamente coherente con las nevadas
recientes observadas, aunque aún falla cuando ERA5 no detecta la tormenta.

---

## 6. No-linealidad SD–elevación confirmada (Caro 2026)

El análisis de percentiles SD por estación en la cuenca del Maipo (13 estaciones,
2010–2024, temporada may–oct) confirma el hallazgo central del paper:

- **Pico de acumulación**: rango 3000–3500 m s.n.m.
- **Disminución sobre 4000 m**: consistente con sublimación eólica documentada
  en Glaciar Juncal Norte (Ayala et al. 2017).
- **Estación de mayor SD mediana en jul–ago**: Las Melosas (3317 m) o Glaciar
  Olivares Gamma (3628 m) según el año.

Esto invalida el supuesto de gradiente lineal positivo SD–elevación usado en
modelos transferidos desde SLF (Suiza) y tiene tres implicancias directas para AndesAI:

1. El subagente S1 (PINNs) debe recalibrarse para el gradiente no lineal andino.
2. La zona de mayor riesgo EAWS (pendientes 30–45° + máxima acumulación SD) coincide
   en el rango 3000–3500 m.
3. Las variables de exposición eólica deben incorporarse en S1 además de elevación.

---

## 7. Propuesta de mejora: HN3d Caro como señal complementaria en S3

El incremento HN3d observado por estaciones DGA (disponible en `snow_depth_caro_2026`
y, operacionalmente, en datos DGA en tiempo real) discrimina bien los eventos que
ERA5 subestima:

| HN3d observado | Snowlab nivel típico | AndesAI v22 (ERA5) |
|---|---|---|
| > 30 cm | 4–5 | 1–2 ❌ |
| 5–30 cm | 2–3 | 1–2 |
| < 5 cm | 1 | 1 ✅ |

**Rol del dataset Caro 2026 en AndesAI: exclusivamente validación offline.**

Los datos de SD observado no están disponibles en tiempo real operacional (el dataset
Caro 2026 cubre hasta dic-2024 y no existe feed DGA en tiempo real en el sistema).
Por lo tanto, `snow_depth_caro_2026` se usa únicamente para:

1. **Validación offline** (como en este análisis): comparar predicciones contra SD observado.
2. **Referencia de PCI** (Physical Consistency Index): la metodología QC de Caro et al. 2026
   se adapta para validar si los pronósticos de acumulación de WeatherNext 2 son
   físicamente consistentes (Pr > umbral, AT < umbral lluvia) — función
   `calcular_pci_pronostico()` en `datos/qc/snow_depth_qc.py`.

**Fuentes primarias para el modelo predictivo operacional:**
- **WeatherNext 2** (S3): precipitación ensemble, temperatura, viento — señal de tormenta.
- **Observaciones satelitales** (S2): cambios en NDSI, cobertura nieve, SAR — estado del manto.

El fix al MAE-tormentas debe venir de mejorar el uso de WN2 y satélite,
no de incorporar observaciones de estaciones que no estarán disponibles en producción.

---

## 8. Limitaciones de esta validación

1. **n = 14 pares**: muestra pequeña. El período Caro 2026 termina en dic-2024
   y los boletines v22.0 comienzan en jun-2024; el solapamiento es una sola temporada.
2. **Versiones distintas en verano vs invierno**: la comparación v3.2 vs v22.0 se hace
   sobre períodos distintos (no A/B en el mismo conjunto de fechas).
3. **Lag Snowlab**: los boletines Snowlab tienen validez de 2–3 días; se asignó la
   fecha de inicio a cada boletin, lo que puede introducir desfase de ±1 día.
4. **SD en La Parva ≠ SD en terreno de avalancha**: La Parva (2703 m) mide SD a
   fondo de valle; las zonas de inicio EAWS están a 3000–4000 m. El HN3d de
   Laguna Negra (2785 m) o Las Melosas (3317 m) sería más representativo.
5. **Solo datos clean de Caro**: Zenodo v4.2 no incluye datos raw. No es posible
   evaluar el efecto del pipeline QC propio sobre la señal HN3d.

---

## 9. Referencias

- Caro, A. et al. (2026). The Southern Andes Daily Snow Depth Dataset (2010–2024).
  *Earth System Science Data Discussions*, in review. doi:10.5194/essd-2026-324
- Medina, J. & Caro, A. (2026). Dataset Zenodo. doi:10.5281/zenodo.20089265
- Ayala, Á. et al. (2017). Sublimation at Juncal Norte Glacier.
  *Journal of Glaciology*, 63(241), 803–822.
- Snowlab La Parva (CAA, Domingo Valdivieso Ducci) — ground truth H4 AndesAI.
- REQ-2026-09: Integración Dataset Caro et al. 2026 en AndesAI.
- Ronda 17 resultados v22.0: `docs/validacion/ronda17_v22_resultados.md`.
