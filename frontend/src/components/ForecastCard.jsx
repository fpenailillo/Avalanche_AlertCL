import { CalendarDays, Snowflake, MoveVertical } from 'lucide-react'
import GlassCard from './GlassCard'
import WeatherIcon from './WeatherIcon'
import { PRONOSTICO_15_DIAS } from '../data/mockData'

const minGlobal = Math.min(...PRONOSTICO_15_DIAS.map((d) => d.min))
const maxGlobal = Math.max(...PRONOSTICO_15_DIAS.map((d) => d.max))
const rango = maxGlobal - minGlobal

function BarraTemp({ min, max }) {
  const izquierda = ((min - minGlobal) / rango) * 100
  const ancho = ((max - min) / rango) * 100
  return (
    <div className="relative h-1 w-full rounded-full bg-white/15">
      <div
        className="absolute h-1 rounded-full bg-gradient-to-r from-cyan-400 to-amber-300"
        style={{ left: `${izquierda}%`, width: `${ancho}%` }}
      />
    </div>
  )
}

export default function ForecastCard({ className = '' }) {
  return (
    <GlassCard
      icon={CalendarDays}
      title="Pronóstico 15 días · WeatherNext 2"
      className={className}
    >
      {/* En md+ el scroll se posiciona absoluto para no estirar las filas del grid */}
      <div className="relative min-h-0 flex-1">
        <div className="scroll-slim max-h-[30rem] divide-y divide-white/10 overflow-y-auto pr-1 md:absolute md:inset-0 md:max-h-none">
          {PRONOSTICO_15_DIAS.map((dia, i) => (
          <div key={i} className="flex items-center gap-3 py-2.5 text-white">
            <div className="w-12 shrink-0">
              <div className="text-sm font-semibold">{dia.dia}</div>
              <div className="text-[10px] text-white/50">{dia.fecha}</div>
            </div>
            <WeatherIcon tipo={dia.icono} className="h-5 w-5 shrink-0" />
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="w-8 shrink-0 text-right text-sm text-white/60">
                {dia.min}°
              </span>
              <BarraTemp min={dia.min} max={dia.max} />
              <span className="w-8 shrink-0 text-sm font-semibold">{dia.max}°</span>
            </div>
            <div className="flex w-20 shrink-0 flex-col items-end gap-0.5">
              <span
                className={`flex items-center gap-1 text-xs font-medium ${
                  dia.nieveCm > 0 ? 'text-cyan-200' : 'text-white/30'
                }`}
              >
                <Snowflake className="h-3 w-3" />
                {dia.nieveCm} cm
              </span>
              <span className="flex items-center gap-1 text-[10px] text-white/50">
                <MoveVertical className="h-3 w-3" />
                {dia.isotermaM.toLocaleString('es-CL')} m
              </span>
            </div>
          </div>
          ))}
        </div>
      </div>
      <p className="pt-3 text-[10px] text-white/40">
        Nieve acumulada e isoterma 0° por día · modelo WeatherNext 2
      </p>
    </GlassCard>
  )
}
