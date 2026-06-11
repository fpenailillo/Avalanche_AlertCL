# Avalanche_AlertCL: Sistema Inteligente de Predicción de Riesgo de Avalanchas en Chile

Sistema multi-agente de inteligencia artificial que genera boletines de riesgo de avalanchas para zonas de montaña chilenas. El proyecto combina modelos físicos, imágenes satelitales, pronósticos meteorológicos y análisis contextual basado en Inteligencia Artificial (LLMs) para suplir la falta de redes de observación en terreno.

> **Tesis de Magíster en Tecnologías de la Información** > **Autor:** Francisco Peñailillo | **Profesor Guía:** Mauricio Solar  
> Universidad Técnica Federico Santa María (UTFSM) — 2026  

---

## El Problema

Las avalanchas representan uno de los peligros naturales de mayor impacto en las zonas cordilleranas de Chile. Cada invierno, los principales centros de ski y zonas de montaña de la Región Metropolitana (La Parva, Valle Nevado, El Colorado) y el sur del país reciben a decenas de miles de visitantes, quienes se exponen a un terreno que no cuenta con un sistema automatizado y centralizado de predicción.

A diferencia de los países alpinos (como Suiza o Austria) donde existen institutos que publican boletines diarios respaldados por cientos de estaciones de medición, en Chile la emisión de alertas es un desafío gigante. La escasez de estaciones meteorológicas de alta montaña y la ausencia de una red masiva de observación del manto nivoso dificultan la aplicación directa de las metodologías europeas.

## La Solución y el Aporte a la Comunidad

**Avalanche_AlertCL** nace para democratizar el acceso a la seguridad invernal. Al no contar con suficientes datos directos de la nieve, este proyecto propone un enfoque innovador: construir un sistema que infiere el riesgo a partir de **fuentes de datos indirectas** y el **conocimiento de la comunidad**.

Utilizando la orquestación de múltiples agentes de Inteligencia Artificial, el sistema recopila datos del clima, topografía, satélites y, de manera crucial, **relatos e informes de montañistas locales** (saberes humanos). Luego, procesa toda esta información simulando el razonamiento de un experto para emitir un boletín de riesgo estructurado bajo el estándar internacional **EAWS (European Avalanche Warning Services)**.

---

## Cómo Funciona: Arquitectura Conceptual

El sistema se divide en tres grandes etapas: la recolección de los datos, el procesamiento a través de agentes especializados en distintas disciplinas, y la generación del producto final.

```mermaid
graph LR
    subgraph GCP [Google Cloud Platform]
        direction LR
        
        subgraph CapaDatos [ Capa de Datos / datos/]
            direction TB
            CS([Cloud Scheduler])
            
            E1[extractor-clima]
            E2[procesador-clima-horas]
            E3[procesador-clima-dias]
            E4[monitor-satelital-nieve]
            E5[analizador-zonas]

            CS -- 3x/día --> E1
            CS -- Triggers --> E2
            CS -- Triggers --> E3
            CS -- 3x/día --> E4
            CS -- Mensual --> E5
        end

        BQ[(BigQuery \n clima.*)]

        E1 --> BQ
        E2 --> BQ
        E3 --> BQ
        E4 --> BQ
        E5 --> BQ

        subgraph CapaAgentes [Capa de Agentes / agentes/]
            direction LR
            O{{Orquestador}}
            S1(S1: Topográfico)
            S2(S2: Satelital)
            S3(S3: Meteorológico)
            S4(S4: Sit. Briefing)
            S5(S5: Integrador EAWS)

            O --> S1
            S1 --> S2 --> S3 --> S4 --> S5
        end

        BQ -- Lectura de contexto --> O

        subgraph CapaResultados [Capa de Resultados]
            direction TB
            BQ_Res[(BigQuery \n boletines_riesgo)]
            GCS[[Cloud Storage \n JSON files]]
        end

        S5 -- Guarda 34 campos --> BQ_Res
        S5 -- Exporta JSON --> GCS
    end

    style GCP fill:#f8f9fa,stroke:#dadce0,stroke-width:2px
    style CapaDatos fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style CapaAgentes fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style CapaResultados fill:#fce8e6,stroke:#ea4335,stroke-width:2px
    style BQ fill:#fef7e0,stroke:#fbbc04,stroke-width:2px

````

## Los 5 Agentes Especializados
Para replicar el análisis multicapa que hace un experto humano, la IA está dividida en 5 subagentes, cada uno enfocado en una tarea específica:

S1 - Agente Topográfico: Analiza la forma de las montañas, la inclinación de las pendientes y la exposición al sol utilizando modelos digitales de elevación. Identifica las zonas estructuralmente propensas a deslaves.

S2 - Agente Satelital: Observa las montañas desde el espacio usando satélites (como Sentinel-2). Mide dónde hay nieve, hasta qué altura llega (línea de nieve) y busca anomalías.

S3 - Agente Meteorológico: Analiza pronósticos climáticos complejos y evalúa ventanas críticas como tormentas inminentes, cambios drásticos de temperatura o vientos fuertes que puedan mover la nieve.

S4 - Agente Contextual (Briefing): Analiza miles de relatos históricos y reportes recientes de montañistas para entender cómo se comporta la nieve en la realidad local y darle contexto humano a los datos fríos.

S5 - Agente Integrador EAWS: Es el "juez final". Toma las conclusiones de los cuatro agentes anteriores, evalúa la estabilidad, frecuencia y tamaño esperado de las avalanchas, y redacta el boletín final con el nivel de peligro (del 1 al 5).

##  Estructura del Repositorio
Para quienes deseen explorar el código fuente, el proyecto está organizado de la siguiente manera:

/datos: Scripts y funciones en la nube (GCP) encargadas de extraer continuamente la información meteorológica, satelital y los relatos de la comunidad.

/agentes: El motor principal de la IA. Aquí reside la lógica de los 5 subagentes, su orquestación y la comunicación con los Modelos de Lenguaje (LLMs).

/notebooks_validacion: Entorno de investigación académica utilizado para comparar los resultados de la IA contra boletines de expertos humanos y validar las hipótesis de la tesis.

/docs: Documentación teórica, papers relevantes, fundamentos de la matriz EAWS y la propuesta original de la tesis.

####  Descargo de Responsabilidad > Este es un proyecto desarrollado con fines de investigación académica y pruebas de concepto. La información predictiva generada por esta Inteligencia Artificial es experimental y bajo ninguna circunstancia reemplaza el criterio humano experto, la capacitación adecuada ni el uso de equipos de seguridad en terreno (ARVA, pala, sonda). La montaña es un entorno dinámico y peligroso.
