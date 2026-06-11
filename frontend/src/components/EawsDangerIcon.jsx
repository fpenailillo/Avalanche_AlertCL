import danger0 from '../assets/eaws/danger-0.svg'
import danger1 from '../assets/eaws/danger-1.svg'
import danger2 from '../assets/eaws/danger-2.svg'
import danger3 from '../assets/eaws/danger-3.svg'
import danger45 from '../assets/eaws/danger-45.svg'

// Pictogramas oficiales EAWS (avalanches.org); niveles 4 y 5 comparten ícono
const ICONOS_NIVEL = {
  0: danger0,
  1: danger1,
  2: danger2,
  3: danger3,
  4: danger45,
  5: danger45,
}

export default function EawsDangerIcon({ nivel, className = 'h-16 w-16' }) {
  return (
    <img
      src={ICONOS_NIVEL[nivel] ?? ICONOS_NIVEL[0]}
      alt={`Ícono EAWS nivel de peligro ${nivel}`}
      className={className}
      draggable={false}
    />
  )
}
