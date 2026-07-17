# Analizador topográfico (DEM/GEE) — operación y gap de despliegue

**Estado 2026-07-17.** El pipeline `datos/analizador_avalanchas/` (entrypoint HTTP
`analizar_topografia`) calcula el perfil topográfico por zona con Google Earth
Engine y escribe las tablas `clima.zonas_avalancha` y `clima.pendientes_detalladas`,
que consume `analizar_dem` (subagente topográfico) vía
`ConsultorBigQuery.obtener_perfil_topografico`.

## Gap de despliegue

Este servicio **no se despliega con `agentes/despliegue/cloudbuild.yaml`** (ese
build solo actualiza `orquestador-avalanchas`, `ingestor-wn2` y
`exportar-series-horas`). No existe configuración de despliegue en el repo: el
servicio GEE se despliega/ejecuta manualmente.

Consecuencia mientras no se ejecute con la lista actualizada: las zonas
agregadas en 2026-07 (Valle de las Arenas, Termas del Flaco, Planchón-Peteroa,
Laguna del Maule, Los Arenales, Mocho-Choshuenco, Ski Chaitén) no tienen filas
en `clima.zonas_avalancha` → `analizar_dem` retorna `disponible=False` →
`datos_topograficos_ok=false` en el boletín, el PINN usa métricas por defecto y
el tamaño EAWS cae al default 2 (`tool_clasificar_eaws._determinar_tamano`),
lo que sesga el nivel a la baja en esas zonas. El boletín se emite igual.

## Cómo cerrar el gap

1. Redesplegar el servicio del analizador con el `UBICACIONES_ANALISIS`
   actualizado (ya incluye las 7 zonas nuevas y excluye El Colorado;
   Los Arenales usa las coordenadas corregidas de la ladera sur del Lonquimay
   `-38.410, -71.580`).
2. Invocar `analizar_topografia` (una corrida completa; el pipeline es mensual).
3. Verificar cobertura:

```sql
SELECT nombre_ubicacion, MAX(fecha_analisis) AS ultimo
FROM `climas-chileno.clima.zonas_avalancha`
GROUP BY 1 ORDER BY 1;
```

Criterio: las 7 zonas nuevas presentes; en la siguiente corrida del orquestador
`datos_topograficos_ok=true` para ellas en `clima.boletines_riesgo`.
