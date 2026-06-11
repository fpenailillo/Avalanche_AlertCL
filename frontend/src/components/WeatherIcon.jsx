import { Sun, Moon, Cloud, CloudSnow, Snowflake, Wind } from 'lucide-react'

const ICONOS = {
  sun: { Icon: Sun, color: 'text-yellow-300' },
  moon: { Icon: Moon, color: 'text-slate-300' },
  cloud: { Icon: Cloud, color: 'text-slate-200' },
  'cloud-snow': { Icon: CloudSnow, color: 'text-sky-200' },
  snowflake: { Icon: Snowflake, color: 'text-cyan-200' },
  wind: { Icon: Wind, color: 'text-teal-200' },
}

export default function WeatherIcon({ tipo, className = 'h-6 w-6' }) {
  const { Icon, color } = ICONOS[tipo] ?? ICONOS.cloud
  return <Icon className={`${className} ${color}`} />
}
