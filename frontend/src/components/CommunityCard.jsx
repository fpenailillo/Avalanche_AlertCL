import { Users, MessageSquarePlus } from 'lucide-react'
import GlassCard from './GlassCard'

// Destino del reporte de observaciones. A futuro se reemplaza por la URL del
// formulario web; por ahora abre un correo al equipo de la tesis.
const URL_REPORTE =
  'mailto:Fpenailillom@correo.uss.cl?subject=Observaci%C3%B3n%20de%20terreno%20-%20Avalanche%20AlertCL'

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

        <a
          href={URL_REPORTE}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          Reportar una observación
        </a>

        <p className="mt-auto text-[10px] text-white/40">
          Resumen NLP de {datos.totalReportes48h} reportes
          {datos.tipoAludPredominante ? ` · alud predominante: ${datos.tipoAludPredominante}` : ''}
          {datos.real ? ' · datos reales' : ' · demo'}
        </p>
      </div>
    </GlassCard>
  )
}
