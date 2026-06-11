import { Layers, ShieldCheck } from 'lucide-react'
import GlassCard from './GlassCard'
import { TOPOGRAFICO_S1 } from '../data/mockData'

export default function SnowpackCard({ className = '' }) {
  return (
    <GlassCard icon={Layers} title="Manto de nieve · S1" className={className}>
      <div className="flex flex-1 flex-col justify-between gap-4 text-white">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-8 w-8 text-emerald-300" />
          <div>
            <div className="text-2xl font-bold tracking-tight">
              {TOPOGRAFICO_S1.estadoManto}
            </div>
            <div className="text-xs text-white/60">Modelo físico PINN</div>
          </div>
        </div>

        <dl className="space-y-2 text-xs">
          <div className="flex justify-between">
            <dt className="text-white/60">Profundidad media</dt>
            <dd className="font-semibold">{TOPOGRAFICO_S1.profundidadCm} cm</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-white/60">Capa débil</dt>
            <dd className="font-semibold text-emerald-300">
              {TOPOGRAFICO_S1.capaDebil}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-white/60">Confianza</dt>
            <dd className="font-semibold">
              {Math.round(TOPOGRAFICO_S1.confianza * 100)}%
            </dd>
          </div>
        </dl>

        <p className="text-[10px] text-white/40">
          Última corrida: {TOPOGRAFICO_S1.ultimaCorrida}
        </p>
      </div>
    </GlassCard>
  )
}
