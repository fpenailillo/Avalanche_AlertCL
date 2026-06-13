import { CalendarDays, Snowflake, MoveVertical, TriangleAlert } from 'lucide-react'
import GlassCard from './GlassCard'
import WeatherIcon from './WeatherIcon'

// Alerta de nevada intensa en el mediano plazo: más allá del horizonte del
// boletín EAWS (>3 días) con escenario p95 del ensemble sobre 20 cm/día.
const HORIZONTE_ALERTA_DIAS = 3
const UMBRAL_NIEVE_P95_CM = 20

const tieneAlertaNieve = (dia, i) =>
  i > HORIZONTE_ALERTA_DIAS && dia.nieveP95 != null && dia.nieveP95 > UMBRAL_NIEVE_P95_CM

function BarraTemp({ min, max, minGlobal, rango }) {
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

export default function ForecastCard({ pronostico, avisoVigente = false, className = '' }) {
  const minGlobal = Math.min(...pronostico.map((d) => d.min))
  const maxGlobal = Math.max(...pronostico.map((d) => d.max))
  const rango = maxGlobal - minGlobal
  const esReal = pronostico.some((d) => d.real)

  // Días con alerta de nevada intensa (mediano plazo) para el resumen superior
  const diasAlerta = pronostico.filter(tieneAlertaNieve)
  const pico = diasAlerta.reduce(
    (max, d) => (d.nieveP95 > (max?.nieveP95 ?? 0) ? d : max),
    null
  )

  return (
    <GlassCard
      icon={CalendarDays}
      title={`Pronóstico ${pronostico.length} días · WeatherNext 2`}
      className={className}
    >
      {avisoVigente && (
        <p className="mb-2 rounded-xl border border-sky-300/25 bg-sky-400/10 px-3 py-1.5 text-[10px] leading-snug text-sky-200/80">
          Pronóstico vigente desde hoy — sin archivo WN2 para la fecha
          histórica seleccionada.
        </p>
      )}
      {pico && (
        <p className="mb-2 flex items-center gap-1.5 rounded-xl border border-amber-300/30 bg-amber-400/10 px-3 py-1.5 text-[10px] leading-snug text-amber-200/90">
          <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
          <span>
            Atención: nevada intensa prevista — hasta <strong>{pico.nieveP95} cm</strong>{' '}
            (p95) el {pico.dia} {pico.fecha}
            {diasAlerta.length > 1 ? ` · ${diasAlerta.length} días sobre ${UMBRAL_NIEVE_P95_CM} cm` : ''}
          </span>
        </p>
      )}
      {/* En md+ el scroll se posiciona absoluto para no estirar las filas del grid */}
      <div className="relative min-h-0 flex-1">
        <div className="scroll-slim max-h-[30rem] divide-y divide-white/10 overflow-y-auto pr-1 md:absolute md:inset-0 md:max-h-none">
          {pronostico.map((dia, i) => {
            const alerta = tieneAlertaNieve(dia, i)
            return (
              <div
                key={i}
                className={`flex items-center gap-3 py-2.5 text-white ${
                  alerta ? 'rounded-lg bg-amber-400/10 px-1' : ''
                }`}
              >
                <div className="w-12 shrink-0">
                  <div className="flex items-center gap-1 text-sm font-semibold">
                    {dia.dia}
                    {alerta && (
                      <TriangleAlert className="h-3 w-3 text-amber-300" title="Nevada intensa prevista" />
                    )}
                  </div>
                  <div className="text-[10px] text-white/50">{dia.fecha}</div>
                </div>
                <WeatherIcon tipo={dia.icono} className="h-5 w-5 shrink-0" />
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span className="w-8 shrink-0 text-right text-sm text-white/60">
                    {dia.min}°
                  </span>
                  <BarraTemp
                    min={dia.min}
                    max={dia.max}
                    minGlobal={minGlobal}
                    rango={rango}
                  />
                  <span className="w-8 shrink-0 text-sm font-semibold">{dia.max}°</span>
                </div>
                <div className="flex w-20 shrink-0 flex-col items-end gap-0.5">
                  <span
                    className={`flex items-center gap-1 text-xs font-medium ${
                      alerta ? 'text-amber-300' : dia.nieveCm > 0 ? 'text-cyan-200' : 'text-white/30'
                    }`}
                  >
                    <Snowflake className="h-3 w-3" />
                    {dia.nieveCm} cm
                  </span>
                  {dia.isotermaM != null ? (
                    <span className="flex items-center gap-1 text-[10px] text-white/50">
                      <MoveVertical className="h-3 w-3" />
                      {dia.isotermaM.toLocaleString('es-CL')} m
                    </span>
                  ) : dia.nieveP95 != null ? (
                    <span
                      className={`text-[10px] ${alerta ? 'font-semibold text-amber-200' : 'text-white/50'}`}
                    >
                      p95: {dia.nieveP95} cm
                    </span>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <p className="pt-3 text-[10px] text-white/40">
        {esReal
          ? 'Ensemble WeatherNext 2: T° mín/máx p05–p95, nieve mediana y p95 · datos reales'
          : 'Nieve acumulada e isoterma 0° por día · demo'}
      </p>
    </GlassCard>
  )
}
