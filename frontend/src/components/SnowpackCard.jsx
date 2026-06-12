import { Layers, ShieldCheck, ShieldAlert } from 'lucide-react'
import GlassCard from './GlassCard'

export default function SnowpackCard({ datos, className = '' }) {
  const IconoEstado = datos.estable ? ShieldCheck : ShieldAlert
  const colorEstado = datos.estable ? 'text-emerald-300' : 'text-amber-300'

  return (
    <GlassCard icon={Layers} title="Manto de nieve · S1" className={className}>
      <div className="flex flex-1 flex-col justify-between gap-4 text-white">
        <div className="flex items-center gap-2">
          <IconoEstado className={`h-8 w-8 ${colorEstado}`} />
          <div>
            <div className="text-2xl font-bold tracking-tight">
              {datos.estadoManto}
            </div>
            <div className="text-xs text-white/60">Modelo físico PINN</div>
          </div>
        </div>

        <dl className="space-y-2 text-xs">
          <div className="flex justify-between">
            <dt className="text-white/60">Profundidad media</dt>
            <dd className="font-semibold">{datos.profundidadCm} cm</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-white/60">Capa débil</dt>
            <dd className={`font-semibold ${colorEstado}`}>{datos.capaDebil}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-white/60">Confianza</dt>
            <dd className="font-semibold">{Math.round(datos.confianza * 100)}%</dd>
          </div>
        </dl>

        <p className="text-[10px] text-white/40">
          Última corrida: {datos.ultimaCorrida}
        </p>
      </div>
    </GlassCard>
  )
}
