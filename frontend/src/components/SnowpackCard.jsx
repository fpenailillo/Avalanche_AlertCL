import { Layers, ShieldCheck, ShieldAlert } from 'lucide-react'
import GlassCard from './GlassCard'

// Interpreta el Factor de Seguridad (Mohr-Coulomb) del PINN en lenguaje claro.
// FS = resistencia del manto / esfuerzo de corte. >1 estable, <1 falla.
function interpretarFS(fs) {
  if (fs == null) return null
  const v = fs.toFixed(2)
  if (fs < 1.0)
    return {
      label: 'Inestable',
      clase: 'text-rose-300',
      texto: `El manto resiste solo ${v}× el esfuerzo de corte: bajo 1.0 hay riesgo de fractura.`,
    }
  if (fs < 1.3)
    return {
      label: 'Marginal',
      clase: 'text-amber-300',
      texto: `Resiste ${v}× el esfuerzo de corte, cerca del umbral crítico (1.0).`,
    }
  if (fs < 1.5)
    return {
      label: 'Estable',
      clase: 'text-emerald-300',
      texto: `Resiste ${v}× el esfuerzo de corte, por encima del umbral de falla (1.0).`,
    }
  return {
    label: 'Muy estable',
    clase: 'text-emerald-300',
    texto: `Resiste ${v}× el esfuerzo de corte: manto cohesivo, muy sobre el umbral (1.0).`,
  }
}

// Posición del marcador en la escala 0–2.5 (umbral crítico en 1.0 → 40%).
const FS_MAX = 2.5
const UMBRAL_PCT = (1.0 / FS_MAX) * 100

export default function SnowpackCard({ datos, className = '' }) {
  const IconoEstado = datos.estable ? ShieldCheck : ShieldAlert
  const colorEstado = datos.estable ? 'text-emerald-300' : 'text-amber-300'
  const fs = datos.factorSeguridad != null ? Number(datos.factorSeguridad) : null
  const interp = interpretarFS(fs)
  const posPct = fs != null ? Math.min((fs / FS_MAX) * 100, 100) : null

  return (
    <GlassCard icon={Layers} title="Manto de nieve · S1" className={className}>
      <div className="flex flex-1 flex-col justify-between gap-4 text-white">
        <div className="flex items-center gap-2">
          <IconoEstado className={`h-8 w-8 ${colorEstado}`} />
          <div>
            <div className="text-2xl font-bold tracking-tight">{datos.estadoManto}</div>
            <div className="text-xs text-white/60">
              Modelo físico PINN · simula la estabilidad del manto
            </div>
          </div>
        </div>

        {fs != null && (
          <div>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span
                className="text-white/70"
                title="Mohr-Coulomb: razón entre la resistencia del manto y el esfuerzo de corte."
              >
                Factor de seguridad
              </span>
              <span className="font-semibold">
                {fs.toFixed(2)}
                {interp && <span className={`ml-2 ${interp.clase}`}>{interp.label}</span>}
              </span>
            </div>

            {/* Escala con el umbral crítico (1.0) marcado */}
            <div className="relative h-2 w-full rounded-full bg-gradient-to-r from-rose-400/70 via-amber-300/70 to-emerald-400/80">
              <div
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-slate-900 bg-white shadow"
                style={{ left: `${posPct}%` }}
              />
              <div
                className="absolute top-0 h-2 w-px bg-slate-900/70"
                style={{ left: `${UMBRAL_PCT}%` }}
              />
            </div>
            <div className="mt-0.5 flex justify-between text-[9px] text-white/40">
              <span>Inestable</span>
              <span>Umbral 1.0</span>
              <span>Muy estable</span>
            </div>

            {interp && <p className="mt-1.5 text-[11px] leading-snug text-white/65">{interp.texto}</p>}
          </div>
        )}

        <p className="text-[10px] text-white/40">
          {datos.real ? 'Pipeline S1 en vivo · ' : ''}Última corrida: {datos.ultimaCorrida}
          {datos.real ? '' : ' · demo'}
        </p>
      </div>
    </GlassCard>
  )
}
