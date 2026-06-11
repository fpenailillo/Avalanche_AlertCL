import { Mountain } from 'lucide-react'
import HeroSection from './components/HeroSection'
import TimelineCarousel from './components/TimelineCarousel'
import ForecastCard from './components/ForecastCard'
import ProblemsCard from './components/ProblemsCard'
import SatelliteCard from './components/SatelliteCard'
import SnowpackCard from './components/SnowpackCard'
import CommunityCard from './components/CommunityCard'
import MapCard from './components/MapCard'

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-blue-900 to-sky-700">
      <div className="mx-auto max-w-5xl px-4 pb-12">
        <HeroSection />

        <TimelineCarousel />

        {/* Grid bento asimétrico */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <ProblemsCard className="md:col-span-2 lg:order-1 lg:col-span-2" />
          <ForecastCard className="md:row-span-2 lg:order-2" />
          <SatelliteCard className="lg:order-3" />
          <SnowpackCard className="lg:order-4" />
          <MapCard className="aspect-square md:aspect-auto lg:order-5" />
          <CommunityCard className="lg:order-6 lg:col-span-2" />
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
