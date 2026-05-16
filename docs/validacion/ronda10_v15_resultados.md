# Ronda 10 — Validación v15.0 (WeatherNext 2 + acumulado v10.x/v13.x)

**Fecha:** 2026-05-15  
**Versión:** v15.0  
**Alcance del reproceso:** Solo La Parva (90 runs — 3 sectores × 30 fechas)  
**H1/H3 Suiza:** sin cambio respecto a v9.0 (reproceso no ejecutado; fixes v10.x/v13.x son Alpes-específicos)

---

## Fixes acumulados desde v8.0 (última ronda con reproceso La Parva)

| Versión | Fix | Impacto esperado La Parva |
|---------|-----|--------------------------|
| v7.5 | S1: eliminados triggers meteo falsos; S5 determina EAWS Paso 1 | Moderado — S1 ya no activa triggers sin datos |
| v10.1 | CR-10A+CR-10B: calibración ERA5 regional Alpes (precip 72h, viento 7m/s) | Bajo — parámetros Alpes; La Parva usa ERA5 indirectamente |
| v13.0 | FIX-CA-WINDOW: ventana ±12h condiciones_actuales | Nulo — La Parva sin IMIS, no usa CA |
| v15.0 | WN2 tool opcional en S3 (disponible=False para fechas históricas 2024-2025) | Nulo para histórico; activo en producción futura |

**Cambio neto esperado para La Parva:** principalmente v7.5 (S1 prompt) y v10.1 (integrador).

---

## Configuración del reproceso

```
Sectores : La Parva Sector Alto / Sector Medio / Sector Bajo
Fechas   : 30 fechas temporadas 2024 y 2025 (junio–septiembre)
Ground truth : Snowlab La Parva (boletines semanales, nivel por banda)
Skip check   : STARTS_WITH(version_prompts, 'v15')
Timeout/run  : 480 s
Estimado     : 90 runs × ~100 s ≈ 2.5 h
```

---

## Resultados H4 — Snowlab La Parva

> **[PENDIENTE — reproceso en ejecución]**  
> Completar esta sección ejecutando:
> ```
> python notebooks_validacion/08_validacion_snowlab.py --version v15
> ```

| Métrica | v8.0 R8 | **v15.0 R10** | Δ | Objetivo | Estado |
|---------|---------|---------------|---|---------|--------|
| QWK | +0.028 | TBD | — | ≥ 0.05 | — |
| MAE | 0.828 | TBD | — | ≤ 1.00 ✅ | — |
| Sesgo | +0.299 | TBD | — | ≤ +0.60 ✅ | — |
| % nivel 1-2 | 85.1% | TBD | — | ≥ 65% ✅ | — |
| MAE tormentas | 1.667 | TBD | — | ≤ 1.00 ❌ | — |
| F1-macro | — | TBD | — | — | — |
| Accuracy exacta | — | TBD | — | — | — |
| Accuracy ±1 | — | TBD | — | — | — |

### Distribución de predicciones

| Nivel | Snowlab GT | AndesAI v8.0 | **AndesAI v15.0** |
|-------|------------|--------------|-------------------|
| 1 | TBD | TBD | TBD |
| 2 | TBD | TBD | TBD |
| 3 | TBD | TBD | TBD |
| 4 | TBD | TBD | TBD |
| 5 | TBD | TBD | TBD |

### Desglose por sector

| Sector | QWK | MAE | Sesgo | n |
|--------|-----|-----|-------|---|
| La Parva Sector Alto | TBD | TBD | TBD | 30 |
| La Parva Sector Medio | TBD | TBD | TBD | 30 |
| La Parva Sector Bajo | TBD | TBD | TBD | 30 |

### Desglose temporal

| Temporada | QWK | MAE | Sesgo | n |
|-----------|-----|-----|-------|---|
| 2024 (jun–sep) | TBD | TBD | TBD | 45 |
| 2025 (jun–sep) | TBD | TBD | TBD | 45 |

---

## Resultados H1/H3 — Swiss SLF (heredados de v9.0)

No se reprocesó Suiza en esta ronda — los fixes v10.x (ERA5 Alpes) y v13.0 (CA-WINDOW) fueron validados internamente con análisis de casos sin reproceso completo. La próxima ronda Suiza debe incluir el backfill IMIS 2018-2020.

| Métrica | v9.0 R9 | v15.0 (heredado) | Objetivo |
|---------|---------|-----------------|---------|
| QWK H3 | +0.049 | +0.049 | ≥ 0.59 |
| F1-macro H1 | 0.288 | 0.288 | ≥ 0.75 |

---

## Análisis WN2 shadow (producción)

WeatherNext 2 está activo en producción (`USE_WEATHERNEXT2=true`) desde 2026-05-15. Para el reproceso histórico (fechas 2024-2025) la tool retorna `disponible=False` — no hay datos WN2 para esas fechas en `weathernext_2_0_0`.

El análisis de impacto real de WN2 se realizará con datos de producción:

```sql
SELECT
  DATE(fecha_emision) AS fecha,
  nombre_ubicacion,
  wn2_avalanche_problem,
  wn2_confianza,
  nivel_eaws_24h
FROM `climas-chileno.clima.boletines_riesgo`
WHERE STARTS_WITH(version_prompts, 'v15')
  AND wn2_avalanche_problem IS NOT NULL
ORDER BY fecha DESC
LIMIT 20
```

Objetivo shadow (7 días): `wn2_avalanche_problem IS NOT NULL` en ≥ 90% de los runs La Parva.

---

## Resumen consolidado de versiones (actualizado R10)

| Ronda | Versión | QWK H3 | QWK H4 | MAE H4 | Sesgo H4 |
|-------|---------|--------|--------|--------|----------|
| R3 | v4.0 | +0.162 | −0.006 | 2.138 | +2.023 |
| R4 | v5.0 | +0.143 | −0.000 | 1.724 | +1.609 |
| R5 | v6.2 | −0.031 | −0.031 | 1.230 | +0.885 |
| R7 | v7.5 | +0.103 | −0.139 | 1.448 | +1.011 |
| R8 | v8.0 | −0.073 | +0.028 | 0.828 | +0.299 |
| R9 | v9.0 | +0.049 | =(v8.0) | =(v8.0) | =(v8.0) |
| **R10** | **v15.0** | **(her. v9.0)** | **TBD** | **TBD** | **TBD** |

---

## Ejecución del reproceso

```
Inicio   : 2026-05-15 23:46 UTC
Estado   : En ejecución (background)
Progreso : ver logs reprocesar_retroactivo.py --solo-snowlab
Comando validación (post-reproceso):
  python notebooks_validacion/08_validacion_snowlab.py --version v15 --verbose
```
