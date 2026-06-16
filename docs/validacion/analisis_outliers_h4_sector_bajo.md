# Análisis de outliers H4 — Sector Bajo La Parva (GT=2→AI=5)

**Fecha:** 2026-06-14
**Versión analizada:** v26.0 (Gemini 3.1 Pro)
**Contexto:** revisión metodológica data-driven para H4. Los dos pares GT=2→AI=5
del Sector Bajo en inicio de temporada 2024 explicaban casi en solitario el bajo
QWK de ese sector (0.198 vs Alto 0.623, Medio 0.510).

## Pares analizados

| Fecha | Sector | AI | GT Snowlab | estado_pinn | factor_meteo | nieve_wn2 | tamaño |
|-------|--------|----|-----------|-------------|--------------|-----------|--------|
| 2024-06-15 | Bajo | 5 | 2 | CRITICO | CICLO_DIURNO_NORMAL | null | 5 (estático) |
| 2024-06-21 | Bajo | 5 | 2 | INESTABLE | NEVADA_RECIENTE+VIENTO_FUERTE | 65 cm | 5 |

El mismo 2024-06-15, Snowlab asignó **GT=5 al Sector Alto, GT=4 al Medio y GT=2 al
Bajo** (3 niveles de diferencia entre sectores). AndesAI **acertó el N5 del Sector
Alto** y aplicó N5 también al Bajo.

## Hipótesis inicial: "manto incipiente" (REFUTADA)

La hipótesis era que en inicio de temporada el manto base es delgado y no puede
sostener avalanchas de tamaño D5, por lo que el tamaño estático D5 de la topografía
inflaba el nivel. El fix propuesto era capar el tamaño cuando el manto fuera incipiente.

### Verificación de fuentes de manto base

| Fuente | ¿Discrimina manto? | Cobertura | Conclusión |
|--------|--------------------|-----------|------------|
| `era5_snow_depth_m` (ERA5-Land @9km) | No (máx 0-12 cm, ruidoso, varios ~0 en todos los centros andinos) | solo 2026-03+ | Subrepresenta el manto andino; no sirve |
| WeatherNext 2 (`pronostico_wn2`) | No (forecast de nieve diaria, sin variable de manto) | solo pronóstico vigente | Sin histórico; no aplica |
| **Caro et al. 2026 (in-situ DGA)** | **Sí** (est. "La Parva" 2703m, máx 129 cm) | 2010 → 2024-12-31 | Única fuente válida; usada para **verificar** la hipótesis |

> **Uso excepcional de Caro:** el dataset Caro/DGA está reservado a validación offline
> (no se integra como feature del modelo, para no crear dependencia de datos in-situ
> no disponibles en operación). Aquí se autorizó su uso **solo para verificar** la
> hipótesis de manto, ante la falta de una señal satelital de manto fiable. No se
> incorporó al pipeline del modelo.

### Resultado: el manto NO era incipiente

Serie Caro "La Parva", snow_depth_cm (temporada 2024):

```
2024-06-13:  41 cm
2024-06-14: 102 cm   ← nevada de ~60 cm en un día
2024-06-15:  96 cm   ← outlier (AI=5)
2024-06-21:  92 cm   ← outlier (AI=5)
2024-06-22: 129 cm   ← máximo estacional
```

El 15 y 21 de junio el manto era de **92-96 cm** (cerca del máximo de temporada),
tras una gran nevada el día 14. **La premisa de "manto incipiente" es falsa.**

## Verificación adicional con WeatherNext 2 histórico (2026-06-14)

El dataset WN2 cubre desde 2022-01-01 y ahora retorna señal para estas fechas
(`obtener_ventanas_6h` por sector con su elevación):

| Fecha | Sector (elev) | Tmin/Tmax | cota 0°C media | nieve 24h p50 | snow_type |
|-------|---------------|-----------|----------------|---------------|-----------|
| 2024-06-21 | Bajo (2300m) | −11/−7°C | 694 m | 65 cm | storm_slab |
| 2024-06-15 | Bajo (2300m) | −15/−3°C | 564 m | ~0 cm | dry_snow (post-tormenta del 14) |

La **cota isoterma 0°C estaba en ~560-700 m**, muy por debajo de los 2300 m del
Sector Bajo. Es decir, la precipitación cayó como **nieve seca en todas las cotas**
— no hay fracción de lluvia que descontar por elevación. **WN2 confirma que el nivel
4-5 de AndesAI en zonas de inicio es correcto y que el GT=2 de Snowlab subestima.**
Un fix de "atenuación por fase nieve/lluvia según elevación" no aplica aquí.

WN2 sí aporta una mejora **legítima vía reproceso** (no por cap manual): el 2024-06-15
la nieve nueva real era ~0 (la nevada fue el 14), por lo que con la señal WN2 correcta
el modelo no lo trataría como tormenta activa → clasificación post-tormenta más fiel.

## Conclusión

Con ~95 cm de manto + ~60 cm de nieve nueva reciente + placas de tormenta y viento,
un nivel **4-5 en zonas de inicio (35-45°, el terreno que AndesAI evalúa) es
físicamente correcto**. La discrepancia con Snowlab (GT=2 en el Sector Bajo) se
explica por:

1. **Diferencia de definición de terreno** — Snowlab reporta el nivel para terreno
   general (<35°, el 95% del área esquiable); AndesAI evalúa zonas de inicio de
   avalanchas (35-45°). En EAWS, el terreno empinado es estructuralmente ~1 nivel
   superior bajo las mismas condiciones (ver `estado_validacion_h4_v17.md`).
2. **Falta de atenuación por elevación entre sectores** — el modelo aplica la misma
   señal WN2 de nieve/viento a los 3 sectores; el Sector Bajo (cota menor) recibe
   en realidad menos nieve fresca. Mejora real pero de impacto marginal (1-2 pares)
   y con riesgo de reducir sensibilidad a tormentas; diferida a investigación futura.

**Decisión: no capar estos pares.** Hacerlo perseguiría un ground truth no comparable
(otro terreno) capando una predicción físicamente correcta, lo que violaría la
integridad metodológica. Además, FIX-SAT-DEFAULT-NO-ELEVA (A1) ya lleva H4 a
QWK≈0.627 (≥0.60) sin tocar estos outliers.

## Referencias

- `docs/validacion/estado_validacion_h4_v17.md` — diferencia de definición de terreno (respuesta a/d del equipo Snowlab)
- `agentes/datos/consultor_bigquery.py:1730` — `obtener_snow_depth_caro` (Caro et al. 2026, doi:10.5281/zenodo.20089265)
- `agentes/subagentes/subagente_integrador/tools/tool_clasificar_eaws.py` — FIX-SAT-DEFAULT-NO-ELEVA (A1)
