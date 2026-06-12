import { useState } from 'react'
import { Mountain } from 'lucide-react'
import HeroSection from './components/HeroSection'
import TimelineCarousel from './components/TimelineCarousel'
import ForecastCard from './components/ForecastCard'
import ProblemsCard from './components/ProblemsCard'
import SatelliteCard from './components/SatelliteCard'
import SnowpackCard from './components/SnowpackCard'
import CommunityCard from './components/CommunityCard'
import MapCard from './components/MapCard'
import { CENTROS, CENTROS_LISTA, ESCALA_EAWS } from './data/mockData'

function SelectorCentros({ seleccionadoId, onSelect }) {
  return (
    <nav className="sticky top-3 z-10 mx-auto mt-4 flex w-fit max-w-full gap-1 overflow-x-auto rounded-full border border-white/15 bg-white/10 p-1 shadow-lg shadow-black/10 backdrop-blur-xl">
      {CENTROS_LISTA.map((centro) => {
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

function App() {
  const [centroId, setCentroId] = useState('la-parva')
  const centro = CENTROS[centroId]

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-blue-900 to-sky-700">
      <div className="mx-auto max-w-5xl px-4 pb-12">
        <SelectorCentros seleccionadoId={centroId} onSelect={setCentroId} />

        <HeroSection centro={centro} />

        <TimelineCarousel timeline={centro.timeline} />

        {/* Grid bento asimétrico */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <ProblemsCard
            problemas={centro.problemas}
            className="md:col-span-2 lg:order-1 lg:col-span-2"
          />
          <ForecastCard
            pronostico={centro.pronostico15}
            className="md:row-span-2 lg:order-2"
          />
          <SatelliteCard datos={centro.satelital} className="lg:order-3" />
          <SnowpackCard datos={centro.topografico} className="lg:order-4" />
          <MapCard
            seleccionadoId={centroId}
            onSelect={setCentroId}
            className="aspect-square md:aspect-auto lg:order-5"
          />
          <CommunityCard datos={centro.comunidad} className="lg:order-6 lg:col-span-2" />
        </div>

        <footer className="mt-10 flex flex-col items-center gap-1 text-center text-[11px] text-white/40">
          <span className="flex items-center gap-1.5 font-semibold text-white/60">
            <Mountain className="h-3.5 w-3.5" />
            Avalanche_AlertCL
          </span>
          <p>
            Prueba de Concepto · Boletines EAWS generados por un sistema
            multi-agente de IA · Temporada 2026
          </p>
          <p>Datos de demostración — no usar para decisiones en terreno.</p>
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
