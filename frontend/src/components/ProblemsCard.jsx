import { TriangleAlert, MoveVertical, Compass } from 'lucide-react'
import GlassCard from './GlassCard'
import { PROBLEMAS_AVALANCHA } from '../data/mockData'
import problemNewSnow from '../assets/eaws/problem-new-snow.jpg'
import problemWindSlab from '../assets/eaws/problem-wind-slab.jpg'
import problemPersistent from '../assets/eaws/problem-persistent-weak-layer.jpg'
import problemWetSnow from '../assets/eaws/problem-wet-snow.jpg'
import problemGliding from '../assets/eaws/problem-gliding-snow.jpg'

// Íconos oficiales EAWS de problemas de avalancha (avalanches.org)
const ICONOS_PROBLEMA = {
  'new-snow': problemNewSnow,
  'wind-slab': problemWindSlab,
  'persistent-weak-layer': problemPersistent,
  'wet-snow': problemWetSnow,
  'gliding-snow': problemGliding,
}

export default function ProblemsCard({ className = '' }) {
  return (
    <GlassCard
      icon={TriangleAlert}
      title="Problemas de avalancha · EAWS"
      className={className}
    >
      <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
        {PROBLEMAS_AVALANCHA.map((problema) => (
          <div
            key={problema.id}
            className="flex items-start gap-3 rounded-2xl bg-white/5 p-3 text-white"
          >
            <img
              src={ICONOS_PROBLEMA[problema.id]}
              alt={`Ícono EAWS: ${problema.nombre}`}
              className="h-14 w-14 shrink-0 rounded-xl border border-white/20"
              draggable={false}
            />
            <div className="min-w-0">
              <div className="text-sm font-semibold">{problema.nombre}</div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-white/60">
                <span className="flex items-center gap-1">
                  <MoveVertical className="h-3 w-3" />
                  {problema.cotas}
                </span>
                <span className="flex items-center gap-1">
                  <Compass className="h-3 w-3" />
                  {problema.orientaciones}
                </span>
              </div>
              <p className="mt-1 text-xs leading-snug text-white/70">
                {problema.detalle}
              </p>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
