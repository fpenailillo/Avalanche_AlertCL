import { MapPin, Wind, Thermometer, TriangleAlert } from 'lucide-react'
import { ESTADO_ACTUAL, ESCALA_EAWS } from '../data/mockData'
import EawsDangerIcon from './EawsDangerIcon'

export default function HeroSection() {
  const nivel = ESCALA_EAWS[ESTADO_ACTUAL.nivelEAWS]

  return (
    <header className="flex flex-col items-center px-4 pt-12 pb-8 text-center text-white">
      <div className="flex items-center gap-1.5 text-sm font-medium text-white/70">
        <MapPin className="h-4 w-4" />
        {ESTADO_ACTUAL.zona}
      </div>
      <h1 className="mt-1 text-4xl font-semibold tracking-tight">
        {ESTADO_ACTUAL.ubicacion}
      </h1>
      <p className="mt-1 text-xs text-white/50">{ESTADO_ACTUAL.fechaBoletin}</p>

      <div className="mt-6 flex flex-col items-center">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-white/50">
          Peligro de avalanchas · EAWS
        </span>
        <div className="mt-2 flex items-center gap-4">
          <EawsDangerIcon
            nivel={ESTADO_ACTUAL.nivelEAWS}
            className="h-20 w-20 drop-shadow-lg sm:h-24 sm:w-24"
          />
          <div
            className="text-6xl font-bold tracking-tight sm:text-7xl"
            style={{ color: nivel.color, textShadow: '0 2px 24px rgba(0,0,0,0.35)' }}
          >
            Nivel {ESTADO_ACTUAL.nivelEAWS}
          </div>
        </div>
        <span
          className="mt-3 inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-bold"
          style={{ backgroundColor: nivel.color, color: nivel.texto }}
        >
          <TriangleAlert className="h-4 w-4" />
          {nivel.nombre}
        </span>
      </div>

      <p className="mt-6 max-w-xl text-balance text-sm leading-relaxed text-white/80 sm:text-base">
        {ESTADO_ACTUAL.descripcionIA}
      </p>

      <div className="mt-4 flex items-center gap-5 text-sm text-white/60">
        <span className="flex items-center gap-1.5">
          <Thermometer className="h-4 w-4" />
          {ESTADO_ACTUAL.temperatura}°C
        </span>
        <span className="flex items-center gap-1.5">
          <Wind className="h-4 w-4" />
          {ESTADO_ACTUAL.vientoKmh} km/h NO
        </span>
      </div>
      <p className="mt-2 text-[11px] text-white/40">{ESTADO_ACTUAL.validoHasta}</p>
    </header>
  )
}
