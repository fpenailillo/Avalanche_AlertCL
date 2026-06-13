import { useState } from 'react'
import { Users, MessageSquarePlus, Camera } from 'lucide-react'
import GlassCard from './GlassCard'
import ObservacionModal from './ObservacionModal'

export default function CommunityCard({ datos, centroNombre, className = '' }) {
  const [modalAbierto, setModalAbierto] = useState(false)
  const reportes = datos.reportes ?? []
  const vacio = reportes.length === 0

  return (
    <GlassCard icon={Users} title="Comunidad · S4" className={className}>
      <div className="flex flex-1 flex-col gap-3 text-white">
        {datos.resumenNLP && (
          <p className="text-sm leading-relaxed text-white/85">{datos.resumenNLP}</p>
        )}

        {vacio ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl bg-white/5 px-4 py-6 text-center">
            <Users className="h-7 w-7 text-white/30" />
            <p className="text-sm text-white/70">Aún no hay observaciones recientes</p>
            <p className="text-xs text-white/45">
              Sé el primero en reportar el estado de la nieve en {centroNombre ?? 'este centro'}.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {reportes.map((reporte, i) => (
              <li key={i} className="rounded-xl bg-white/5 px-3 py-2 text-xs">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold">{reporte.autor}</span>
                  <span className="shrink-0 text-[10px] text-white/40">{reporte.hace}</span>
                </div>
                <p className="mt-0.5 flex items-start gap-1 text-white/70">
                  {reporte.tieneFotos && <Camera className="mt-0.5 h-3 w-3 shrink-0 text-white/40" />}
                  <span>{reporte.texto}</span>
                </p>
              </li>
            ))}
          </ul>
        )}

        <button
          type="button"
          onClick={() => setModalAbierto(true)}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          Reportar una observación
        </button>

        {modalAbierto && (
          <ObservacionModal centroNombre={centroNombre} onCerrar={() => setModalAbierto(false)} />
        )}

        <p className="mt-auto text-[10px] text-white/40">
          {vacio
            ? `Observaciones de la comunidad · ${datos.real ? 'en vivo' : 'demo'}`
            : `${reportes.length} observación${reportes.length === 1 ? '' : 'es'} de la comunidad · ${datos.real ? 'en vivo' : 'demo'}`}
        </p>
      </div>
    </GlassCard>
  )
}
