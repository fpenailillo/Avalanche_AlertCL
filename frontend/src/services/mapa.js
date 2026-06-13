import { useEffect, useState } from 'react'

// Capas de Earth Engine (color real, nieve, riesgo) para el mapa interactivo.
const URL_MAPA_GEE =
  import.meta.env.VITE_MAPA_GEE_URL ?? 'https://mapa-gee-hyf7y447pa-uc.a.run.app'

const TIMEOUT_MS = 60000

export async function obtenerMapaGEE() {
  const respuesta = await fetch(URL_MAPA_GEE, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
  })
  if (!respuesta.ok) {
    throw new Error(`Mapa GEE no disponible (HTTP ${respuesta.status})`)
  }
  const cuerpo = await respuesta.json()
  if (!cuerpo.capas) throw new Error('Respuesta de mapa GEE no reconocida')
  return cuerpo
}

// Hook: carga las capas GEE una vez. Devuelve { datos, estado }.
// estado: 'cargando' | 'ok' | 'error' (el widget cae al mapa base si falla).
export function useMapaGEE() {
  const [resultado, setResultado] = useState({ datos: null, estado: 'cargando' })

  useEffect(() => {
    let montado = true
    obtenerMapaGEE()
      .then((datos) => {
        if (montado) setResultado({ datos, estado: 'ok' })
      })
      .catch((error) => {
        console.warn('Mapa GEE no disponible:', error.message)
        if (montado) setResultado({ datos: null, estado: 'error' })
      })
    return () => {
      montado = false
    }
  }, [])

  return resultado
}
