import { useEffect, useState } from 'react'

// Boletín activo publicado diariamente por el backend (BigQuery → GCS).
// Esquema (generado por agentes/salidas/almacenador.py → exportar_boletin_activo):
// {
//   "generado": "2026-06-12T03:04:10Z",
//   "fuente": "pipeline-s5",
//   "boletines": [{
//     "zona": "La Parva", "nivel_eaws": 2,
//     "nivel_eaws_48h": 2, "nivel_eaws_72h": 2, "confianza": "Alta",
//     "descripcion": "...", "tendencia": "estable",
//     "temperatura_c": 0.1, "viento_kmh": 10, "precip_24h_mm": 0,
//     "pronostico_3d": [{ "fecha", "tmax", "tmin", "precip_mm", "viento_kmh", "cielo" }],
//     "manto": { "estado", "factor_seguridad" },
//     "satelital": { "estado", "score_anomalia", "datos_disponibles" },
//     "comunidad": { "relatos_analizados", "tipo_alud_predominante", "indice_riesgo_historico" },
//     "problema": "low_load", "terreno_riesgo": "...",
//     "titulo_recomendacion": "...", "recomendaciones": ["..."],
//     "emitido": "2026-06-12T02:58:10Z"
//   }]
// }
// Solo "zona" y "nivel_eaws" son obligatorios: todo lo demás cae a mock si falta.

const URL_BOLETIN =
  import.meta.env.VITE_BOLETIN_URL ??
  'https://storage.googleapis.com/avalanche-alertcl-boletines/boletin_activo.json'

// Series diarias del ensemble WeatherNext 2 (publica ingestor-wn2, ~16 días/zona):
// { "generado", "fuente": "ingestor-wn2",
//   "series": [{ "zona": "La Parva", "dias": [{ "fecha", "tmin", "tmax",
//     "nieve_cm", "nieve_cm_p95", "problema", "confianza" }] }] }
const URL_SERIES_WN2 =
  import.meta.env.VITE_SERIES_WN2_URL ??
  'https://storage.googleapis.com/avalanche-alertcl-boletines/series_wn2.json'

// Series horarias de Google Weather (publica exportar_series_horas.py, ~72 h/zona):
// { "generado", "fuente": "google-weather-hours",
//   "series": [{ "zona": "La Parva", "horas": [{ "t": ISO_UTC, "temp", "icono" }] }] }
const URL_SERIES_HORAS =
  import.meta.env.VITE_SERIES_HORAS_URL ??
  'https://storage.googleapis.com/avalanche-alertcl-boletines/series_horas.json'

const TIMEOUT_MS = 8000

// Nombre de zona (como aparece en BigQuery) → id de centro del frontend
const slug = (texto) =>
  String(texto)
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, '-')

const nivelValido = (valor) => {
  const nivel = Number(valor)
  return Number.isInteger(nivel) && nivel >= 1 && nivel <= 5 ? nivel : null
}

function normalizarEntrada(entrada) {
  const zona = entrada.zona ?? entrada.centro ?? entrada.id
  const nivel = nivelValido(entrada.nivel_eaws ?? entrada.nivel ?? entrada.nivel_riesgo)
  if (zona == null || nivel == null) return null

  return [
    slug(zona),
    {
      nivel,
      nivel48h: nivelValido(entrada.nivel_eaws_48h),
      nivel72h: nivelValido(entrada.nivel_eaws_72h),
      confianza: entrada.confianza ?? null,
      descripcion: entrada.descripcion ?? null,
      tendencia: entrada.tendencia ?? null,
      temperaturaC: entrada.temperatura_c ?? null,
      vientoKmh: entrada.viento_kmh ?? null,
      pronostico3d: Array.isArray(entrada.pronostico_3d) ? entrada.pronostico_3d : [],
      manto: entrada.manto ?? {},
      satelital: entrada.satelital ?? {},
      comunidad: entrada.comunidad ?? {},
      problema: entrada.problema ?? null,
      terrenoRiesgo: entrada.terreno_riesgo ?? null,
      tituloRecomendacion: entrada.titulo_recomendacion ?? null,
      recomendaciones: Array.isArray(entrada.recomendaciones) ? entrada.recomendaciones : [],
      emitido: entrada.emitido ?? null,
    },
  ]
}

// Carpeta del bucket (para histórico e índice de fechas)
const URL_BASE = URL_BOLETIN.replace(/[^/]+$/, '')

async function obtenerBoletinDesde(url) {
  const respuesta = await fetch(url, {
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

  const boletines = new Map(entradas.map(normalizarEntrada).filter(Boolean))
  if (boletines.size === 0) {
    throw new Error('El boletín no contiene zonas válidas')
  }

  return {
    generado: cuerpo.generado ?? null,
    fechaBoletin: cuerpo.fecha_boletin ?? null,
    boletines,
  }
}

export const obtenerBoletinActivo = () => obtenerBoletinDesde(URL_BOLETIN)

export const obtenerBoletinFecha = (fecha) =>
  obtenerBoletinDesde(`${URL_BASE}historico/boletin_${fecha}.json`)

// Índice de fechas con boletín histórico disponible (orden descendente)
export function useIndiceFechas() {
  const [fechas, setFechas] = useState([])

  useEffect(() => {
    let montado = true
    fetch(`${URL_BASE}indice_boletines.json`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: 'no-store',
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((cuerpo) => {
        if (montado && Array.isArray(cuerpo.fechas)) setFechas(cuerpo.fechas)
      })
      .catch((error) => {
        console.warn('Índice de boletines no disponible:', error.message)
      })
    return () => {
      montado = false
    }
  }, [])

  return fechas
}

export async function obtenerSeriesWN2(fecha = null) {
  const url = fecha ? `${URL_BASE}series_wn2/series_${fecha}.json` : URL_SERIES_WN2
  const respuesta = await fetch(url, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  if (!respuesta.ok) {
    throw new Error(`Series WN2 no disponibles (HTTP ${respuesta.status})`)
  }

  const cuerpo = await respuesta.json()
  if (!Array.isArray(cuerpo.series)) {
    throw new Error('Formato de series WN2 no reconocido')
  }

  return new Map(
    cuerpo.series
      .filter((s) => s.zona && Array.isArray(s.dias) && s.dias.length > 0)
      .map((s) => [slug(s.zona), s.dias])
  )
}

const SERIES_VACIAS = { series: new Map(), esDeFecha: true }

// Series del ensemble WN2. Con fecha histórica intenta el archivo datado
// (series_wn2/series_<fecha>.json) y si no existe cae al pronóstico vigente
// con esDeFecha=false (la tarjeta lo advierte). Ante error total → demo.
export function useSeriesWN2(fecha = null) {
  const [resultado, setResultado] = useState({ paraFecha: undefined, ...SERIES_VACIAS })

  useEffect(() => {
    let montado = true
    obtenerSeriesWN2(fecha)
      .then((series) => {
        if (montado) setResultado({ paraFecha: fecha, series, esDeFecha: true })
      })
      .catch((error) => {
        console.warn('Series WN2 no disponibles para la fecha:', error.message)
        if (!montado) return
        if (!fecha) {
          setResultado({ paraFecha: fecha, ...SERIES_VACIAS })
          return
        }
        obtenerSeriesWN2()
          .then((series) => {
            if (montado) setResultado({ paraFecha: fecha, series, esDeFecha: false })
          })
          .catch(() => {
            if (montado) setResultado({ paraFecha: fecha, ...SERIES_VACIAS })
          })
      })
    return () => {
      montado = false
    }
  }, [fecha])

  return resultado.paraFecha === fecha ? resultado : SERIES_VACIAS
}

export async function obtenerSeriesHoras(fecha = null) {
  const url = fecha ? `${URL_BASE}series_horas/series_${fecha}.json` : URL_SERIES_HORAS
  const respuesta = await fetch(url, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  if (!respuesta.ok) {
    throw new Error(`Series horarias no disponibles (HTTP ${respuesta.status})`)
  }

  const cuerpo = await respuesta.json()
  if (!Array.isArray(cuerpo.series)) {
    throw new Error('Formato de series horarias no reconocido')
  }

  return new Map(
    cuerpo.series
      .filter((s) => s.zona && Array.isArray(s.horas) && s.horas.length > 0)
      .map((s) => [slug(s.zona), s.horas])
  )
}

const MAPA_HORAS_VACIO = new Map()

// Series horarias reales (Google Weather) para el widget de evolución.
// Vigente → series_horas.json; histórico → series_horas/series_<fecha>.json.
// Si no hay archivo, cae a vacío y el widget usa el mock con niveles reales.
export function useSeriesHoras(fecha = null) {
  const [resultado, setResultado] = useState({ paraFecha: undefined, series: MAPA_HORAS_VACIO })

  useEffect(() => {
    let montado = true
    obtenerSeriesHoras(fecha)
      .then((mapa) => {
        if (montado) setResultado({ paraFecha: fecha, series: mapa })
      })
      .catch((error) => {
        console.warn('Series horarias no disponibles:', error.message)
        if (montado) setResultado({ paraFecha: fecha, series: MAPA_HORAS_VACIO })
      })
    return () => {
      montado = false
    }
  }, [fecha])

  return resultado.paraFecha === fecha ? resultado.series : MAPA_HORAS_VACIO
}

const MAPA_OBS_VACIO = new Map()

export async function obtenerObservaciones() {
  const respuesta = await fetch(`${URL_BASE}observaciones.json`, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  if (!respuesta.ok) {
    throw new Error(`Observaciones no disponibles (HTTP ${respuesta.status})`)
  }
  const cuerpo = await respuesta.json()
  if (!Array.isArray(cuerpo.observaciones)) {
    throw new Error('Formato de observaciones no reconocido')
  }
  // Agrupa por centro (slug) preservando el orden (más recientes primero).
  const mapa = new Map()
  for (const obs of cuerpo.observaciones) {
    if (!obs.centro || !obs.comentarios) continue
    const clave = slug(obs.centro)
    if (!mapa.has(clave)) mapa.set(clave, [])
    mapa.get(clave).push(obs)
  }
  return mapa
}

// Observaciones reales de la comunidad (envíos del formulario). Independiente
// de la fecha seleccionada: son reportes vigentes de la comunidad.
export function useObservaciones() {
  const [observaciones, setObservaciones] = useState(MAPA_OBS_VACIO)

  useEffect(() => {
    let montado = true
    obtenerObservaciones()
      .then((mapa) => {
        if (montado) setObservaciones(mapa)
      })
      .catch((error) => {
        console.warn('Observaciones no disponibles:', error.message)
        if (montado) setObservaciones(MAPA_OBS_VACIO)
      })
    return () => {
      montado = false
    }
  }, [])

  return observaciones
}

const BOLETIN_CARGANDO = {
  estado: 'cargando',
  boletines: new Map(),
  generado: null,
  fechaBoletin: null,
}

// estado: 'cargando' | 'en-linea' | 'demo' (fallback elegante a datos mock)
// fecha = null → boletín activo; 'YYYY-MM-DD' → boletín histórico de esa fecha
export function useBoletinActivo(fecha = null) {
  // paraFecha permite derivar 'cargando' al cambiar de fecha sin setState síncrono
  const [resultado, setResultado] = useState({ paraFecha: undefined, ...BOLETIN_CARGANDO })

  useEffect(() => {
    let montado = true
    const promesa = fecha ? obtenerBoletinFecha(fecha) : obtenerBoletinActivo()
    promesa
      .then(({ generado, fechaBoletin, boletines }) => {
        if (montado) {
          setResultado({ paraFecha: fecha, estado: 'en-linea', boletines, generado, fechaBoletin })
        }
      })
      .catch((error) => {
        console.warn('Boletín en línea no disponible, usando datos demo:', error.message)
        if (montado) setResultado({ paraFecha: fecha, ...BOLETIN_CARGANDO, estado: 'demo' })
      })
    return () => {
      montado = false
    }
  }, [fecha])

  return resultado.paraFecha === fecha ? resultado : BOLETIN_CARGANDO
}
