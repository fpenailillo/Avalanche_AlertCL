import { useEffect, useState } from 'react'

// Boletín activo publicado diariamente por el backend (BigQuery → GCS).
// Esquema esperado del JSON:
// {
//   "generado": "2026-06-11T08:00:00Z",
//   "boletines": [
//     { "zona": "La Parva", "nivel_eaws": 2 },
//     { "zona": "Valle Nevado", "nivel_eaws": 3 },
//     ...
//   ]
// }
// El normalizador también acepta variantes de campo (centro/id, nivel/nivel_riesgo)
// y un arreglo en la raíz en lugar de la clave "boletines".

const URL_BOLETIN =
  import.meta.env.VITE_BOLETIN_URL ??
  'https://storage.googleapis.com/mi-bucket-avalanchas/boletin_activo.json'

const TIMEOUT_MS = 8000

// Nombre de zona (como aparece en BigQuery) → id de centro del frontend
const slug = (texto) =>
  String(texto)
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '-')

function normalizarEntrada(entrada) {
  const zona = entrada.zona ?? entrada.centro ?? entrada.id
  const nivelCrudo = entrada.nivel_eaws ?? entrada.nivel ?? entrada.nivel_riesgo
  if (zona == null || nivelCrudo == null) return null

  const nivel = Number(nivelCrudo)
  if (!Number.isInteger(nivel) || nivel < 1 || nivel > 5) return null

  return [slug(zona), nivel]
}

export async function obtenerBoletinActivo() {
  const respuesta = await fetch(URL_BOLETIN, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  if (!respuesta.ok) {
    throw new Error(`Boletín no disponible (HTTP ${respuesta.status})`)
  }

  const cuerpo = await respuesta.json()
  const entradas = Array.isArray(cuerpo) ? cuerpo : cuerpo.boletines
  if (!Array.isArray(entradas)) {
    throw new Error('Formato de boletín no reconocido')
  }

  const niveles = new Map(entradas.map(normalizarEntrada).filter(Boolean))
  if (niveles.size === 0) {
    throw new Error('El boletín no contiene zonas válidas')
  }

  return { generado: cuerpo.generado ?? null, niveles }
}

// estado: 'cargando' | 'en-linea' | 'demo' (fallback elegante a datos mock)
export function useBoletinActivo() {
  const [boletin, setBoletin] = useState({
    estado: 'cargando',
    niveles: new Map(),
    generado: null,
  })

  useEffect(() => {
    let montado = true
    obtenerBoletinActivo()
      .then(({ generado, niveles }) => {
        if (montado) setBoletin({ estado: 'en-linea', niveles, generado })
      })
      .catch((error) => {
        console.warn('Boletín en línea no disponible, usando datos demo:', error.message)
        if (montado) setBoletin({ estado: 'demo', niveles: new Map(), generado: null })
      })
    return () => {
      montado = false
    }
  }, [])

  return boletin
}
