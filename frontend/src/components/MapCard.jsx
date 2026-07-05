import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Map, Layers, Loader2, Maximize2, X } from 'lucide-react'
import GlassCard from './GlassCard'
import { ESCALA_EAWS } from '../data/mockData'
import { useMapaGEE } from '../services/mapa'

const COORDS = {
  'ski-arpa': [-32.6, -70.39],
  portillo: [-32.837, -70.129],
  'la-parva': [-33.34, -70.28],
  'valle-nevado': [-33.35, -70.25],
  lagunillas: [-33.68, -70.25],
  'chapa-verde': [-34.17, -70.37],
  'laguna-del-maule': [-36.058, -70.56],
  'nevados-de-chillan': [-36.858, -71.3727],
  antuco: [-37.41, -71.42],
  corralco: [-38.37, -71.57],
  'las-araucarias': [-38.73, -71.74],
  'ski-pucon': [-39.50, -71.96],
  antillanca: [-40.7756, -72.2046],
  'volcan-osorno': [-41.10, -72.50],
  'el-fraile': [-45.68, -71.94],
  'cerro-mirador': [-53.13, -70.98],
  'valle-de-las-arenas': [-33.90, -70.05],
  'planchon-peteroa': [-35.24, -70.57],
  'los-arenales': [-38.85, -72.00],
  'mocho-choshuenco': [-39.93, -72.03],
  'ski-chaiten': [-42.83, -72.68],
  'el-colorado': [-33.36, -70.29],
}

const CENTRO_DEFECTO = [-39.0, -71.2]
const ZOOM_DEFECTO = 4

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

function fechaCorta(iso, conAnio = false) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return `${d} ${MESES[m - 1]}${conAnio ? ` ${y}` : ''}`
}

function fechaReciente(gee) {
  if (!gee?.fecha_hasta) return ''
  const fecha = fechaCorta(gee.fecha_hasta, true)
  return gee.hora_hasta ? `${fecha} ${gee.hora_hasta} UTC` : fecha
}

function iniciarMapa(contenedor, gee, centros, seleccionadoId, onSelect, zoom) {
  const mapa = L.map(contenedor, {
    center: CENTRO_DEFECTO,
    zoom: zoom ?? ZOOM_DEFECTO,
    zoomControl: true,
    attributionControl: true,
  })
  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: 'Esri, Maxar', maxZoom: 17 }
  ).addTo(mapa)

  if (gee?.capas) {
    const atrib = gee.atribucion ?? 'Google Earth Engine'
    const color = L.tileLayer(gee.capas.color, { attribution: atrib, opacity: 1 })
    const nieve = L.tileLayer(gee.capas.nieve, { opacity: 0.9 })
    const riesgo = L.tileLayer(gee.capas.riesgo, { opacity: 0.95 })
    color.addTo(mapa)
    nieve.addTo(mapa)
    riesgo.addTo(mapa)
    L.control
      .layers(
        null,
        { 'Color real (Sentinel-2)': color, 'Cobertura de nieve (NDSI ≥ 0.4)': nieve, 'Zonas de riesgo (nieve + 30–45°)': riesgo },
        { collapsed: true, position: 'topright' }
      )
      .addTo(mapa)
    if (gee.bounds) mapa.fitBounds(gee.bounds)
  }

  centros.forEach((centro) => {
    const coord = COORDS[centro.id]
    if (!coord) return
    const nivel = ESCALA_EAWS[centro.estadoActual.nivelEAWS]
    const activo = centro.id === seleccionadoId
    L.circleMarker(coord, {
      radius: activo ? 13 : 9,
      color: activo ? '#ffffff' : 'rgba(0,0,0,0.5)',
      weight: activo ? 3 : 1.5,
      fillColor: nivel.color,
      fillOpacity: 0.95,
    })
      .addTo(mapa)
      .bindTooltip(`${centro.nombre} · Nivel ${centro.estadoActual.nivelEAWS}`, { direction: 'top' })
      .on('click', () => onSelect?.(centro.id))
  })

  if (!gee?.bounds) {
    const coordsVisibles = centros.map((c) => COORDS[c.id]).filter(Boolean)
    if (coordsVisibles.length > 1) mapa.fitBounds(L.latLngBounds(coordsVisibles), { padding: [30, 30] })
  }
  setTimeout(() => mapa.invalidateSize(), 0)
  return mapa
}

// Modal fullscreen — renderiza via portal fuera de GlassCard para evitar
// que backdrop-blur-xl del padre bloquee position:fixed.
function MapaAmpliado({ gee, centros, seleccionadoId, onSelect, onCerrar }) {
  const refCont = useRef(null)

  useEffect(() => {
    if (!refCont.current) return
    const mapa = iniciarMapa(refCont.current, gee, centros, seleccionadoId, onSelect, ZOOM_DEFECTO + 1)
    return () => mapa.remove()
  }, [gee, centros, seleccionadoId, onSelect])

  // Cerrar con Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCerrar])

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex flex-col bg-black/85 backdrop-blur-sm">
      <div className="relative flex-1">
        <div ref={refCont} className="absolute inset-0" />

        {/* Botón cerrar */}
        <button
          onClick={onCerrar}
          className="absolute top-3 right-3 z-[10000] flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
        >
          <X className="h-3.5 w-3.5" />
          Cerrar
        </button>

        {/* Leyenda */}
        {gee && (
          <div className="pointer-events-none absolute bottom-3 left-3 z-[10000] flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[9px] text-white/85 backdrop-blur-sm">
            <Layers className="h-3 w-3" />
            Sentinel-2 · imagen al {fechaReciente(gee)}
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}

export default function MapCard({ centros, seleccionadoId, onSelect, className = '' }) {
  const { datos: gee, estado } = useMapaGEE()
  const refContenedor = useRef(null)
  const refMapa = useRef(null)
  const refMarcadores = useRef({})
  const [ampliado, setAmpliado] = useState(false)

  // 1. Inicializa el mapa base una sola vez.
  useEffect(() => {
    if (refMapa.current || !refContenedor.current) return
    const mapa = L.map(refContenedor.current, {
      center: CENTRO_DEFECTO,
      zoom: ZOOM_DEFECTO,
      zoomControl: true,
      attributionControl: true,
    })
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Esri, Maxar', maxZoom: 17 }
    ).addTo(mapa)
    const todasCoords = Object.values(COORDS)
    if (todasCoords.length > 1) mapa.fitBounds(L.latLngBounds(todasCoords), { padding: [30, 30] })
    refMapa.current = mapa
    setTimeout(() => mapa.invalidateSize(), 0)
    return () => {
      mapa.remove()
      refMapa.current = null
    }
  }, [])

  // 2. Capas Earth Engine.
  useEffect(() => {
    const mapa = refMapa.current
    if (!mapa || !gee?.capas) return
    const atrib = gee.atribucion ?? 'Google Earth Engine'
    const color = L.tileLayer(gee.capas.color, { attribution: atrib, opacity: 1 })
    const nieve = L.tileLayer(gee.capas.nieve, { opacity: 0.9 })
    const riesgo = L.tileLayer(gee.capas.riesgo, { opacity: 0.95 })
    color.addTo(mapa)
    nieve.addTo(mapa)
    riesgo.addTo(mapa)
    const control = L.control
      .layers(
        null,
        { 'Color real (Sentinel-2)': color, 'Cobertura de nieve (NDSI ≥ 0.4)': nieve, 'Zonas de riesgo (nieve + 30–45°)': riesgo },
        { collapsed: true, position: 'topright' }
      )
      .addTo(mapa)
    // No re-encuadra al bounds del ROI GEE: el mapa ya muestra Chile completo.
    return () => {
      mapa.removeControl(control)
      mapa.removeLayer(color)
      mapa.removeLayer(nieve)
      mapa.removeLayer(riesgo)
    }
  }, [gee])

  // 3. Marcadores por nivel EAWS.
  useEffect(() => {
    const mapa = refMapa.current
    if (!mapa) return
    Object.values(refMarcadores.current).forEach((m) => m.remove())
    refMarcadores.current = {}
    centros.forEach((centro) => {
      const coord = COORDS[centro.id]
      if (!coord) return
      const nivel = ESCALA_EAWS[centro.estadoActual.nivelEAWS]
      const activo = centro.id === seleccionadoId
      const marcador = L.circleMarker(coord, {
        radius: activo ? 11 : 8,
        color: activo ? '#ffffff' : 'rgba(0,0,0,0.5)',
        weight: activo ? 3 : 1.5,
        fillColor: nivel.color,
        fillOpacity: 0.95,
      })
        .addTo(mapa)
        .bindTooltip(`${centro.nombre} · Nivel ${centro.estadoActual.nivelEAWS}`, { direction: 'top' })
      marcador.on('click', () => onSelect?.(centro.id))
      refMarcadores.current[centro.id] = marcador
    })
  }, [centros, seleccionadoId, onSelect])

  return (
    <GlassCard icon={Map} title="Mapa de zonas EAWS · Earth Engine" className={className}>
      <div className="relative min-h-72 flex-1 overflow-hidden rounded-2xl">
        <div ref={refContenedor} className="absolute inset-0 z-0 h-full w-full" />

        {estado === 'cargando' && (
          <div className="pointer-events-none absolute inset-0 z-[400] flex items-center justify-center bg-slate-900/40">
            <span className="flex items-center gap-2 rounded-full bg-black/50 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Generando capas satelitales…
            </span>
          </div>
        )}

        {/* Botón ampliar */}
        <button
          onClick={() => setAmpliado(true)}
          className="absolute top-2 right-2 z-[400] flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
        >
          <Maximize2 className="h-3.5 w-3.5" />
          Ampliar
        </button>

        {estado === 'ok' && gee && (
          <div className="pointer-events-none absolute bottom-2 left-2 z-[400] flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[9px] text-white/85 backdrop-blur-sm">
            <Layers className="h-3 w-3" />
            Sentinel-2 · imagen al {fechaReciente(gee)}
          </div>
        )}
      </div>

      {ampliado && (
        <MapaAmpliado
          gee={gee}
          centros={centros}
          seleccionadoId={seleccionadoId}
          onSelect={onSelect}
          onCerrar={() => setAmpliado(false)}
        />
      )}
    </GlassCard>
  )
}
