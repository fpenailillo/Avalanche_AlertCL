import { Users } from 'lucide-react'
import GlassCard from './GlassCard'

export default function CommunityCard({ datos, className = '' }) {
  return (
    <GlassCard icon={Users} title="Comunidad · S4" className={className}>
      <div className="flex flex-1 flex-col gap-3 text-white">
        <p className="text-sm leading-relaxed text-white/85">{datos.resumenNLP}</p>

        <ul className="space-y-2">
          {datos.reportes.map((reporte, i) => (
            <li key={i} className="rounded-xl bg-white/5 px-3 py-2 text-xs">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-semibold">{reporte.autor}</span>
                <span className="shrink-0 text-[10px] text-white/40">
                  {reporte.hace}
                </span>
              </div>
              <p className="mt-0.5 text-white/70">{reporte.texto}</p>
            </li>
          ))}
        </ul>

        <p className="mt-auto text-[10px] text-white/40">
          Resumen NLP de {datos.totalReportes48h} reportes
          {datos.tipoAludPredominante ? ` · alud predominante: ${datos.tipoAludPredominante}` : ''}
          {datos.real ? ' · datos reales' : ' · demo'}
        </p>
      </div>
    </GlassCard>
  )
}
