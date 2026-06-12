import { Satellite, TrendingUp, Minus } from 'lucide-react'
import GlassCard from './GlassCard'

export default function SatelliteCard({ datos, className = '' }) {
  const enAumento = datos.tendencia === 'En aumento'
  const IconoTendencia = enAumento ? TrendingUp : Minus

  return (
    <GlassCard icon={Satellite} title="Satelital · S2" className={className}>
      <div className="flex flex-1 flex-col justify-between gap-4 text-white">
        <div>
          <div className="text-4xl font-bold tracking-tight">
            {datos.ndsi.toFixed(2)}
          </div>
          <div className="text-xs text-white/60">Índice NDSI</div>
        </div>

        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs text-white/70">
            <span>Cobertura de nieve</span>
            <span className="font-semibold text-white">{datos.coberturaPct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-white/15">
            <div
              className="h-1.5 rounded-full bg-gradient-to-r from-sky-300 to-cyan-100"
              style={{ width: `${datos.coberturaPct}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-white/50">
          <span>
            Sentinel-2 · {datos.tile}
            <br />
            {datos.fechaPasada}
          </span>
          <span
            className={`flex items-center gap-1 ${
              enAumento ? 'text-emerald-300' : 'text-white/60'
            }`}
          >
            <IconoTendencia className="h-3.5 w-3.5" />
            {datos.tendencia}
          </span>
        </div>
      </div>
    </GlassCard>
  )
}
