# Problemas típicos de avalancha (EAWS) en el sistema

Referencia de los cinco problemas típicos EAWS y de cómo los detecta el sistema.
Fuente normativa: *EAWS — Typical avalanche problems* (avalanches.org, versión en
español, 2022). Implementación:
`agentes/subagentes/subagente_integrador/tools/tool_clasificar_problema_eaws.py`.

## Por qué existe este documento

El skill `eaws-methodology` cubre los tres factores de la matriz (estabilidad,
frecuencia, tamaño) y el nivel de peligro, pero no los problemas típicos. Y hasta
la v25.19 el sistema no tenía clasificación propia: `tipo_problema_eaws` nunca se
poblaba y el boletín publicaba `wn2_avalanche_problem`, decidido por un `CASE`
sobre la temperatura del aire del ensemble a la altitud de referencia de la zona.

El caso que lo dejó en evidencia: **La Parva / Farellones, sábado 25-jul-2026**.
Llovió con cota de nieve alta (~3.000 m) y el boletín publicó `new_snow` en los
tres sectores. El dato de lluvia estaba en `pronostico_horas.tipo_precipitacion`
desde la ingesta —`RAIN_AND_SNOW` y `LIGHT_RAIN` en el Sector Bajo desde la
01:00— pero ninguna tool lo leía.

## Los cinco problemas y su detección

### 1. Nieve reciente (*new snow*)

Nieve caída recientemente que aún no se ha estabilizado. Depende de la cantidad,
la intensidad de la nevada y la temperatura durante la precipitación.

**Detección:** `heavy_snow` del ensemble WN2 o nieve nueva ≥ 10 cm/24 h; en su
defecto, ≥ 3 h de nieve observada con acumulación. **Sustento: sólido.**

### 2. Nieve venteada (*wind-drifted snow*)

Nieve transportada por el viento que forma placas en laderas a sotavento,
depresiones y detrás de rupturas de pendiente. Es el problema más frecuente en
los Andes centrales.

**Detección:** alerta `storm_slab` del ensemble, o viento a 100 m ≥ 8 m/s con
nieve disponible para transporte. Se cruza con `exposicion_predominante` de la
zona (`METADATA_ZONAS`) para nombrar las laderas a sotavento.
**Sustento: sólido.**

### 3. Capa débil persistente (*persistent weak layer*)

Capa frágil dentro del manto —escarcha de profundidad, cristales facetados,
escarcha superficial enterrada— que puede sobrevivir semanas y romper con
propagación lejos del punto de sobrecarga.

**Detección:** proxy del ensemble (amplitud térmica > 3 °C con baja probabilidad
de nieve). **Sustento: débil.** Los índices IMIS (`snowpack_features.py`, campos
`pwl_100`, `ssi_pwl`, `sk38_pwl`) solo existen para los Alpes suizos: en los
Andes no hay observación del perfil del manto. Por eso este problema **nunca se
emite como dominante si compite con una señal sustentada en datos**, y siempre
viaja con `confianza: "baja"`.

### 4. Nieve húmeda (*wet snow*)

Pérdida de resistencia por presencia de agua líquida en el manto: lluvia,
radiación solar intensa o ascenso térmico marcado. La lluvia es el mecanismo más
rápido — actúa en horas.

**Detección, en orden de prioridad:**

1. Lluvia observada ≥ 2 h con acumulación (`tipo_precipitacion` ∈ RAIN,
   LIGHT_RAIN, HEAVY_RAIN, FREEZING_RAIN, RAIN_AND_SNOW) — **confianza alta**
2. Bulbo húmedo máximo > 0,5 °C con precipitación, *solo si el proveedor no
   clasificó el tipo* — confianza media
3. Alerta `wet_snow` del ensemble WN2 — confianza media
4. Humedad superficial SAR (ΔVV < −3 dB vs baseline, Nagler et al. 2016) con
   fusión activa — confianza media

**Sustento: sólido.** El tipo observado tiene prioridad sobre cualquier
inferencia: si el proveedor reporta `SNOW`, un pico de bulbo húmedo en otra hora
del día no convierte la nevada en lluvia.

### 5. Nieve deslizante (*gliding snow*)

El manto completo repta sobre un suelo liso —roca lisa, pastizal— humedecido en
la base. Las grietas de reptación anuncian el proceso, pero el momento de la
liberación es impredecible.

**Detección:** humedad SAR + pendiente media de la zona de inicio entre 30° y 45°
+ ausencia de nieve nueva reciente + fusión activa. **Sustento: proxy.** No hay
observación de grietas de reptación ni del sustrato: se emite solo como problema
secundario.

## Cota de nieve

Se publica como `cota_nieve_m`. Método principal: la transición medida entre los
sectores de la zona, que están a distinta altitud (La Parva: 2.700 / 3.000 /
3.600 m de altitud de referencia). La cota queda entre el sector más alto con
lluvia y el más bajo con nieve.

Si la zona no tiene sectores con precipitación observada, se usa
`cota_0c_media_dia_m` del ensemble, que `fuente_weathernext2.py` ya calcula con
lapse rate variable según presión.

**Cuando nevó en todo el rango de la zona no se publica cota.** La transición
queda por debajo del terreno observado, y publicar la altitud del punto más bajo
se leería como una cota real cuando el dato solo dice "nevó hasta aquí abajo".

## Umbral de fase lluvia/nieve

La transición real ocurre en torno a **1 °C** de temperatura del aire, no a 2 °C.
El bulbo húmedo es mejor predictor porque incorpora el enfriamiento por
evaporación (Steinacker 1983; Sims & Liu 2015); el sistema usa 0,5 °C.

Umbrales corregidos en la v25.19:

| lugar | antes | ahora |
|---|---|---|
| `ingestor_wn2.py` `is_rain_member` | T > 2,0 °C | T > 1,0 °C |
| `ingestor_wn2.py` `is_wet_snow_member` | 0,0 – 2,0 °C | −0,5 – 1,5 °C |
| `fuente_weathernext2.py` `snow_type_member` | rain > 2,0 °C | rain > 1,0 °C |
| `tool_ventanas_criticas.py` ventana ROS | T instantánea > 2 °C | tipo observado, o T máxima del día > 2 °C |

Verificación con el caso del 25-jul: con los umbrales nuevos, el ensemble pasó a
marcar `wet_snow` en Lagunillas (antes `false`), y la clasificación propia da
`wet_snow` en La Parva Sector Bajo (11 h de lluvia) manteniendo `new_snow` en el
Sector Alto (19 h de nieve).

## Limitaciones declaradas

1. **Capa débil persistente y nieve deslizante son proxies** en los Andes. Sin
   perfiles de manto ni observación de grietas, su confianza es baja por
   construcción y no encabezan el boletín frente a una señal sólida.
2. **Un problema dominante por zona.** El boletín no divide por bandas de
   altitud: publica el dominante y la cota como dato. El 25-jul eso significa que
   La Parva se reporta con el problema de su sector representativo (Medio),
   aunque el Bajo tuviera lluvia y el Alto nieve seca.
3. **El tipo de precipitación depende del proveedor.** Google Weather no publica
   `tipo_precipitacion` para fechas anteriores a su cobertura; en esos casos la
   clasificación cae al ensemble y a los umbrales por temperatura.
