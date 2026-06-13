import { Satellite, TrendingUp, Minus, CheckCircle2 } from 'lucide-react'
import GlassCard from './GlassCard'

// Interpreta el score de anomalía del análisis ViT (0–1) en lenguaje claro.
// El ViT compara la superficie actual del manto con patrones normales.
function interpretarAnomalia(pct) {
  if (pct == null) return null
  if (pct < 10)
    return { clase: 'text-emerald-300', texto: 'Sin anomalías detectadas en la superficie del manto.' }
  if (pct < 30)
    return { clase: 'text-emerald-200', texto: 'Anomalía leve en la superficie del manto.' }
  if (pct < 60)
    return { clase: 'text-amber-300', texto: 'Anomalía moderada: cambios superficiales detectados.' }
  return { clase: 'text-rose-300', texto: 'Anomalía marcada: posibles signos de inestabilidad.' }
}

function VistaReal({ datos }) {
  const scorePct = datos.scoreAnomalia != null ? Math.round(datos.scoreAnomalia * 100) : null
  const interp = interpretarAnomalia(scorePct)
  return (
    <div className="flex flex-1 flex-col justify-between gap-4 text-white">
      <div>
        <div className="text-3xl font-bold tracking-tight">{datos.estadoVit}</div>
        <div className="text-xs text-white/60">
          Vision Transformer (ViT) sobre imágenes Sentinel-2
        </div>
      </div>

      {scorePct != null && (
        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs text-white/70">
            <span title="Cuánto se desvía la superficie del manto respecto de patrones normales (0 % = normal).">
              Score de anomalía superficial
            </span>
            <span className="font-semibold text-white">{scorePct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-white/15">
            <div
              className="h-1.5 rounded-full bg-gradient-to-r from-emerald-300 via-amber-300 to-rose-400"
              style={{ width: `${Math.max(scorePct, 2)}%` }}
            />
          </div>
          {interp && <p className={`mt-1.5 text-[11px] leading-snug ${interp.clase}`}>{interp.texto}</p>}
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] text-white/50">
        <span>
          Pipeline S2 en vivo
          <br />
          Boletín: {datos.fechaPasada}
        </span>
        {datos.datosDisponibles && (
          <span
            className="flex items-center gap-1 text-emerald-300"
            title="Había imagen Sentinel-2 disponible para el análisis."
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Imagen disponible
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
