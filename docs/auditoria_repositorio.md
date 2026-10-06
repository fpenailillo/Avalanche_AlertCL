# Auditoría del repositorio — versión final

**Fecha:** 2026-10-06 · **Rama auditada:** `main` @ `0b86d48`

> **Estado:** auditoría completada y **Fases 1 a 3 ejecutadas** (ver §5). Las secciones 2
> y 3 describen el diagnóstico original; donde una recomendación ya se aplicó, está
> marcada como **Ejecutado**. Quedan abiertas la Fase 0 (§3.4.b), la Fase 4 y las dos
> decisiones manuales señaladas en §2.1.b y §2.3.

| Antes | Después |
|---|---|
| 340 archivos versionados | **327** |
| 248 MB en disco · `.git` 38 MB | **232 MB** · `.git` **23 MB** |
| 3 ramas (`main`, `develop`, `feat/*`) | **1** (`main`) |
| 641 tests | **634** (se retiró `test_tools.py`, que probaba código muerto) |

Este informe responde a dos preguntas: **qué sobra** en el repositorio y **qué falta**
para que la versión final sea reproducible y citable. Cada afirmación va acompañada del
comando que la produce, para que puedas reverificarla en cualquier momento.

---

## 1. Inventario

| Área | Archivos versionados | Propósito |
|---|---:|---|
| `agentes/` | 164 | Motor multi-agente: orquestador, 5 subagentes, despliegue, tests |
| `datos/` | 60 | Capa de ingesta: Cloud Functions, monitor satelital, QC, relatos |
| `docs/` | 44 | Documentación metodológica, papers, informes de validación |
| `frontend/` | 40 | Interfaz React + Vite + Tailwind (GitHub Pages) |
| `notebooks_validacion/` | 26 | Entorno de validación académica (H1/H3/H4) |
| Raíz | 5 | `README.md`, `.gitignore`, `.gcloudignore`, `.env.example`, `gcp_cors.json` |
| `.github/` | 1 | Workflow de despliegue del frontend |
| **Total** | **340** | 380 commits · 200 archivos `.py` · 32 archivos de test |

```bash
git ls-files | wc -l                                    # 340
git ls-files | awk -F/ '{print (NF==1)?"(raiz)":$1}' | sort | uniq -c
git rev-list --count HEAD                               # 380
```

**El repositorio no está inflado en git, sino en disco.** Ocupa 248 MB, de los cuales
~170 MB son artefactos ignorados y regenerables (ver §2.5). El contenido versionado
comprimido son 247 KB.

---

## 2. Qué sobra

### 2.1 Código muerto confirmado

**`agentes/tools/`** — cuatro módulos de la arquitectura anterior a los subagentes
(fecha original 2026-03-17):

- `tool_eaws.py`
- `tool_meteorologico.py`
- `tool_satelital.py`
- `tool_topografico.py`

Ningún componente del pipeline los importa. El **único** consumidor en todo el repositorio
es `agentes/tests/test_tools.py`, es decir, su propio test. Su función vive hoy en
`agentes/subagentes/*/tools/`.

```bash
grep -rn "agentes.tools" --include=*.py . | grep -v "^./agentes/tools/"
# → solo agentes/tests/test_tools.py (líneas 18-21)
```

Detalle adicional: `agentes/tools/tool_eaws.py:18` inyecta un `sys.path.insert` hacia
`datos/analizador_avalanchas` para poder importar `eaws_constantes`. El equivalente
vigente, `agentes/subagentes/subagente_integrador/tools/tool_clasificar_eaws.py:13-14`,
hace exactamente lo mismo: también manipula `sys.path` antes de importar. Eliminar el
módulo muerto no elimina el patrón, solo quita una copia más. La causa de fondo es que el
paquete no está declarado (ver §3.1): sin `pyproject.toml`, cada módulo que cruza la
frontera `agentes/` ↔ `datos/` tiene que parchear `sys.path` a mano.

> Los tests pasan (`7 passed, 1 skipped`), pero verifican código que nadie ejecuta.
> Eliminar los cuatro módulos obliga a eliminar también `agentes/tests/test_tools.py`.

**`datos/analizador_avalanchas/analisis_pendientes.py`** — cero referencias en todo el
repositorio, en ningún formato.

```bash
grep -rn "analisis_pendientes" --include=*.py --include=*.md --include=*.yaml .
# → sin resultados
```

### 2.1.b Pendiente de decisión: `agentes/subagentes/subagente_nlp/`

`docs/revision_metodologica.md:96` ya señalaba que este subagente fue *«reemplazado por
S4 Situational Briefing»*. La verificación lo confirma a medias, por eso **no se tocó** en
esta limpieza:

- El orquestador conserva el **nombre** del atributo pero instancia otra clase:
  `agentes/orquestador/agente_principal.py:80` → `self.subagente_nlp = AgenteSituationalBriefing()`.
  La clase `SubagenteNLP` de `subagente_nlp/agente.py` no se instancia en producción.
- Pero `subagente_nlp/conocimiento_base_andino.py` **sí está vivo**: lo importan
  `notebooks_validacion/n06_analisis_nlp_sintetico.py` (7 veces) y
  `subagente_nlp/tools/tool_conocimiento_historico.py`.
- `agentes/prompts/registro_versiones.py:69` sigue registrando el hash de
  `agentes.subagentes.subagente_nlp.prompts`.

Es decir, el paquete está medio muerto: la capa de agente sobra, la base de conocimiento
andino no. Separarlas es refactor, no limpieza, y afecta al registro de versiones de
prompts — que es trazabilidad de tesis. **Queda a tu criterio.**

### 2.2 Scripts de un solo uso ya ejecutados

Migraciones de esquema y demos que cumplieron su función. Se dividen en dos grupos según
si la tesis los cita o no:

**Sin ninguna cita — eliminables sin consecuencias:**

| Script | Citas |
|---|---:|
| `agentes/scripts/migrar_schema_boletines_v25_19.py` | 0 |
| `agentes/scripts/backfill_problema_eaws.py` | 0 |
| `agentes/scripts/backfill_series_wn2_frontend.py` | 0 |
| `datos/analizador_avalanchas/regenerar_imagenes_gcs.py` | 0 |

**Citados por nombre en la documentación — mover a `agentes/scripts/historico/`, no borrar:**

| Script | Citado en |
|---|---|
| `migrar_schema_boletines_v7.py` | `docs/revision_metodologica.md`, `docs/validacion/ronda6_v70_resultados.md` |
| `demo_v24_ajuste_tormenta.py` | `docs/revision_metodologica.md`, `docs/validacion/ronda18_v25_resultados.md`, `docs/validacion/validacion_caro2026_andesai.md` |
| `demo_fix_sat_storm.py` | `docs/revision_metodologica.md` |
| `datos/ingestores/explorar_caro_2026.py` | `docs/datasets/caro_2026.md` |

Borrar estos cuatro rompería la trazabilidad de la tesis: los informes de validación
remiten a ellos como el procedimiento que generó un resultado concreto.

`datos/migrar_gcs.py` no aparece citado en documentación, pero sí dejó
`datos/migrar_gcs_progreso.log` como rastro de ejecución.

### 2.3 Duplicados y residuos versionados

- **`docs/validacion/baseline_v32_ronda2.json`** y
  **`notebooks_validacion/baseline_v32_ronda2.json`**: copia exacta, **idéntico hash git**.
  Conservar una y referenciarla desde la otra ubicación.

- **`RESULTADOS_VALIDACION.md` existe dos veces con contenido distinto**:
  `docs/validacion/` (167 líneas) y `notebooks_validacion/` (223 líneas). Mismo nombre,
  distinto contenido, ninguna nota que indique cuál manda. **Esta ambigüedad hay que
  resolverla a mano**: no es seguro deducir cuál es el canónico desde el código.

- **`notebooks_validacion/data/external/caro_2026/sd_clean.csv`**: archivo de **0 bytes**
  versionado. Es el mismo blob vacío que los `__init__.py`.

```bash
git ls-files -s | awk '{print $2, $4}' | sort   # agrupar por hash → revela los duplicados exactos
```

### 2.4 Archivos sin versionar en `docs/`

```
docs/informe_final_andesai (4).docx      56 KB   ← decidir: versionar o ignorar
docs/plantilla_final-2026 (1).docx      373 KB   ← decidir: versionar o ignorar
docs/~$forme_final_andesai (4).docx     162 B    ← basura: archivo de bloqueo de Word
```

El tercero es un lock temporal que Word deja al abrir un documento. Siempre es
desechable y `.gitignore` no lo cubre (ver §2.6).

### 2.5 Artefactos locales — ~170 MB recuperables

Todos están correctamente ignorados por git; ocupan disco, no historia.

| Ruta | Peso | Regenerable con |
|---|---:|---|
| `frontend/node_modules/` | 147 MB | `npm ci` |
| `logs_validacion/` (33 archivos) | 14 MB | — (son evidencia de corridas pasadas) |
| `agentes/validacion/modelo_h3_rf_train2016.joblib` | 5,3 MB | `modelo_h3_supervisado.py --guardar` |
| `__pycache__/` (35 directorios) | 3,1 MB | automático |
| `claude/` (incluye 2 tarballs) | 368 KB | — |
| `.DS_Store` (16 archivos) | 152 KB | — |
| `.pytest_cache/` | 88 KB | automático |
| `.coverage` | 52 KB | automático |

**Objetos git sueltos:** 3108 objetos ocupando **37 MB**, frente a 247 KB ya empaquetados.

```bash
git count-objects -vH
# count: 3108 / size: 37.00 MiB / size-pack: 247.03 KiB
```

**Ejecutado.** `git gc` empaquetó los 3108 objetos sueltos: `.git` pasó de 38 MB a 23 MB
y el árbol completo de 248 MB a 232 MB, sin reescribir la historia y sin afectar clones,
GitHub Pages ni los despliegues de Cloud Run. La recuperación real fue de ~15 MB en
`.git` más ~3 MB de cachés, no los ~37 MB que sugería la cifra de objetos sueltos: buena
parte de esos 37 MB eran historia alcanzable que al empaquetarse quedó en 22 MB de pack.
Ese pack es el peso real de los PDF y CSV que decidiste conservar.

### 2.6 Defecto en `.gitignore`

La regla de la línea 44 no hace lo que aparenta:

```gitignore
data/external/
```

Un patrón que contiene `/` en medio queda **anclado a la raíz del repositorio**. Por lo
tanto solo cubriría `/data/external/`, que no existe. El directorio real,
`notebooks_validacion/data/external/`, **no está ignorado**:

```bash
git check-ignore -q "notebooks_validacion/data/external/x.csv" && echo IGNORADO || echo "no ignorado"
# → no ignorado
```

Esto explica que `Southern_Andes_Snow_Depth_Dataset_v4.2.csv` (884 KB) y el
`sd_clean.csv` vacío estén versionados. La corrección es `**/data/external/`.

Faltan además dos patrones: `~$*` (locks de Word) y, si decides no versionar los informes,
`*.docx`.

### 2.7 Ramas

| Rama | Commits propios | Estado |
|---|---:|---|
| `main` | — | Rama viva, al día con `origin/main` |
| `develop` | **0** | Totalmente fusionada en `main`; no aporta nada |
| `feat/mejoras-h1h3h4-datadriven` | 1 (`39d610e`) | 56 commits por detrás de `main` |

```bash
git rev-list --count main..develop                       # 0
git rev-list --count main..feat/mejoras-h1h3h4-datadriven # 1
```

El único commit propio de `feat/*` es *«FEAT(frontend): agregar contador de visitas al
footer»*. **Decisión tomada: se descarta.**

Comandos para ejecutarlo cuando quieras (`-D` en lugar de `-d` para `feat/*`, porque su
commit no está fusionado):

```bash
git branch -d develop
git branch -D feat/mejoras-h1h3h4-datadriven
git push origin --delete develop
git push origin --delete feat/mejoras-h1h3h4-datadriven
```

---

## 3. Qué falta

Vacíos que importan específicamente porque esta es la versión final de un trabajo
académico público.

### 3.1 El paquete Python no está declarado

No existe `pyproject.toml`, `setup.py`, `pytest.ini`, `setup.cfg` ni `conftest.py`.
Consecuencia concreta: los tests solo funcionan si se invocan desde la raíz del
repositorio, porque las importaciones `from agentes...` dependen del directorio de
trabajo. Quien clone el repositorio no tiene forma declarada de instalarlo.

### 3.2 Las dependencias de desarrollo no están en ninguna parte

`pytest` no aparece en ningún `requirements.txt`. Tampoco las dependencias de
`notebooks_validacion/` (scikit-learn para el RF de H3, pandas, matplotlib). Los 10
`requirements.txt` que existen son todos de despliegue, uno por Cloud Function:

```
agentes/despliegue/              datos/monitor_satelital/
datos/analizador_avalanchas/     datos/procesador/
datos/extractor/                 datos/procesador_dias/
datos/extractor_historico/       datos/procesador_horas/
datos/mapa_gee/                  datos/receptor_observaciones/
```

No comparten una base común de versiones, así que nada garantiza que `google-cloud-bigquery`
sea la misma versión en todos los servicios.

### 3.3 Sin licencia ni forma de citar

No hay `LICENSE` ni `CITATION.cff`. El repositorio es público y acompaña una tesis: sin
licencia explícita, nadie puede reutilizar el código legalmente, y sin `CITATION.cff` no
hay forma canónica de citarlo. Para un trabajo cuyo propósito declarado es «democratizar
el acceso a la seguridad invernal», es una omisión que contradice el objetivo.

### 3.4 La suite de tests no es ejecutable de forma rutinaria

Suite completa ejecutada en esta auditoría:

```
14 failed, 617 passed, 12 skipped in 1112.66s (0:18:32)
```

**18 min 32 s de reloj para 643 resultados, con solo ~33 s de CPU.** El tiempo no se va en
cómputo sino en espera de red: varios tests alcanzan BigQuery en vivo. Como contraste,
`test_tools.py` y `test_sistema_completo.py` juntos (8 tests, sin BigQuery) tardan 15,5 s.

No existen marcadores (`@pytest.mark.integration`, `@pytest.mark.slow`) que permitan
correr solo los unitarios. Y el único workflow de CI, `.github/workflows/deploy.yml`,
compila y publica el frontend: **los tests de Python nunca se ejecutan en CI**. Una
regresión en la capa de agentes no se detecta hasta que alguien corre la suite a mano y
espera 18 minutos — lo que explica que haya 14 tests en rojo sin que nadie lo notara.

Los 14 fallos se concentran en tres archivos:

| Archivo | Fallos | Área |
|---|---:|---|
| `test_fix_pinn_wn2.py` | 6 | Fallback determinista WN2 en el cálculo PINN |
| `test_fix_h.py` | 5 | Estabilidad dominante sin datos satelitales |
| `test_fix_cr10.py` | 3 | Ventanas críticas con precipitación 72 h |

Ninguno es intermitente: reproducidos individualmente fallan igual, en ~7 s cada uno.


### 3.4.b Dos correcciones en conflicto sobre el error dominante de H4

**Este es el hallazgo de mayor valor del informe y conviene resolverlo antes de cerrar la
tesis.** No es un problema de orden del repositorio: toca el resultado central de H4.

El test `test_fix_h.py::TestFixH::test_andes_good_sin_datos_no_eleva` falla así:

```
AssertionError: assert 'fair' == 'good'
```

Su docstring dice literalmente: *«FIX-SAT-DEFAULT-NO-ELEVA: Andes con PINN ESTABLE (good)
y satélite ausente debe quedar 'good' (no 'fair'). Es la causa raíz del error GT=1→AI=2
en H4.»* Es decir, el test vigila exactamente el modo de error dominante de la validación
(31 de 60 casos).

La corrección sigue estando en el código, en
`agentes/subagentes/subagente_integrador/tools/tool_clasificar_eaws.py:826`: si
`estabilidad_satelital` no está en la escala y la región es `andes_chile`, entonces
`idx_base = idx_topo`, sin elevar.

El problema es lo que ocurre **antes**. En las líneas 788-815, una corrección posterior
—`FIX-SAT-EAWS-MAP`, del commit `04e3845` *«hacer determinista estabilidad satelital»*—
consulta BigQuery y **reescribe `estabilidad_satelital`** a partir de NDSI y cobertura de
nieve:

```python
estabilidad_satelital = _estab_sat_determinista   # línea 813
```

Cuando esa consulta devuelve datos, `estabilidad_satelital` deja de ser `None`, la
condición `estabilidad_satelital in escala` pasa a ser verdadera y **la rama de
FIX-SAT-DEFAULT-NO-ELEVA nunca se ejecuta**. Vuelve a aplicarse `max(idx_topo, idx_sat)`,
que es justo el `max(good, fair) = fair` que la corrección existía para evitar.

Dicho de otro modo: con datos satelitales disponibles, el camino que inflaba ~21 días
calmos de nivel 1 a nivel 2 vuelve a estar activo.

**Lo que esta auditoría no puede determinar** es cuál de las dos lecturas es la correcta:

1. `FIX-SAT-EAWS-MAP` reemplazó deliberadamente a `FIX-SAT-DEFAULT-NO-ELEVA` —en cuyo
   caso el test está obsoleto y hay que actualizarlo o retirarlo—, o
2. las dos correcciones se pisan sin que nadie lo advirtiera —en cuyo caso el error
   dominante de H4 puede estar reapareciendo en producción.

Decidir entre ambas exige conocer la intención con que se introdujo `04e3845`, y eso no
está escrito en el repositorio. **Es una decisión tuya, no una limpieza.**

Nota metodológica: el test tampoco es hermético. Aunque no declara ningún mock de
BigQuery, alcanza la base de datos indirectamente a través de `FIX-SAT-EAWS-MAP`, así que
su resultado depende de qué datos satelitales haya ese día. Un test que vigila el
resultado central de la tesis no debería depender del estado de una tabla externa.

### 3.5 El README no describe la arquitectura que está en producción

`README.md` documenta la capa de Cloud Functions con un diagrama Mermaid, pero **no
menciona ni una sola vez los Cloud Run Jobs que hoy sostienen el sistema**:

```bash
grep -c "Cloud Run" README.md   # → 0
```

Los cuatro jobs ausentes del README:

| Job | Qué hace | Definido en |
|---|---|---|
| `orquestador-avalanchas` | Genera los boletines (entrypoint del `Dockerfile`) | `cloudbuild.yaml` |
| `ingestor-wn2` | Ingesta de WeatherNext 2 | `cloudbuild.yaml` |
| `exportar-series-horas` | Series horarias para el frontend | `cloudbuild.yaml` |
| `exportar-boletin-activo` | Publicación desacoplada de `boletin_activo.json` | **`setup_scheduler_boletin.sh`** |

Alguien que lea el README para entender el sistema se formará un modelo incorrecto de
cómo funciona.

### 3.5.b El cuarto job queda fuera de la infraestructura declarativa

`cloudbuild.yaml` crea o actualiza tres jobs de forma declarativa: cada
`gcloud builds submit` los reaplica. El cuarto, `exportar-boletin-activo` (con su
scheduler `publicar-boletin-activo` a las 10:30 UTC), solo existe si alguien ejecutó a
mano `agentes/despliegue/setup_scheduler_boletin.sh`.

```bash
grep -oE "jobs (describe|create) [a-z-]+" agentes/despliegue/cloudbuild.yaml | awk '{print $3}' | sort -u
# → exportar-series-horas, ingestor-wn2, orquestador-avalanchas   (falta el cuarto)
```

Ese job es precisamente el que evita que el frontend se congele cuando el orquestador
excede su `task-timeout`. Que su definición viva en un script manual y no en el pipeline
significa que recrear el entorno desde cero deja el sistema con un fallo latente que solo
se manifiesta el día que una corrida se pasa de tiempo. **Recomendación:** mover ese
bloque a `cloudbuild.yaml` como paso 6, igual que los otros tres.

### 3.6 Sin `CLAUDE.md` en la raíz

El que existe está en `claude/CLAUDE.md`, dentro de un directorio ignorado por git, así
que no acompaña al repositorio.

---

## 4. Decisiones registradas

| Tema | Decisión |
|---|---|
| Alcance de esta pasada | Solo auditoría; no se modificó ningún archivo del repositorio |
| PDFs de `docs/papers-relevantes/` (~18 MB) | **Mantener todos** — respaldo metodológico de la tesis |
| Los 14 informes de ronda en `docs/validacion/` | **Archivar** en `docs/validacion/historico/` |
| Ramas `develop` y `feat/mejoras-h1h3h4-datadriven` | **Borrar ambas** (local y origin); se descarta `39d610e` |

Sobre el archivado: `docs/validacion/` contiene 26 archivos. 14 son informes
`rondaN_vXX_resultados.md` (rondas 5 a 18) y 11 son documentos vigentes
(`RESULTADOS_VALIDACION.md`, análisis H3/H4, EDA, calidad de datos suizos). Mover las
rondas a `historico/` deja visible de un vistazo qué documento sigue siendo válido.

---

## 5. Plan de ejecución por fases

Ordenado de menor a mayor riesgo. Ninguna fase se ha ejecutado.

### Fase 0 — PENDIENTE: resolver §3.4.b

Decidir si `FIX-SAT-EAWS-MAP` deroga o contradice a `FIX-SAT-DEFAULT-NO-ELEVA`, y dejar
la conclusión escrita en el código. Si resulta que se pisan, los números de H4 del informe
de validación habría que recalcularlos. Nada de lo demás es urgente comparado con esto.

### Fase 1 — Sin riesgo (solo disco, nada versionado cambia) ✅ EJECUTADA

```bash
git gc --prune=now --aggressive          # recupera ~37 MB
find . -name __pycache__ -type d -not -path './frontend/*' -exec rm -rf {} +
find . -name .DS_Store -not -path './.git/*' -delete
rm -rf .pytest_cache .coverage
rm "docs/~\$forme_final_andesai (4).docx"
```

*Verificación:* `git status` no debe mostrar ningún cambio en archivos versionados.

### Fase 2 — Bajo riesgo ✅ EJECUTADA

```bash
# Ramas
git branch -d develop && git branch -D feat/mejoras-h1h3h4-datadriven
git push origin --delete develop
git push origin --delete feat/mejoras-h1h3h4-datadriven

# Archivar informes de ronda
mkdir -p docs/validacion/historico
git mv docs/validacion/ronda*_resultados.md docs/validacion/historico/

# Residuos versionados
git rm notebooks_validacion/data/external/caro_2026/sd_clean.csv
git rm notebooks_validacion/baseline_v32_ronda2.json

# Corregir .gitignore: data/external/ → **/data/external/, añadir ~$*
```

*Verificación:* `git log --oneline -1 origin/main` sin cambios; `ls docs/validacion/` muestra
solo los 11 documentos vigentes.

### Fase 3 — Riesgo medio ✅ EJECUTADA

```bash
git rm -r agentes/tools/ agentes/tests/test_tools.py
git rm datos/analizador_avalanchas/analisis_pendientes.py
git rm agentes/scripts/migrar_schema_boletines_v25_19.py \
       agentes/scripts/backfill_problema_eaws.py \
       agentes/scripts/backfill_series_wn2_frontend.py \
       datos/analizador_avalanchas/regenerar_imagenes_gcs.py

mkdir -p agentes/scripts/historico
git mv agentes/scripts/migrar_schema_boletines_v7.py \
       agentes/scripts/demo_v24_ajuste_tormenta.py \
       agentes/scripts/demo_fix_sat_storm.py agentes/scripts/historico/
```

*Verificación:* reconstruir la imagen (`gcloud builds submit --config agentes/despliegue/cloudbuild.yaml`)
y confirmar que el job `orquestador-avalanchas` genera un boletín. El `Dockerfile` solo
copia `agentes/` y `datos/analizador_avalanchas/`, así que nada de lo eliminado afecta
a la imagen — pero conviene confirmarlo en una corrida real.

**Pendiente de decisión manual:** cuál de los dos `RESULTADOS_VALIDACION.md` es el canónico.

### Fase 4 — PENDIENTE: aditivo (cierra los vacíos de §3)

1. `pyproject.toml` con el paquete declarado, configuración de pytest y marcadores
   `integration` / `slow`; marcar los tests que tocan BigQuery.
2. `requirements-dev.txt` con `pytest` y las dependencias de `notebooks_validacion/`.
3. `LICENSE` (MIT o CC BY 4.0, según lo que exija la universidad) y `CITATION.cff`.
4. Actualizar `README.md`: añadir los cuatro Cloud Run Jobs al diagrama y al texto.
5. Mover la definición de `exportar-boletin-activo` desde `setup_scheduler_boletin.sh`
   a `cloudbuild.yaml`, para que los cuatro jobs se desplieguen por el mismo camino.
6. Workflow de CI que corra `pytest -m "not integration"` en cada push.

---

## Anexo — Comandos de reverificación

```bash
# Inventario
git ls-files | wc -l
git ls-files | awk -F/ '{print (NF==1)?"(raiz)":$1}' | sort | uniq -c | sort -rn

# Código muerto
grep -rn "agentes.tools" --include=*.py . | grep -v "^./agentes/tools/"
grep -rn "analisis_pendientes" --include=*.py --include=*.md .

# Duplicados exactos por hash
git ls-files -s | awk '{print $2, $4}' | sort

# Peso de git y de disco
git count-objects -vH
du -sh frontend/node_modules logs_validacion

# Ramas
git rev-list --count main..develop
git rev-list --count main..feat/mejoras-h1h3h4-datadriven

# Cobertura de .gitignore
git check-ignore -v "notebooks_validacion/data/external/x.csv"
```
