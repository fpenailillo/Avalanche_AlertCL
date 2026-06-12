import { Satellite, TrendingUp, Minus, CheckCircle2 } from 'lucide-react'
import GlassCard from './GlassCard'

function VistaReal({ datos }) {
  const scorePct = datos.scoreAnomalia != null ? Math.round(datos.scoreAnomalia * 100) : null
  return (
    <div className="flex flex-1 flex-col justify-between gap-4 text-white">
      <div>
        <div className="text-3xl font-bold tracking-tight">{datos.estadoVit}</div>
        <div className="text-xs text-white/60">Análisis ViT del manto (Sentinel-2)</div>
      </div>

      {scorePct != null && (
        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs text-white/70">
            <span>Score de anomalía</span>
            <span className="font-semibold text-white">{scorePct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-white/15">
            <div
              className="h-1.5 rounded-full bg-gradient-to-r from-emerald-300 to-amber-300"
              style={{ width: `${Math.max(scorePct, 2)}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] text-white/50">
        <span>
          Boletín: {datos.fechaPasada}
          <br />
          Pipeline S2 en vivo
        </span>
        {datos.datosDisponibles && (
          <span className="flex items-center gap-1 text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Datos disponibles
          </span>
        )}
      </div>
    </div>
  )
}

function VistaDemo({ datos }) {
  const enAumento = datos.tendencia === 'En aumento'
  const IconoTendencia = enAumento ? TrendingUp : Minus
  return (
    <div className="flex flex-1 flex-col justify-between gap-4 text-white">
      <div>
        <div className="text-4xl font-bold tracking-tight">{datos.ndsi.toFixed(2)}</div>
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
  )
}

export default function SatelliteCard({ datos, className = '' }) {
  return (
    <GlassCard icon={Satellite} title="Satelital · S2" className={className}>
      {datos.real ? <VistaReal datos={datos} /> : <VistaDemo datos={datos} />}
    </GlassCard>
  )
}
