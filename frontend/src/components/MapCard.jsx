import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Map, Layers, Loader2 } from 'lucide-react'
import GlassCard from './GlassCard'
import { ESCALA_EAWS } from '../data/mockData'
import { useMapaGEE } from '../services/mapa'

// Coordenadas reales (lat, lon) de cada centro, para los marcadores Leaflet.
const COORDS = {
  'ski-arpa': [-32.6, -70.39],
  portillo: [-32.837, -70.129],
  'la-parva': [-33.34, -70.28],
  'valle-nevado': [-33.35, -70.25],
  lagunillas: [-33.68, -70.25],
  'chapa-verde': [-34.17, -70.37],
}

const CENTRO_DEFECTO = [-33.4, -70.25]
const ZOOM_DEFECTO = 9

export default function MapCard({ centros, seleccionadoId, onSelect, className = '' }) {
  const { datos: gee, estado } = useMapaGEE()
  const refContenedor = useRef(null)
  const refMapa = useRef(null)
  const refMarcadores = useRef({})

  // 1. Inicializa el mapa una sola vez (base satelital).
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
    refMapa.current = mapa
    // Leaflet necesita recalcular tamaño dentro de contenedores flex.
    setTimeout(() => mapa.invalidateSize(), 0)

    return () => {
      mapa.remove()
      refMapa.current = null
    }
  }, [])

  // 2. Agrega las capas de Earth Engine cuando llegan.
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
        {
          'Color real (Sentinel-2)': color,
          'Cobertura de nieve (NDSI ≥ 0.4)': nieve,
          'Zonas de riesgo (nieve + 30–45°)': riesgo,
        },
        { collapsed: false, position: 'topright' }
      )
      .addTo(mapa)

    if (gee.bounds) mapa.fitBounds(gee.bounds)

    return () => {
      mapa.removeControl(control)
      mapa.removeLayer(color)
      mapa.removeLayer(nieve)
      mapa.removeLayer(riesgo)
    }
  }, [gee])

  // 3. Marcadores de centros por nivel EAWS (se rehacen al cambiar datos/selección).
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
        .bindTooltip(`${centro.nombre} · Nivel ${centro.estadoActual.nivelEAWS}`, {
          direction: 'top',
        })
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

        {estado === 'ok' && gee && (
          <div className="pointer-events-none absolute bottom-2 left-2 z-[400] flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[9px] text-white/85 backdrop-blur-sm">
            <Layers className="h-3 w-3" />
            Mosaico Sentinel-2 · {gee.imagenes_usadas} imágenes desde {gee.ventana_desde}
          </div>
        )}
      </div>
    </GlassCard>
  )
}
