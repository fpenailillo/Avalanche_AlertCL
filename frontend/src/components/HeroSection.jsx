import { useState } from 'react'
import { MapPin, Wind, Thermometer, TriangleAlert, MoveVertical, CalendarDays, ChevronDown } from 'lucide-react'
import { ESCALA_EAWS } from '../data/mockData'
import EawsDangerIcon from './EawsDangerIcon'

const etiquetaFecha = (fecha) =>
  new Date(`${fecha}T12:00:00`).toLocaleDateString('es-CL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

function SelectorFecha({ fechas, fechaSeleccionada, onSeleccionarFecha }) {
  const estiloActivo = fechaSeleccionada
    ? 'border-sky-300/40 bg-sky-400/15 text-sky-100'
    : 'border-white/15 bg-white/10 text-white/80'
  return (
    <label
      className={`relative mt-1.5 flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs backdrop-blur-sm transition-colors hover:bg-white/15 ${estiloActivo}`}
    >
      <CalendarDays className="h-3.5 w-3.5 shrink-0" />
      <select
        value={fechaSeleccionada ?? ''}
        onChange={(e) => onSeleccionarFecha(e.target.value || null)}
        className="cursor-pointer appearance-none bg-transparent pr-4 outline-none [&>option]:text-slate-900"
        aria-label="Seleccionar fecha del boletín"
      >
        <option value="">Boletín más reciente</option>
        {fechas.map((fecha) => (
          <option key={fecha} value={fecha}>
            {etiquetaFecha(fecha)}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 h-3 w-3" />
    </label>
  )
}

function AnalisisTecnico({ texto }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <div className="mt-2 max-w-xl">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        className="mx-auto flex items-center gap-1 text-[11px] text-white/40 transition-colors hover:text-white/70"
      >
        {abierto ? 'Ocultar' : 'Ver'} análisis técnico del sistema
        <ChevronDown
          className={`h-3 w-3 transition-transform ${abierto ? 'rotate-180' : ''}`}
        />
      </button>
      {abierto && (
        <p className="mt-2 text-balance text-xs leading-relaxed text-white/55">
          {texto}
        </p>
      )}
    </div>
  )
}

export default function HeroSection({ centro, fechas = [], fechaSeleccionada, onSeleccionarFecha }) {
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
      {fechas.length > 0 ? (
        <SelectorFecha
          fechas={fechas}
          fechaSeleccionada={fechaSeleccionada}
          onSeleccionarFecha={onSeleccionarFecha}
        />
      ) : (
        <p className="mt-1 text-xs text-white/50">{estado.fechaBoletin}</p>
      )}
      {fechas.length > 0 && (
        <p className="mt-1 text-[11px] text-white/45">{estado.fechaBoletin}</p>
      )}
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
      {estado.descripcionTecnica && (
        <AnalisisTecnico texto={estado.descripcionTecnica} />
      )}

      <div className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-sm text-white/60">
        <span className="flex items-center gap-1.5">
          <Thermometer className="h-4 w-4" />
          {estado.temperatura}°C
        </span>
        <span className="flex items-center gap-1.5">
          <Wind className="h-4 w-4" />
          {estado.vientoKmh} km/h
        </span>
        {estado.tendencia && (
          <span className="flex items-center gap-1.5">
            Tendencia: {estado.tendencia}
          </span>
        )}
        {estado.confianza && (
          <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs">
            Confianza {estado.confianza}
          </span>
        )}
      </div>
      <p className="mt-2 text-[11px] text-white/40">{estado.validoHasta}</p>
    </header>
  )
}
