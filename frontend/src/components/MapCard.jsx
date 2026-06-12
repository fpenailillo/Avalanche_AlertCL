import { Map, Mountain } from 'lucide-react'
import GlassCard from './GlassCard'
import { ESCALA_EAWS } from '../data/mockData'

// Posiciones relativas en el lienzo SVG según geografía real (norte arriba):
// Aconcagua al N (Ski Arpa, Portillo), Farellones al centro (LP/EC/VN),
// Cajón del Maipo al SE (Lagunillas) y O'Higgins al S (Chapa Verde).
// labelDy permite subir la etiqueta en los marcadores cercanos al borde inferior.
const POSICIONES = {
  'ski-arpa': { x: 110, y: 38 },
  'portillo': { x: 255, y: 32 },
  'la-parva': { x: 130, y: 92 },
  'valle-nevado': { x: 225, y: 102 },
  'lagunillas': { x: 280, y: 152 },
  'chapa-verde': { x: 135, y: 172, labelDy: -18 },
}

export default function MapCard({ centros, seleccionadoId, onSelect, className = '' }) {
  return (
    <GlassCard icon={Map} title="Mapa de zonas EAWS" className={className}>
      <div className="relative min-h-44 flex-1 overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-900 via-blue-800 to-sky-600">
        {/* Cordillera estilizada */}
        <svg viewBox="0 0 400 200" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          <polygon
            points="0,200 70,90 130,150 200,40 270,130 330,70 400,200"
            fill="rgba(255,255,255,0.18)"
          />
          <polygon
            points="0,200 100,130 180,170 260,90 340,160 400,120 400,200"
            fill="rgba(255,255,255,0.30)"
          />
          {centros.map((centro) => {
            const pos = POSICIONES[centro.id]
            const nivel = ESCALA_EAWS[centro.estadoActual.nivelEAWS]
            const activo = centro.id === seleccionadoId
            return (
              <g
                key={centro.id}
                onClick={() => onSelect?.(centro.id)}
                className="cursor-pointer"
              >
                {activo && (
                  <circle cx={pos.x} cy={pos.y} r="16" fill="none" stroke="white" strokeWidth="2" opacity="0.9" />
                )}
                <circle cx={pos.x} cy={pos.y} r="11" fill={nivel.color} opacity="0.95" />
                <text
                  x={pos.x}
                  y={pos.y + 4}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="bold"
                  fill={nivel.texto}
                >
                  {centro.estadoActual.nivelEAWS}
                </text>
                <text
                  x={pos.x}
                  y={pos.y + (pos.labelDy ?? 28)}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight={activo ? 'bold' : 'normal'}
                  fill="white"
                  opacity={activo ? 1 : 0.75}
                >
                  {centro.nombre}
                </text>
              </g>
            )
          })}
        </svg>

        <div className="pointer-events-none absolute inset-x-0 top-2 flex flex-col items-center gap-0.5 text-white">
          <span className="flex items-center gap-1 text-xs font-semibold drop-shadow">
            <Mountain className="h-3.5 w-3.5" />
            Andes de Chile Central
          </span>
          <span className="rounded-full bg-black/30 px-2 py-0.5 text-[9px] text-white/80 backdrop-blur-sm">
            Toca un centro para ver su boletín
          </span>
        </div>
      </div>
    </GlassCard>
  )
}
