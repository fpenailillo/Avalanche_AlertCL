import { useMemo, useState } from 'react'
import { Mountain, TriangleAlert } from 'lucide-react'
import HeroSection from './components/HeroSection'
import TimelineCarousel from './components/TimelineCarousel'
import ForecastCard from './components/ForecastCard'
import ProblemsCard from './components/ProblemsCard'
import SatelliteCard from './components/SatelliteCard'
import SnowpackCard from './components/SnowpackCard'
import CommunityCard from './components/CommunityCard'
import MapCard from './components/MapCard'
import { CENTROS_LISTA, ESCALA_EAWS } from './data/mockData'
import { useBoletinActivo, useSeriesWN2, useSeriesHoras, useIndiceFechas } from './services/boletin'
import { fusionarCentros } from './services/fusion'

function BanderaChile({ className = 'h-3.5 w-5' }) {
  return (
    <svg viewBox="0 0 24 16" className={`${className} rounded-[2px] shadow`} aria-label="Bandera de Chile">
      <rect width="24" height="8" fill="#ffffff" />
      <rect y="8" width="24" height="8" fill="#d52b1e" />
      <rect width="8" height="8" fill="#0039a6" />
      <path
        d="M4 1.6 4.66 3.5l2 .03-1.6 1.2.58 1.93L4 5.5 2.36 6.66l.58-1.93-1.6-1.2 2-.03Z"
        fill="#ffffff"
      />
    </svg>
  )
}

function BrandHeader() {
  return (
    <div className="flex flex-col items-center gap-1.5 pt-6 text-center text-white">
      <div className="flex items-center gap-2">
        <Mountain className="h-5 w-5 text-white/80" />
        <BanderaChile />
        <span className="rounded-full border border-amber-300/40 bg-amber-400/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
          Beta
        </span>
      </div>
      <h1 className="text-balance text-2xl font-bold leading-snug tracking-tight sm:text-3xl">
        Riesgo de Avalanchas Chile
      </h1>
      <p className="max-w-xl text-balance text-xs text-white/60 sm:text-sm">
        Boletines EAWS por zona, generados por agentes de IA especializados
      </p>
    </div>
  )
}

function SelectorCentros({ centros, seleccionadoId, onSelect }) {
  return (
    <nav className="sticky top-3 z-10 mx-auto mt-4 flex w-fit max-w-full gap-1 overflow-x-auto rounded-full border border-white/15 bg-white/10 p-1 shadow-lg shadow-black/10 backdrop-blur-xl">
      {centros.map((centro) => {
        const activo = centro.id === seleccionadoId
        const nivel = ESCALA_EAWS[centro.estadoActual.nivelEAWS]
        return (
          <button
            key={centro.id}
            type="button"
            onClick={() => onSelect(centro.id)}
            className={`flex shrink-0 items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              activo
                ? 'bg-white/90 text-slate-900'
                : 'text-white/75 hover:bg-white/10 hover:text-white'
            }`}
          >
            {centro.nombre}
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: nivel.color }}
              title={`EAWS ${centro.estadoActual.nivelEAWS} — ${nivel.nombre}`}
            />
          </button>
        )
      })}
    </nav>
  )
}

function EstadoBoletin({ boletin, fechaSeleccionada }) {
  if (boletin.estado === 'cargando') return null

  if (boletin.estado === 'demo') {
    return (
      <p className="mx-auto mt-3 flex w-fit items-center gap-1.5 rounded-full border border-amber-300/25 bg-amber-400/10 px-3 py-1 text-[11px] text-amber-200/80 backdrop-blur-sm">
        <TriangleAlert className="h-3 w-3" />
        Boletín en línea no disponible temporalmente — mostrando datos de demostración
      </p>
    )
  }

  if (fechaSeleccionada) {
    const etiqueta = new Date(`${fechaSeleccionada}T12:00:00`).toLocaleDateString('es-CL', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
    return (
      <p className="mx-auto mt-3 flex w-fit items-center gap-1.5 rounded-full border border-sky-300/25 bg-sky-400/10 px-3 py-1 text-[11px] text-sky-200/80 backdrop-blur-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-sky-300" />
        Estás viendo el boletín histórico del {etiqueta}
      </p>
    )
  }

  const fecha = boletin.generado
    ? new Date(boletin.generado).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' })
    : null
  return (
    <p className="mx-auto mt-3 flex w-fit items-center gap-1.5 text-[11px] text-white/40">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
      Boletín en línea{fecha ? ` · actualizado ${fecha}` : ' activo'}
    </p>
  )
}

function App() {
  const [centroId, setCentroId] = useState('la-parva')
  const [fechaSeleccionada, setFechaSeleccionada] = useState(null)
  const fechasDisponibles = useIndiceFechas()
  const boletin = useBoletinActivo(fechaSeleccionada)
  const { series: seriesWN2, esDeFecha: seriesDeFecha } = useSeriesWN2(fechaSeleccionada)
  const seriesHoras = useSeriesHoras(fechaSeleccionada)

  // Fusiona el mock con el boletín y las series en línea, campo por campo
  const centros = useMemo(
    () => fusionarCentros(CENTROS_LISTA, boletin.boletines, seriesWN2, seriesHoras, fechaSeleccionada),
    [boletin.boletines, seriesWN2, seriesHoras, fechaSeleccionada]
  )

  const centro = centros.find((c) => c.id === centroId) ?? centros[0]

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-blue-900 to-sky-700">
      <div className="mx-auto max-w-5xl px-4 pb-12">
        <BrandHeader />
        <SelectorCentros centros={centros} seleccionadoId={centroId} onSelect={setCentroId} />
        <EstadoBoletin boletin={boletin} fechaSeleccionada={fechaSeleccionada} />

        <HeroSection
          centro={centro}
          fechas={fechasDisponibles}
          fechaSeleccionada={fechaSeleccionada}
          onSeleccionarFecha={setFechaSeleccionada}
        />

        <TimelineCarousel
          timeline={centro.timeline}
          esHistorico={!!fechaSeleccionada}
          fechaBase={fechaSeleccionada}
        />

        {/* Grid bento asimétrico */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <ProblemsCard
            problemas={centro.problemas}
            recomendaciones={centro.recomendaciones}
            tituloRecomendacion={centro.tituloRecomendacion}
            className="md:col-span-2 lg:order-1 lg:col-span-2"
          />
          <ForecastCard
            pronostico={centro.pronostico15}
            avisoVigente={!!fechaSeleccionada && !seriesDeFecha}
            className="md:row-span-2 lg:order-2"
          />
          <SatelliteCard datos={centro.satelital} className="lg:order-3" />
          <SnowpackCard datos={centro.topografico} className="lg:order-4" />
          <MapCard
            centros={centros}
            seleccionadoId={centroId}
            onSelect={setCentroId}
            className="aspect-square md:aspect-auto lg:order-5"
          />
          <CommunityCard datos={centro.comunidad} className="lg:order-6 lg:col-span-2" />
        </div>

        <footer className="mt-10 flex flex-col items-center gap-2 text-center text-[11px] text-white/40">
          <span className="flex items-center gap-1.5 font-semibold text-white/60">
            <Mountain className="h-3.5 w-3.5" />
            Sistema Inteligente de Predicción de Riesgo de Avalanchas para Chile
            <BanderaChile className="h-2.5 w-4" />
          </span>
          <p className="max-w-xl">
            Boletines de Seguridad Zonales mediante Coordinación de Agentes de IA
            Especializados — desarrollado como parte de la tesis de{' '}
            <strong className="text-white/60">Francisco Peñailillo</strong> para
            optar al grado de Magíster en Tecnologías de la Información de la{' '}
            <strong className="text-white/60">
              Universidad Técnica Federico Santa María (UTFSM)
            </strong>
            . Los boletines se generan de forma automática, sin revisión humana.
          </p>
          <p className="max-w-xl rounded-2xl border border-amber-300/30 bg-amber-400/10 px-4 py-2 text-amber-200/90">
            ⚠️ Mensaje de seguridad: esta es una versión beta. No utilices esta
            información para tomar decisiones en terreno ni planificar
            actividades en montaña; consulta siempre los boletines oficiales y a
            las patrullas de cada centro.
          </p>
          <p>
            Íconos estándar de niveles de peligro y problemas de avalancha ©{' '}
            <a
              href="https://www.avalanches.org/standards/"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-white/70"
            >
              EAWS
            </a>
          </p>
        </footer>
      </div>
    </div>
  )
}

export default App
