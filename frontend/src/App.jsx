import { useMemo, useState } from 'react'
import { Mountain, TriangleAlert, BookOpen, MapPin, ChevronDown } from 'lucide-react'
import HeroSection from './components/HeroSection'
import RiskDaysSummary from './components/RiskDaysSummary'
import TimelineCarousel from './components/TimelineCarousel'
import ForecastCard from './components/ForecastCard'
import ProblemsCard from './components/ProblemsCard'
import SatelliteCard from './components/SatelliteCard'
import SnowpackCard from './components/SnowpackCard'
import CommunityCard from './components/CommunityCard'
import MapCard from './components/MapCard'
import { CENTROS_LISTA, ESCALA_EAWS } from './data/mockData'
import {
  useBoletinActivo,
  useSeriesWN2,
  useSeriesHoras,
  useObservaciones,
  useIndiceFechas,
} from './services/boletin'
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
      <h1 className="text-balance text-2xl font-bold uppercase leading-snug tracking-tight sm:text-3xl">
        Riesgos de Avalanchas - Chile
      </h1>
      <p className="max-w-xl text-balance text-xs text-white/60 sm:text-sm">
        Boletines basados en la metodología de EAWS por zonas, generados por
        agentes de IA especializados en datos satelitales, topográficos,
        climatológicos y conocimiento humano experto.
      </p>
      <a
        href="https://www.avalanches.org/wp-content/uploads/2022/09/Escala_europea_peligro_aludes_EAWS.pdf"
        target="_blank"
        rel="noreferrer"
        className="mt-1 inline-flex items-center gap-1 text-[11px] text-white/60 underline underline-offset-2 transition-colors hover:text-white/90"
      >
        <BookOpen className="h-3 w-3" />
        Metodología · Escala europea de peligro de aludes (EAWS)
      </a>
    </div>
  )
}

function SelectorCentros({ centros, seleccionadoId, onSelect }) {
  const seleccionado = centros.find((c) => c.id === seleccionadoId) ?? centros[0]
  const nivelSel = ESCALA_EAWS[seleccionado.estadoActual.nivelEAWS]

  // Agrupa los centros por zona preservando el orden geográfico norte → sur
  const grupos = []
  const indice = new Map()
  for (const c of centros) {
    if (!indice.has(c.zona)) {
      indice.set(c.zona, grupos.length)
      grupos.push({ zona: c.zona, centros: [] })
    }
    grupos[indice.get(c.zona)].centros.push(c)
  }

  return (
    <div className="sticky top-3 z-10 mx-auto mt-4 flex w-fit max-w-full justify-center">
      <label className="relative flex cursor-pointer items-center gap-2 rounded-full border border-white/15 bg-white/10 py-2 pl-4 pr-3 text-sm text-white shadow-lg shadow-black/10 backdrop-blur-xl transition-colors hover:bg-white/15">
        <MapPin className="h-4 w-4 shrink-0 text-white/70" />
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: nivelSel.color }}
          title={`EAWS ${seleccionado.estadoActual.nivelEAWS} — ${nivelSel.nombre}`}
        />
        <select
          value={seleccionadoId}
          onChange={(e) => onSelect(e.target.value)}
          className="cursor-pointer appearance-none bg-transparent pr-5 font-medium outline-none [&>optgroup]:text-slate-900 [&>optgroup>option]:text-slate-900"
          aria-label="Seleccionar centro de montaña"
        >
          {grupos.map((g) => (
            <optgroup key={g.zona} label={g.zona}>
              {g.centros.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 h-3.5 w-3.5 text-white/70" />
      </label>
    </div>
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
  const [verProyeccion, setVerProyeccion] = useState(false)
  const fechasDisponibles = useIndiceFechas()
  const boletin = useBoletinActivo(fechaSeleccionada)
  const { series: seriesWN2, esDeFecha: seriesDeFecha } = useSeriesWN2(fechaSeleccionada)
  const seriesHoras = useSeriesHoras(fechaSeleccionada)
  const observaciones = useObservaciones()

  // Fusiona el mock con el boletín y las series en línea, campo por campo
  const centros = useMemo(
    () =>
      fusionarCentros(
        CENTROS_LISTA,
        boletin.boletines,
        seriesWN2,
        seriesHoras,
        observaciones,
        fechaSeleccionada
      ),
    [boletin.boletines, seriesWN2, seriesHoras, observaciones, fechaSeleccionada]
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

        <RiskDaysSummary
          estadoActual={centro.estadoActual}
          pronostico={centro.pronostico15}
          abierto={verProyeccion}
          onToggle={() => setVerProyeccion((v) => !v)}
        />

        {verProyeccion && (
          <TimelineCarousel
            timeline={centro.timeline}
            esHistorico={!!fechaSeleccionada}
            fechaBase={fechaSeleccionada}
          />
        )}

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
          <CommunityCard
            datos={centro.comunidad}
            centroNombre={centro.nombre}
            className="lg:order-6 lg:col-span-2"
          />
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
            ⚠️ Recuerda: esta es una versión beta. Por tu seguridad, no la uses
            para tomar decisiones en terreno ni planificar tus salidas a la
            montaña; consulta siempre la información oficial. Lleva siempre tu
            equipo de seguridad y capacítate en su uso de acuerdo con las
            actividades que realices. ¿Tienes comentarios, dudas o ideas para
            mejorar? Escríbenos a{' '}
            <a
              href="mailto:fpenailillo@usm.cl"
              className="font-medium underline hover:text-amber-100"
            >
              fpenailillo@usm.cl
            </a>
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
          <img
            src="https://visitor-badge.laobi.icu/badge?page_id=fpenailillo.avalanche-alertcl"
            alt="Contador de visitas"
            className="h-5 opacity-70"
          />
        </footer>
      </div>
    </div>
  )
}

export default App
