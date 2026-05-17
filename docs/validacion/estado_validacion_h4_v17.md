# Estado de Validación H4 — AndesAI vs Snowlab La Parva (v17.0 / Mayo 2026)

**Última actualización:** 2026-05-17
**Versión sistema:** v17.0
**Rondas completadas:** 12 (R3–R12)

---

## Resumen ejecutivo

El sistema AndesAI alcanzó QWK=+0.052 en R12/v17.0, superando por primera vez el
objetivo de concordancia ordinal (≥ +0.028, baseline v8.0). Sin embargo, el sesgo
sistemático (+0.816, AndesAI predice nivel más alto que Snowlab) requiere verificación
metodológica antes de continuar calibrando.

---

## Historial completo de rondas

| Ronda | Versión | Fix principal | QWK H4 | MAE H4 | Sesgo H4 | Diagonal |
|-------|---------|---------------|--------|--------|----------|----------|
| R3 | v4.0 | — | −0.006 | 2.138 | +2.023 | — |
| R4 | v5.0 | FIX-T/V/D | −0.000 | 1.724 | +1.609 | — |
| R5 | v6.2 | FIX-S3 | −0.031 | 1.230 | +0.885 | — |
| R7 | v7.5 | S1 sin triggers meteo | −0.139 | 1.448 | +1.011 | — |
| R8 | v8.0 | FIX-GEO/H/CR7 | **+0.028** | **0.828** | **+0.299** | — |
| R9 | v9.0 | FIX-CA-WINDOW | =(v8.0) | =(v8.0) | =(v8.0) | — |
| R10 | v15.0 | WN2 + CR-10A/B | +0.022 | 1.138 | +0.770 | 17.2% |
| R11 | v16.0 | FIX-CR16A (revertido) | −0.065 | 1.391 | +1.023 | 13.8% |
| **R12** | **v17.0** | **FIX-CR17A** | **+0.052** | 1.161 | +0.816 | **20.7%** |

**Mejor punto histórico H4:** v8.0 (MAE 0.828, Sesgo +0.299)
**Mejor QWK hasta la fecha:** v17.0 (+0.052)

---

## Métricas detalladas v17.0 (estado actual)

| Métrica | Valor v17.0 | Objetivo | Estado |
|---------|-------------|---------|--------|
| QWK (Kappa cuadrático ponderado) | +0.052 | ≥ +0.028 | ✅ |
| MAE | 1.161 | ≤ 0.828 | ❌ |
| Sesgo medio (EAWS − Snowlab) | +0.816 | ≤ +0.60 | ❌ |
| MAE tormentas (Snowlab ≥ 3) | 1.333 | ≤ 1.00 | ❌ |
| F1-macro | 0.123 | — | — |
| Accuracy exacta | 20.7% | — | — |
| n pares válidos | 87 | — | — |

### Matriz de confusión v17.0 (87 pares)

```
         AI=1  AI=2  AI=3  AI=4  AI=5
SL=1  →     8    33    15     4     0   (60 casos — 69.0%)
SL=2  →     1     8     4     1     1   (15 casos — 17.2%)
SL=3  →     0     5     2     0     1   ( 8 casos —  9.2%)
SL=4  →     1     2     0     0     0   ( 3 casos —  3.5%)
SL=5  →     0     0     1     0     0   ( 1 caso  —  1.1%)
```

### Distribución de predicciones

| Nivel | Snowlab GT | AndesAI v17.0 |
|-------|------------|---------------|
| 1 | 60 (69.0%) | 10 (11.5%) |
| 2 | 15 (17.2%) | 48 (55.2%) |
| 3 | 8 ( 9.2%) | 22 (25.3%) |
| 4 | 3 ( 3.5%) | 5 ( 5.7%) |
| 5 | 1 ( 1.1%) | 2 ( 2.3%) |

### Por sector

| Sector | QWK | MAE | Sesgo | n |
|--------|-----|-----|-------|---|
| La Parva Sector Alto | +0.052 | 1.23 | +0.70 | 30 |
| La Parva Sector Bajo | +0.037 | 0.93 | +0.87 | 30 |
| La Parva Sector Medio | +0.009 | 1.33 | +0.89 | 27 |

---

## Patrón dominante: sesgo sistemático positivo

**69% del dataset (60/87 pares) tiene Snowlab=1.** De esos 60 casos:
- 8 predichos correctamente como nivel 1 (13%)
- 33 predichos como nivel 2 (55%)
- 15 predichos como nivel 3 (25%)

La mayor parte del sesgo viene de **SL=1 → AI=2** (33 casos). Esto corresponde
principalmente a semanas de julio/agosto sin eventos de precipitación, donde Snowlab
asigna nivel 1 (Débil) y AndesAI asigna nivel 2 (Limitado).

---

## Preguntas metodológicas para verificar con equipo Snowlab

Antes de continuar calibrando, es importante confirmar si el sesgo observado refleja
una diferencia real del sistema o un desajuste metodológico entre AndesAI y Snowlab.

### 1. Definición de nivel para La Parva

**Pregunta:** ¿El nivel reportado en los boletines Snowlab para La Parva (campos
`nivel_alta`, `nivel_media`, `nivel_baja`) corresponde al nivel EAWS oficial publicado
en superficie, o es una estimación interna del equipo?

**Relevancia:** Si el nivel Snowlab incluye riesgo de terreno inherente (pendiente >35°,
desnivel >600m) sin evento meteo activo, el nivel 1 para condiciones calmas podría
reflejar "sin problema activo en manto plano", mientras AndesAI incluye el terreno en
la evaluación → sesgo estructural irreducible.

### 2. Período de referencia temporal

**Pregunta:** El campo `fecha_inicio` / `fecha_fin` de los boletines Snowlab cubre
2-3 días. ¿El nivel reportado es el nivel mínimo, máximo o promedio del período?

**Relevancia:** AndesAI usa ERA5 a 12:00 UTC del primer día del período. Si Snowlab
reporta el nivel mínimo y el evento principal ocurrió en los días posteriores, el
emparejamiento subvalora la predicción de AndesAI (o viceversa).

**Ejemplo concreto:** Boletin 2024-06-15 → Snowlab=5 (muy alto), AndesAI=3 (Sector Alto).
Si el nivel 5 fue del día 2024-06-16 y ERA5 del 15 no captura el evento completo,
el error (−2) no refleja falla del modelo.

### 3. Granularidad espacial

**Pregunta:** ¿Los campos `nivel_alta`, `nivel_media`, `nivel_baja` de Snowlab
corresponden exactamente a los sectores Alto, Medio, Bajo de AndesAI respectivamente?
¿O "banda alta" incluye terreno >3000m que no es el mismo que "Sector Alto"?

**Relevancia:** Si hay desalineamiento espacial, los 87 pares pueden estar comparando
predicciones de zonas distintas.

### 4. Tratamiento de días sin eventos (nivel 1 predominante)

**Pregunta:** ¿El nivel 1 de Snowlab en julio/agosto implica que el manto no tiene
carga alguna, o que el terreno familiar (nivel 1 ≤ 2500m) es seguro pero el terreno
extremo (>35°, >3000m) podría ser nivel 2?

**Relevancia:** AndesAI evalúa zonas de inicio con pendiente 35-45°. Si Snowlab
reporta el nivel para pendientes <35° (el 95% del terreno esquiable), el nivel 1
de Snowlab ≈ nivel 2 de AndesAI para terreno de inicio. El sesgo +0.816 sería
entonces un artefacto de definición de terreno, no de error de predicción.

### 5. Datos de entrada ERA5 vs datos locales Snowlab

**Pregunta:** ¿Qué fuente de datos meteorológicos usa Snowlab para asignar el nivel?
¿Estación automática in-situ, modelo numérico, o evaluación de campo directa?

**Relevancia:** AndesAI usa ERA5 (resolución 9km, interpolado a punto). Si Snowlab
usa mediciones in-situ de una estación automática en La Parva y esas mediciones
difieren sistemáticamente de ERA5 (típico en terreno de montaña), el error no es
del modelo sino de los datos de entrada.

---

## Interpretación del sesgo +0.816

### Escenario A: sesgo metodológico (AndesAI correcto)
- AndesAI evalúa terreno de inicio (35°+) donde nivel 2 es realista en condiciones calmas
- Snowlab reporta nivel para terreno general (< 35°) donde nivel 1 es correcto
- **Acción:** ajustar la comparación, no el modelo

### Escenario B: sesgo de calibración (AndesAI sobre-predice)
- AndesAI no distingue correctamente entre "terreno peligroso" y "manto peligroso"
- Snowlab captura correctamente la condición del manto con datos locales superiores
- **Acción:** continuar calibrando (FIX-CR18)

### Escenario C: mixto
- Parte del sesgo es metodológico, parte es de calibración
- **Acción:** descontar la fracción metodológica de los objetivos

---

## Configuración del test set

- **Fechas:** 30 boletines Snowlab (2024-06-15 → 2025-09-21), semanas seleccionadas
- **Sectores:** La Parva Sector Alto, Medio, Bajo
- **Pares válidos:** 87 (3 sectores × ~29 fechas; algunas fechas tienen datos parciales)
- **Balance:** 69% nivel 1 (datos de temporada media con pocas tormentas registradas)
- **Temporadas:** 2024 (julio–septiembre) + 2025 (junio–septiembre)

---

## Archivos de referencia

| Archivo | Contenido |
|---------|-----------|
| `docs/validacion/ronda12_v17_resultados.md` | Análisis detallado R12 |
| `docs/validacion/ronda11_v16_resultados.md` | Análisis R11 + diagnóstico FIX-CR16A |
| `docs/validacion/ronda10_v15_resultados.md` | Análisis R10 + diagnóstico regresión |
| `docs/validacion/ronda8_v80_resultados.md` | Mejor línea base histórica (v8.0) |
| `agentes/tests/test_fix_s1_semantica.py` | Tests unitarios S1 semántica EAWS |
| `agentes/tests/test_req05_st_regionstats.py` | Tests REQ-05 stats regionales |
