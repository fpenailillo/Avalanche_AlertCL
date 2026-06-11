import { Map, Mountain } from 'lucide-react'
import GlassCard from './GlassCard'
import { ESCALA_EAWS } from '../data/mockData'

export default function MapCard({ className = '' }) {
  return (
    <GlassCard icon={Map} title="Mapa de zonas EAWS" className={className}>
      <div className="relative min-h-44 flex-1 overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-900 via-blue-800 to-sky-600">
        {/* Cordillera estilizada */}
        <svg
          viewBox="0 0 400 200"
          preserveAspectRatio="none"
          className="absolute inset-x-0 bottom-0 h-3/4 w-full"
        >
          <polygon
            points="0,200 70,90 130,150 200,40 270,130 330,70 400,200"
            fill="rgba(255,255,255,0.18)"
          />
          <polygon
            points="0,200 100,130 180,170 260,90 340,160 400,120 400,200"
            fill="rgba(255,255,255,0.30)"
          />
          {/* Zonas EAWS sobre las laderas */}
          <circle cx="200" cy="70" r="14" fill={ESCALA_EAWS[3].color} opacity="0.9" />
          <circle cx="120" cy="140" r="12" fill={ESCALA_EAWS[2].color} opacity="0.9" />
          <circle cx="300" cy="125" r="12" fill={ESCALA_EAWS[1].color} opacity="0.9" />
          <text x="200" y="75" textAnchor="middle" fontSize="13" fontWeight="bold" fill={ESCALA_EAWS[3].texto}>3</text>
          <text x="120" y="145" textAnchor="middle" fontSize="12" fontWeight="bold" fill={ESCALA_EAWS[2].texto}>2</text>
          <text x="300" y="130" textAnchor="middle" fontSize="12" fontWeight="bold" fill={ESCALA_EAWS[1].texto}>1</text>
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-white">
          <Mountain className="h-7 w-7 text-white/80" />
          <span className="text-sm font-semibold drop-shadow">
            Andes Centrales
          </span>
          <span className="rounded-full bg-black/30 px-2.5 py-0.5 text-[10px] text-white/80 backdrop-blur-sm">
            Mapa interactivo próximamente
          </span>
        </div>
      </div>
    </GlassCard>
  )
}
