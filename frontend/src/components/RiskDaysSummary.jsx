import { useMemo } from 'react'
import { CalendarRange, ChevronDown } from 'lucide-react'
import GlassCard from './GlassCard'
import WeatherIcon from './WeatherIcon'
import EawsDangerIcon from './EawsDangerIcon'
import { ESCALA_EAWS } from '../data/mockData'

const ETIQUETAS = ['Hoy', 'Mañana', 'Día 3']
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// Fecha relativa legible (día + mes) para degradar cuando falta el pronóstico WN2.
const fechaRelativa = (offset) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return `${d.getDate()} ${MESES[d.getMonth()]}`
}

// Resumen simplificado del riesgo por día: hoy / mañana / día 3, cada uno con
// clima y un único nivel EAWS. La proyección granular (24/48/72 h) vive en
// TimelineCarousel, colapsada bajo el botón "Ver proyección detallada".
export default function RiskDaysSummary({ estadoActual, pronostico = [], abierto, onToggle }) {
  const dias = useMemo(() => {
    const niveles = [
      estadoActual.nivelEAWS,
      estadoActual.nivel48h ?? estadoActual.nivelEAWS,
      estadoActual.nivel72h ?? estadoActual.nivel48h ?? estadoActual.nivelEAWS,
    ]
    return niveles.map((nivelRaw, i) => {
      const clima = pronostico[i] ?? null
      const nivel = nivelRaw ?? 1
      return {
        etiqueta: ETIQUETAS[i],
        fecha: clima?.fecha ?? fechaRelativa(i),
        icono: clima?.icono ?? null,
        min: clima?.min ?? null,
        max: clima?.max ?? null,
        nivel,
        escala: ESCALA_EAWS[nivel] ?? ESCALA_EAWS[1],
      }
    })
  }, [estadoActual, pronostico])

  return (
    <GlassCard icon={CalendarRange} title="Resumen de riesgo · próximos 3 días" className="mt-4">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-3">
        {dias.map((dia) => (
          <div
            key={dia.etiqueta}
            className="flex flex-col gap-2.5 rounded-2xl bg-white/5 px-3 py-3 text-white"
          >
            <div className="text-sm font-bold uppercase tracking-wide">
              {dia.etiqueta} <span className="text-white/50">({dia.fecha})</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-white/70">
                {dia.icono && <WeatherIcon tipo={dia.icono} className="h-6 w-6 shrink-0" />}
                {dia.min != null && dia.max != null ? (
                  <span className="text-xs">
                    {dia.min}° / {dia.max}°C
                  </span>
                ) : (
                  <span className="text-[11px] text-white/40">Sin pronóstico</span>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <EawsDangerIcon nivel={dia.nivel} className="h-10 w-10 drop-shadow" />
                <span
                  className="text-xs font-bold leading-tight"
                  style={{ color: dia.escala.color }}
                >
                  Nivel {dia.nivel}:<br />
                  {dia.escala.nombre}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onToggle}
        className="mx-auto mt-4 flex items-center gap-1 text-xs font-medium text-sky-200/80 transition-colors hover:text-sky-100"
      >
        {abierto ? 'Ocultar proyección detallada' : 'Ver proyección detallada'}
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${abierto ? 'rotate-180' : ''}`}
        />
      </button>
    </GlassCard>
  )
}
