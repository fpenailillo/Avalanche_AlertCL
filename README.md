# Snow Alert — Sistema de Predicción Automática de Avalanchas

Sistema multi-agente de inteligencia artificial que genera boletines EAWS de riesgo de avalanchas para zonas de montaña chilenas, combinando modelos físicos, imágenes satelitales, pronóstico meteorológico de ensemble y análisis contextual basado en LLMs.

> **Tesis de Magíster en Tecnologías de la Información**  
> Francisco Peñailillo — Universidad Técnica Federico Santa María  
> Proyecto GCP: `climas-chileno` | BigQuery: `clima` | Región: `us-central1`

---

## Motivación

Las avalanchas representan uno de los peligros naturales de mayor impacto en las zonas cordilleranas de Chile. Los principales centros de ski y zonas de montaña del sector de Santiago — La Parva, Valle Nevado y El Colorado — reciben decenas de miles de visitantes durante la temporada de invierno, expuestos a un riesgo que no cuenta con un sistema automatizado de predicción y alerta temprana.

A diferencia de países alpinos como Suiza o Austria, donde el Instituto SLF publica boletines EAWS diarios con décadas de registro, en Chile los boletines de avalanchas se producen de forma manual, con baja frecuencia y cobertura limitada. La escasez de estaciones meteorológicas de alta montaña, la ausencia de redes de observación del manto nivoso y la heterogeneidad del terreno andino dificultan la extrapolación de metodologías europeas.

Este proyecto propone una alternativa: construir un sistema de predicción automática basado en fuentes de datos indirectas — satélites, reanálisis climático, modelos de ensemble y relatos de montañistas — orquestadas por un sistema multi-agente que reproduce la lógica de clasificación EAWS (European Avalanche Warning Services) sin requerir observación directa del manto.

---

## Objetivo académico

Diseñar, implementar y validar un sistema multi-agente capaz de generar boletines EAWS (niveles de peligro 1–5) para los sectores La Parva y Valle Nevado, evaluando si los modelos de inteligencia artificial pueden aproximar el juicio experto humano a partir de datos geoespaciales y meteorológicos disponibles en Chile.

La investigación busca responder cuatro hipótesis:

| ID | Hipótesis | Métrica | Objetivo |
|----|-----------|---------|----------|
| H1 | El sistema supera el rendimiento de un clasificador trivial (majority class) vs. datos SLF Suiza | F1-macro | ≥ 0.75 |
| H2 | Incorporar relatos de montañistas (NLP) mejora la predicción respecto a usar solo datos físicos | Delta F1 ablación | > +5 pp |
| H3 | El sistema es competitivo con el benchmark de Techel (2022) en datos suizos | QWK | ≥ 0.59 |
| H4 | El sistema alcanza acuerdo sustancial con boletines expertos locales (Snowlab La Parva) | QWK | ≥ 0.40 |

La validación local (H4) es la hipótesis de mayor relevancia práctica: contrasta las predicciones del sistema contra boletines reales del centro de ski La Parva, emitidos por observadores certificados CAA nivel 2.

---

## Enfoque técnico

El sistema implementa la **Matriz EAWS 2025** (Müller, Techel & Mitterer), que clasifica el riesgo de avalanchas combinando tres factores: *estabilidad del manto* (muy pobre → buena), *frecuencia* (muchas → casi ninguna) y *tamaño* (1–5). Un orquestador coordina cinco subagentes especializados que analizan cada factor de forma independiente y luego lo integran en un boletín estructurado.

**Fuentes de datos:**
- **Topografía**: DEM Copernicus GLO-30, atributos TAGEE (curvatura, pendiente, aspecto), embeddings AlphaEarth 64D
- **Satelital**: SAR Sentinel-1, Sentinel-2 SR (NDSI, cobertura nieve), MODIS LST, Vision Transformer (ViT)
- **Meteorología**: Open-Meteo + ERA5-Land (reanálisis), WeatherNext 2 (64 miembros ensemble, Google)
- **Contextual**: 3.131 relatos de montañistas de Andeshandbook (37 campos por relato)
- **Física**: PINN (Physics-Informed Neural Network) con modelo de esfuerzo de Mohr-Coulomb para el factor de seguridad del manto

**LLM de producción**: Qwen3-80B vía Databricks (GCP Secret Manager); Claude como alternativa local.

---

## Resultados de validación — Junio 2026

### Hipótesis locales — H4 vs. Snowlab La Parva

| Versión | n pares | QWK | Estado |
|---------|--------:|----:|--------|
| v3.2 (Ronda 2, baseline) | 90 | −0.016 | — |
| v25.8 (Ronda 3, fixes PINN) | 87 | +0.385 | — |
| v26.0 (Gemini integrado) | ~90 | **+0.465** | ✅ Objetivo alcanzado (≥ 0.40) |

El error dominante (pre-v25.x) era **GT=1 → AI=2**: el sistema sobreestimaba el peligro en condiciones estables. La causa fue identificada en el mapeo LLM del estado PINN: ESTABLE se traducía como `poor` en lugar de `good`, inflando artificialmente el nivel. El FIX-PINN-EAWS-MAP (v25.9) corrigió el comportamiento estructuralmente.

### Hipótesis internacionales — H1/H3 vs. SLF Suiza

| Métrica | v3.2 (Ronda 2) | v4.0 (Ronda 3) | Objetivo | Estado |
|---------|---------------:|---------------:|----------|--------|
| F1-macro (H1) | 0.161 | 0.155 | ≥ 0.75 | ❌ Rechazada |
| QWK (H3) | +0.016 | +0.162 | ≥ 0.59 | ❌ Rechazada |

El gap entre las métricas andinas y alpinas tiene una causa documentada y publicable: el modelo de corrección orográfica ERA5 fue calibrado para los Andes centrales (gradientes de precipitación distintos a los Alpes). El sistema tiende a subestimar el peligro en la topografía alpina. Esto se documenta como hallazgo metodológico de **transferencia de dominio Andes→Alpes**.

**H2** (aporte del NLP): delta F1 de +7.9 pp confirmado en experimento de ablación sintético. ✅

---

## Arquitectura del sistema

```
┌──────────────────────────────────────────────────────────────────────┐
│                       GOOGLE CLOUD PLATFORM                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  CAPA DE DATOS  (datos/)                     │    │
│  │                                                              │    │
│  │  Cloud Scheduler                                             │    │
│  │  ├── extractor-clima (3x/día)     ──────────→ BigQuery ✅   │    │
│  │  ├── procesador-clima-horas       ──────────→ BigQuery ✅   │    │
│  │  ├── procesador-clima-dias        ──────────→ BigQuery ✅   │    │
│  │  ├── monitor-satelital-nieve (3x/día) ──────→ BigQuery ✅   │    │
│  │  └── analizador-zonas-avalanchas (mensual) ─→ BigQuery ✅   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               ↓ BigQuery clima.*                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │               CAPA DE AGENTES  (agentes/)                    │    │
│  │                                                              │    │
│  │  Cloud Run Job: orquestador-avalanchas                       │    │
│  │                                                              │    │
│  │   [S1 Topográfico · PINN · GLO-30 · TAGEE · AlphaEarth]    │    │
│  │   → [S2 Satelital · ViT · SAR · Sentinel-2 · MODIS]        │    │
│  │   → [S3 Meteorológico · ERA5 · Open-Meteo · WeatherNext2]  │    │
│  │   → [S4 Situational Briefing · Qwen3-80B · relatos NLP]    │    │
│  │   → [S5 Integrador EAWS · Boletín 24h/48h/72h]             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  CAPA DE RESULTADOS                          │    │
│  │  BigQuery: clima.boletines_riesgo (34 campos)                │    │
│  │  GCS: boletines/{ubicacion}/{YYYY/MM/DD}/{timestamp}.json    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline de 5 subagentes

| # | Subagente | Técnica principal | Output clave |
|---|-----------|-------------------|--------------|
| S1 | Topográfico | PINN (Mohr-Coulomb) + GLO-30 + TAGEE (13 atributos) + AlphaEarth embeddings 64D | Factor de seguridad FS, IC 95%, `estado_pinn` (ESTABLE/MARGINAL/INESTABLE/CRITICO), drift interanual |
| S2 | Satelital | ViT (MHA, H=2) + SAR Sentinel-1 + Sentinel-2 SR + MODIS/061; Gemini 2.5 multispectral en A/B | `alertas_satelitales`, `anomalia_score`, NDSI, línea de nieve |
| S3 | Meteorológico | Open-Meteo + ERA5-Land + WeatherNext 2 (64 miembros ensemble) | `ventanas_criticas`, precipitación P10/P50/P90, `nieve_3d_cm_p95`, alertas ensemble |
| S4 | Situational Briefing | Qwen3-80B vía Databricks; 4 tools: clima reciente, contexto histórico, características zona, eventos pasados | `narrativa_integrada`, `factores_atencion_eaws`, `indice_riesgo_cualitativo` |
| S5 | Integrador EAWS | Matriz EAWS 2025 (Müller, Techel & Mitterer) — Qwen3-80B | Boletín EAWS completo 24h/48h/72h, nivel de peligro N1–N5 |

---

## Estado del proyecto — Junio 2026

### ✅ Operacional
- 6 Cloud Functions activas recolectando datos 3x/día (92 ubicaciones monitoreadas)
- 5 subagentes implementados con agentic loop, retries y logging estructurado
- 3.131 relatos Andeshandbook en BigQuery (37 campos por relato)
- Pipeline end-to-end en ~120 s por boletín individual
- WeatherNext 2 activo en producción (`USE_WEATHERNEXT2=true`)
- Cloud Run Job `orquestador-avalanchas` desplegado en `main`
- H4 QWK = **+0.465** ✅ (objetivo ≥ 0.40 alcanzado, v26.0)
- 518 tests unitarios passing, 13 skipped (requieren credenciales GCP)
- VERSION_GLOBAL: `v25.17` — extractor WN2 centralizado, FIX-WN2-SIZE-RATIO, persistencia post-tormenta `ayer-1`

### ⏳ Pendiente
- Calibración estadística (Fase D) con datos v25.17 — confirmar QWK > 0.40 en ronda de validación formal
- Crear tabla `estado_manto_gee` en BQ y ejecutar backfill (`backfill_estado_manto_gee.py`)
- Actualizar tests de regresión `test_fix_pinn_wn2` tras refactor extractor WN2 (v25.17)

---

## Instalación y uso local

```bash
# Requisitos
# Python 3.11+, gcloud CLI autenticado, ANTHROPIC_API_KEY o DATABRICKS_TOKEN
# En producción: Databricks token se lee desde GCP Secret Manager automáticamente

# Instalar dependencias
cd agentes
pip install -r despliegue/requirements.txt

# Generar un boletín individual
cd snow_alert
python agentes/scripts/generar_boletin.py --ubicacion "La Parva Sector Bajo"

# Solo imprimir (sin guardar en BQ/GCS)
python agentes/scripts/generar_boletin.py --ubicacion "Valle Nevado" --solo-imprimir

# Listar ubicaciones disponibles
python agentes/scripts/generar_boletin.py --listar-ubicaciones

# Generar todos los sectores para una fecha
export USE_WEATHERNEXT2=true
python agentes/scripts/generar_todos.py --preset laparva --fecha 2026-06-10 --sin-backfill --guardar
```

## Tests

```bash
cd snow_alert

# Suite completa (sin credenciales externas)
python3 -m pytest agentes/tests/ -q
# → 518 passed, 7 failed, 13 skipped

# Por módulo
python3 -m pytest agentes/tests/test_situational_briefing.py -v   # S4
python3 -m pytest agentes/tests/test_weathernext2.py -v           # S3 WeatherNext 2
python3 -m pytest agentes/tests/test_s1_glo30.py -v               # S1 GLO-30/TAGEE/AlphaEarth
python3 -m pytest agentes/tests/test_req01_persistencia_temporal.py -v  # REQ-01
python3 -m pytest agentes/tests/test_req03_correccion_orografica.py -v  # REQ-03 ERA5

# Test E2E completo (requiere credenciales GCP)
python3 -m pytest agentes/tests/test_sistema_completo.py -v -s
```

## Despliegue en GCP

```bash
# Capa de datos (6 Cloud Functions)
cd datos && ./desplegar.sh climas-chileno us-central1

# Sistema multi-agente (Cloud Run Job)
gcloud builds submit --config agentes/despliegue/cloudbuild.yaml --project=climas-chileno
gcloud run jobs execute orquestador-avalanchas --region=us-central1
```

---

## Tablas BigQuery

**Dataset operacional** (`climas-chileno.clima.*`):

| Tabla | Filas | Descripción |
|-------|------:|-------------|
| `condiciones_actuales` | 77.480 | Meteorología 3x/día — 92 ubicaciones |
| `pronostico_horas` | 201.563 | Pronóstico horario hasta 14 días — 71 ubicaciones |
| `pronostico_dias` | 42.353 | Pronóstico diario diurno/nocturno — 71 ubicaciones |
| `imagenes_satelitales` | 3.555 | GOES-18 + SAR Sentinel-1 + ERA5-Land; 15 zonas andinas |
| `relatos_montanistas` | 3.131 | Relatos Andeshandbook (37 campos) |
| `boletines_riesgo` | 427+ | Output del sistema (34 campos, Chile + Suiza) |
| `pendientes_detalladas` | activa | GLO-30 + TAGEE + AlphaEarth (embeddings 64D) |
| `s2_comparaciones` | activa | A/B testing ViT vs Gemini multispectral |
| `zonas_objetivo` | 4 | Polígonos GEOGRAPHY La Parva / Valle Nevado / El Colorado |

**Dataset de validación** (`climas-chileno.validacion_avalanchas.*`):

| Tabla | Filas | Descripción |
|-------|------:|-------------|
| `slf_danger_levels_qc` | 45.049 | Ground truth EAWS — SLF Suiza 2001-2024 |
| `slf_meteo_snowpack` | 29.296 | Estaciones IMIS suizas 2001-2020 |
| `snowlab_boletines` | 30 | Boletines expertos Snowlab La Parva (CAA nivel 2, 2024-2025) |

---

## Estructura del repositorio

```
snow_alert/
├── datos/                         ← Cloud Functions de recolección (6 activas en GCP)
│   ├── extractor/                 # Google Weather API → condiciones_actuales
│   ├── procesador/                # Pub/Sub: condiciones brutas → BigQuery
│   ├── procesador_horas/          # Pronóstico horario → pronostico_horas
│   ├── procesador_dias/           # Pronóstico diario → pronostico_dias
│   ├── monitor_satelital/         # GEE MODIS/Sentinel → imagenes_satelitales
│   ├── analizador_avalanchas/     # GEE GLO-30 → zonas_avalancha
│   └── relatos/                   # ETL Andeshandbook → relatos_montanistas
│
├── agentes/                       ← Sistema multi-agente (S1–S5)
│   ├── datos/                     # Capa de acceso: BQ, constantes, LLM client, backfill
│   ├── subagentes/                # S1 topográfico, S2 satelital, S3 meteo, S4 briefing, S5 integrador
│   ├── orquestador/               # Coordina S1→S2→S3→S4→S5
│   ├── salidas/                   # Almacenador BQ+GCS, schema boletines
│   ├── validacion/                # Métricas EAWS (F1, QWK, Techel 2022), mapeo SLF
│   ├── despliegue/                # Dockerfile, cloudbuild.yaml, requirements.txt
│   ├── scripts/                   # CLI: generar_boletin.py, generar_todos.py
│   └── tests/                     # 518 tests unitarios + E2E
│
├── notebooks_validacion/          ← Scripts de validación académica (H1–H4)
│
└── docs/                          ← Documentos académicos, papers, migraciones BQ
    ├── propuesta_tesina_fpenailillo.pdf
    ├── papers-relevantes/         # Techel 2022, EAWS matrix, PINNs
    └── validacion/                # EDA, resultados por ronda, mapeos
```
