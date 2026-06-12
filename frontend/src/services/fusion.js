// Fusiona los datos en línea del boletín (pipeline S5) sobre la estructura
// de los centros mock. Campo por campo: lo que el boletín no trae conserva
// su valor de demostración.

const capitalizar = (texto) =>
  texto ? texto.charAt(0).toUpperCase() + texto.slice(1).toLowerCase() : texto

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

function fusionarEstadoActual(estadoMock, detalle) {
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
    descripcionIA: detalle.descripcion ?? estadoMock.descripcionIA,
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

export function fusionarCentros(centrosMock, boletines) {
  if (!boletines || boletines.size === 0) return centrosMock

  return centrosMock.map((centro) => {
    const detalle = boletines.get(centro.id)
    if (!detalle) return centro

    return {
      ...centro,
      enLinea: true,
      estadoActual: fusionarEstadoActual(centro.estadoActual, detalle),
      timeline: fusionarTimeline(centro.timeline, detalle),
      topografico: fusionarTopografico(centro.topografico, detalle.manto, detalle),
      satelital: fusionarSatelital(centro.satelital, detalle.satelital, detalle),
      comunidad: fusionarComunidad(centro.comunidad, detalle.comunidad),
      problemas: fusionarProblemas(centro.problemas, detalle),
      recomendaciones: detalle.recomendaciones,
      tituloRecomendacion: detalle.tituloRecomendacion,
      pronostico3dReal: detalle.pronostico3d,
    }
  })
}
