// Fusiona los datos en línea del boletín (pipeline S5) sobre la estructura
// de los centros mock. Campo por campo: lo que el boletín no trae conserva
// su valor de demostración.

import { ESCALA_EAWS } from '../data/mockData'

const capitalizar = (texto) =>
  texto ? texto.charAt(0).toUpperCase() + texto.slice(1).toLowerCase() : texto

// Frase clara por tipo de problema EAWS (sin jerga técnica) para el resumen
const FRASE_PROBLEMA = {
  wind_slab: 'El viento acumuló placas de nieve en laderas resguardadas.',
  storm_slab: 'La nieve reciente de la tormenta aún no se asienta.',
  drifting_snow: 'El viento sigue transportando nieve en altura.',
  new_snow: 'Cayó nieve nueva que todavía no se ha consolidado.',
  heavy_snow: 'Se acumula nieve nueva en cantidad importante.',
  wet_snow: 'La nieve se humedece con el calor del día.',
  gliding_snow: 'La nieve podría deslizar sobre el terreno.',
  persistent_weak_layer: 'Hay una capa débil enterrada en el manto.',
}

// Construye una descripción breve y clara a partir de los datos del boletín:
// nivel → problema → nieve prevista → tendencia. Real, sin tecnicismos.
function descripcionClara(detalle, dias) {
  const nombreNivel = ESCALA_EAWS[detalle.nivel]?.nombre?.toLowerCase()
  const partes = nombreNivel ? [`Peligro ${nombreNivel}.`] : []

  const fraseProblema = FRASE_PROBLEMA[detalle.problema]
  if (fraseProblema) {
    partes.push(fraseProblema)
  } else if (detalle.manto?.estado?.toUpperCase() === 'ESTABLE') {
    partes.push('El manto de nieve se mantiene estable.')
  }

  // Nieve prevista próximos 3 días (mediana del ensemble WN2)
  const nieve3d = (dias ?? [])
    .slice(0, 3)
    .reduce((suma, d) => suma + (d.nieveCm ?? 0), 0)
  if (nieve3d >= 5) {
    partes.push(`Se esperan unos ${Math.round(nieve3d)} cm de nieve en los próximos días.`)
  }

  // Tendencia a 48/72 h derivada de los niveles
  const futuro = Math.max(detalle.nivel48h ?? 0, detalle.nivel72h ?? 0)
  if (futuro > detalle.nivel) {
    partes.push('El riesgo tiende a aumentar.')
  } else if ((detalle.nivel48h ?? detalle.nivel) < detalle.nivel) {
    partes.push('El riesgo tiende a disminuir.')
  } else {
    partes.push('El riesgo se mantiene estable.')
  }

  return partes.join(' ')
}

const formatearFecha = (iso, opciones) => {
  if (!iso) return null
  const fecha = new Date(iso)
  if (Number.isNaN(fecha.getTime())) return null
  return fecha.toLocaleString('es-CL', { timeZone: 'America/Santiago', ...opciones })
}

// Tipos de problema del backend (tipo_problema_eaws / wn2_avalanche_problem)
// → id de ícono oficial EAWS + texto genérico
const PROBLEMAS_EAWS = {
  wind_slab: { id: 'wind-slab', nombre: 'Placas de viento' },
  storm_slab: { id: 'wind-slab', nombre: 'Placas de tormenta' },
  drifting_snow: { id: 'wind-slab', nombre: 'Nieve venteada' },
  new_snow: { id: 'new-snow', nombre: 'Nieve nueva' },
  heavy_snow: { id: 'new-snow', nombre: 'Nieve nueva intensa' },
  wet_snow: { id: 'wet-snow', nombre: 'Nieve húmeda' },
  gliding_snow: { id: 'gliding-snow', nombre: 'Nieve deslizante' },
  persistent_weak_layer: { id: 'persistent-weak-layer', nombre: 'Capa débil persistente' },
  low_load: { id: 'no-distinct', nombre: 'Sin problema distintivo' },
  no_distinct: { id: 'no-distinct', nombre: 'Sin problema distintivo' },
}

function fusionarEstadoActual(estadoMock, detalle, dias) {
  const fechaBoletin = formatearFecha(detalle.emitido, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const validoHasta =
    detalle.emitido &&
    formatearFecha(new Date(new Date(detalle.emitido).getTime() + 24 * 3600e3).toISOString(), {
      dateStyle: 'short',
      timeStyle: 'short',
    })

  return {
    ...estadoMock,
    nivelEAWS: detalle.nivel,
    // Mensaje principal claro (sin jerga); el análisis técnico de la IA
    // queda disponible aparte como descripcionTecnica.
    descripcionIA: descripcionClara(detalle, dias),
    descripcionTecnica: detalle.descripcion ?? null,
    temperatura: detalle.temperaturaC ?? estadoMock.temperatura,
    vientoKmh: detalle.vientoKmh ?? estadoMock.vientoKmh,
    fechaBoletin: fechaBoletin ? capitalizar(fechaBoletin) : estadoMock.fechaBoletin,
    validoHasta: validoHasta ? `Válido hasta el ${validoHasta}` : estadoMock.validoHasta,
    confianza: detalle.confianza ?? null,
    tendencia: detalle.tendencia ?? null,
  }
}

function fusionarTimeline(timelineMock, detalle) {
  // La timeline mock tiene 12 tramos de 6 h: 0-3 → 24 h, 4-7 → 48 h, 8-11 → 72 h
  const porTramo = [
    detalle.nivel,
    detalle.nivel48h ?? detalle.nivel,
    detalle.nivel72h ?? detalle.nivel48h ?? detalle.nivel,
  ]
  return timelineMock.map((punto, i) => ({
    ...punto,
    nivel: porTramo[Math.min(Math.floor(i / 4), 2)],
  }))
}

function fusionarTopografico(topoMock, manto, detalle) {
  if (!manto?.estado) return topoMock
  return {
    estadoManto: capitalizar(manto.estado),
    estable: manto.estado.toUpperCase() === 'ESTABLE',
    factorSeguridad: manto.factor_seguridad ?? null,
    confianza: null,
    ultimaCorrida:
      formatearFecha(detalle.emitido, { dateStyle: 'medium', timeStyle: 'short' }) ??
      topoMock.ultimaCorrida,
    real: true,
  }
}

function fusionarSatelital(satMock, satelital, detalle) {
  if (!satelital?.estado) return satMock
  return {
    estadoVit: capitalizar(satelital.estado),
    scoreAnomalia: satelital.score_anomalia ?? null,
    datosDisponibles: satelital.datos_disponibles ?? null,
    fechaPasada:
      formatearFecha(detalle.emitido, { dateStyle: 'medium', timeStyle: 'short' }) ??
      satMock.fechaPasada,
    real: true,
  }
}

function fusionarComunidad(comMock, comunidad) {
  if (comunidad?.relatos_analizados == null) return comMock
  return {
    ...comMock,
    totalReportes48h: comunidad.relatos_analizados,
    tipoAludPredominante: comunidad.tipo_alud_predominante ?? null,
    real: true,
  }
}

function fusionarProblemas(problemasMock, detalle) {
  const problema = PROBLEMAS_EAWS[detalle.problema]
  if (!problema) return problemasMock
  return [
    {
      id: problema.id,
      nombre: problema.nombre,
      cotas: null,
      orientaciones: null,
      detalle: detalle.terrenoRiesgo ?? 'Evaluación automática del sistema multi-agente.',
      real: true,
    },
  ]
}

const DIAS_SEMANA = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

const iconoDia = (dia) => {
  const nieve = dia.nieve_cm ?? 0
  if (nieve >= 10) return 'snowflake'
  if (nieve >= 1) return 'cloud-snow'
  if (dia.problema === 'wet_snow') return 'cloud'
  return 'sun'
}

function fusionarPronostico15(dias) {
  return dias
    .filter((dia) => dia.tmin != null && dia.tmax != null)
    .map((dia, i) => {
      // T12:00 evita el corrimiento de día por zona horaria al parsear la fecha
      const fecha = new Date(`${dia.fecha}T12:00:00`)
      return {
        dia: i === 0 ? 'Hoy' : DIAS_SEMANA[fecha.getDay()],
        fecha: `${fecha.getDate()} ${MESES[fecha.getMonth()]}`,
        icono: iconoDia(dia),
        min: dia.tmin,
        max: dia.tmax,
        nieveCm: Math.round(dia.nieve_cm ?? 0),
        nieveP95: dia.nieve_cm_p95 ?? null,
        isotermaM: null,
        confianza: dia.confianza ?? null,
        real: true,
      }
    })
}

export function fusionarCentros(centrosMock, boletines, seriesWN2) {
  const hayBoletin = boletines && boletines.size > 0
  const haySeries = seriesWN2 && seriesWN2.size > 0
  if (!hayBoletin && !haySeries) return centrosMock

  return centrosMock.map((centro) => {
    const detalle = hayBoletin ? boletines.get(centro.id) : null
    const dias = haySeries ? seriesWN2.get(centro.id) : null
    if (!detalle && !dias) return centro

    const fusionado = { ...centro }

    if (detalle) {
      Object.assign(fusionado, {
        enLinea: true,
        estadoActual: fusionarEstadoActual(centro.estadoActual, detalle, dias),
        timeline: fusionarTimeline(centro.timeline, detalle),
        topografico: fusionarTopografico(centro.topografico, detalle.manto, detalle),
        satelital: fusionarSatelital(centro.satelital, detalle.satelital, detalle),
        comunidad: fusionarComunidad(centro.comunidad, detalle.comunidad),
        problemas: fusionarProblemas(centro.problemas, detalle),
        recomendaciones: detalle.recomendaciones,
        tituloRecomendacion: detalle.tituloRecomendacion,
      })
    }

    if (dias?.length) {
      fusionado.pronostico15 = fusionarPronostico15(dias)
    }

    return fusionado
  })
}
