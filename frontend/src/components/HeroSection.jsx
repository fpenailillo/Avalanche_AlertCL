import { MapPin, Wind, Thermometer, TriangleAlert, MoveVertical } from 'lucide-react'
import { ESCALA_EAWS } from '../data/mockData'
import EawsDangerIcon from './EawsDangerIcon'

export default function HeroSection({ centro }) {
  const estado = centro.estadoActual
  const nivel = ESCALA_EAWS[estado.nivelEAWS]

  return (
    <header className="flex flex-col items-center px-4 pt-6 pb-8 text-center text-white">
      <div className="flex items-center gap-1.5 text-sm font-medium text-white/70">
        <MapPin className="h-4 w-4" />
        {centro.zona}
      </div>
      <h2 className="mt-1 text-4xl font-semibold tracking-tight">
        {centro.nombre}
      </h2>
      <p className="mt-1 text-xs text-white/50">{estado.fechaBoletin}</p>
      <p className="mt-0.5 flex items-center gap-1 text-[11px] text-white/40">
        <MoveVertical className="h-3 w-3" />
        {centro.elevacion} · exposición {centro.exposicion}
      </p>

      <div className="mt-6 flex flex-col items-center">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-white/50">
          Peligro de avalanchas · EAWS
        </span>
        <div className="mt-2 flex items-center gap-4">
          <EawsDangerIcon
            nivel={estado.nivelEAWS}
            className="h-20 w-20 drop-shadow-lg sm:h-24 sm:w-24"
          />
          <div
            className="text-6xl font-bold tracking-tight sm:text-7xl"
            style={{ color: nivel.color, textShadow: '0 2px 24px rgba(0,0,0,0.35)' }}
          >
            Nivel {estado.nivelEAWS}
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
        {estado.descripcionIA}
      </p>

      <div className="mt-4 flex items-center gap-5 text-sm text-white/60">
        <span className="flex items-center gap-1.5">
          <Thermometer className="h-4 w-4" />
          {estado.temperatura}°C
        </span>
        <span className="flex items-center gap-1.5">
          <Wind className="h-4 w-4" />
          {estado.vientoKmh} km/h NO
        </span>
      </div>
      <p className="mt-2 text-[11px] text-white/40">{estado.validoHasta}</p>
    </header>
  )
}
