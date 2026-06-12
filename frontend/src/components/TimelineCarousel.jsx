import { Clock } from 'lucide-react'
import GlassCard from './GlassCard'
import WeatherIcon from './WeatherIcon'
import { ESCALA_EAWS } from '../data/mockData'

export default function TimelineCarousel({ timeline }) {
  return (
    <GlassCard icon={Clock} title="Evolución del riesgo · próximas 72 h">
      <div className="scroll-slim -mx-1 flex snap-x snap-mandatory gap-1 overflow-x-auto pb-1">
        {timeline.map((punto, i) => {
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
