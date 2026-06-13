import { Clock } from 'lucide-react'
import GlassCard from './GlassCard'
import WeatherIcon from './WeatherIcon'
import { ESCALA_EAWS } from '../data/mockData'

const DIAS_ABBR = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

// Fecha de referencia del boletín: la seleccionada en modo histórico
// ("YYYY-MM-DD") o el día actual en el boletín vigente.
function fechaReferenciaDate(fechaBase) {
  if (fechaBase) {
    const [y, m, d] = fechaBase.split('-').map(Number)
    return new Date(y, m - 1, d)
  }
  return new Date()
}

// Etiqueta del día de la semana a N días de la fecha de referencia.
function etiquetaDia(base, offsetDias) {
  const d = new Date(base)
  d.setDate(d.getDate() + offsetDias)
  return DIAS_ABBR[d.getDay()]
}

export default function TimelineCarousel({ timeline, esHistorico = false, fechaBase = null }) {
  // Reemplaza las etiquetas estáticas de día por el día real según la fecha
  // del boletín. El 1er marcador es +1 día, el 2º +2 días.
  const base = fechaReferenciaDate(fechaBase)
  const puntos = timeline.map((p, i) => {
    if (!p.etiqueta) return p
    const offsetDias = timeline.slice(0, i + 1).filter((q) => q.etiqueta).length
    return { ...p, etiqueta: etiquetaDia(base, offsetDias) }
  })

  return (
    <GlassCard
      icon={Clock}
      title={
        esHistorico
          ? 'Evolución del riesgo · 24/48/72 h desde el boletín'
          : 'Evolución del riesgo · próximas 72 h'
      }
    >
      <div className="scroll-slim -mx-1 flex snap-x snap-mandatory gap-1 overflow-x-auto pb-1">
        {puntos.map((punto, i) => {
          const nivel = ESCALA_EAWS[punto.nivel]
          return (
            <div
              key={i}
              className="flex min-w-[64px] snap-start flex-col items-center gap-2 rounded-2xl px-2 py-3 text-white transition-colors hover:bg-white/10"
            >
              <span className="text-xs font-medium text-white/70">
                {punto.etiqueta ? (
                  <span className="font-bold text-white">{punto.etiqueta}</span>
                ) : (
                  punto.hora
                )}
              </span>
              <WeatherIcon tipo={punto.icono} />
              <span className="text-sm font-semibold">{punto.temp}°</span>
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                style={{ backgroundColor: nivel.color, color: nivel.texto }}
                title={`EAWS ${punto.nivel} — ${nivel.nombre}`}
              >
                {punto.nivel}
              </span>
            </div>
          )
        })}
      </div>
    </GlassCard>
  )
}
