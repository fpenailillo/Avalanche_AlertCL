import { useState } from 'react'
import { X, Send, ImagePlus, Loader2, CheckCircle2, MapPin, LocateFixed } from 'lucide-react'
import {
  enviarObservacion,
  MAX_FOTOS,
  MAX_BYTES_FOTO,
  TIPOS_FOTO,
} from '../services/observaciones'

const CORREO_CONTACTO = 'fpenailillo@usm.cl'
const hoyISO = () => new Date().toISOString().slice(0, 10)

export default function ObservacionModal({ centroNombre, onCerrar }) {
  const [nombre, setNombre] = useState('')
  const [contacto, setContacto] = useState('')
  const [comentarios, setComentarios] = useState('')
  const [fecha, setFecha] = useState(hoyISO())
  const [fotos, setFotos] = useState([])
  const [estado, setEstado] = useState('idle') // idle | enviando | ok | error
  const [error, setError] = useState('')

  // Ubicación: null | 'buscando' | { lat, lon, precision } | 'manual'
  const [ubicacion, setUbicacion] = useState(null)
  const [latManual, setLatManual] = useState('')
  const [lonManual, setLonManual] = useState('')

  const pedirGPS = () => {
    if (!navigator.geolocation) {
      setUbicacion('manual')
      return
    }
    setUbicacion('buscando')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUbicacion({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          precision: pos.coords.accuracy,
        })
      },
      () => setUbicacion('manual'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const latLonFinal = () => {
    if (ubicacion && ubicacion !== 'buscando' && ubicacion !== 'manual') {
      return { latitud: ubicacion.lat, longitud: ubicacion.lon, precisionGps: ubicacion.precision }
    }
    if (ubicacion === 'manual') {
      const lat = parseFloat(latManual)
      const lon = parseFloat(lonManual)
      if (!Number.isNaN(lat) && !Number.isNaN(lon)) return { latitud: lat, longitud: lon, precisionGps: null }
    }
    return { latitud: null, longitud: null, precisionGps: null }
  }

  const seleccionarFotos = (e) => {
    setError('')
    const elegidas = Array.from(e.target.files || [])
    if (elegidas.length > MAX_FOTOS) {
      setError(`Máximo ${MAX_FOTOS} fotos`)
      return
    }
    for (const f of elegidas) {
      if (!TIPOS_FOTO.includes(f.type)) {
        setError('Solo se permiten imágenes JPG, PNG o WEBP')
        return
      }
      if (f.size > MAX_BYTES_FOTO) {
        setError('Cada foto debe pesar menos de 6 MB')
        return
      }
    }
    setFotos(elegidas)
  }

  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    if (!comentarios.trim()) {
      setError('Cuéntanos qué observaste')
      return
    }
    if (!nombre.trim() && !contacto.trim()) {
      setError('Indica al menos tu nombre o un contacto')
      return
    }
    setEstado('enviando')
    try {
      await enviarObservacion({
        nombre: nombre.trim(),
        contacto: contacto.trim(),
        comentarios: comentarios.trim(),
        centro: centroNombre,
        fechaObservacion: fecha,
        fotos,
        ...latLonFinal(),
      })
      setEstado('ok')
    } catch (err) {
      setEstado('error')
      setError(err.message)
    }
  }

  const campo =
    'w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder-white/40 outline-none focus:border-sky-400/60'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onCerrar}
    >
      <div
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-3xl border border-white/15 bg-slate-900/90 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Reportar una observación</h3>
            <p className="text-xs text-white/50">
              {centroNombre ? `${centroNombre} · ` : ''}Aporta a la comunidad de montaña
            </p>
          </div>
          <button
            onClick={onCerrar}
            className="rounded-full p-1 text-white/60 hover:bg-white/10 hover:text-white"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {estado === 'ok' ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center text-white">
            <CheckCircle2 className="h-12 w-12 text-emerald-400" />
            <p className="font-medium">¡Gracias por tu reporte!</p>
            <p className="text-sm text-white/60">
              Tu observación quedó registrada y ayudará a mejorar los boletines.
            </p>
            <button
              onClick={onCerrar}
              className="mt-2 rounded-xl bg-sky-500/80 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
            >
              Cerrar
            </button>
          </div>
        ) : (
          <form onSubmit={enviar} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <input
                className={campo}
                placeholder="Nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                maxLength={200}
              />
              <input
                className={campo}
                placeholder="Correo o teléfono"
                value={contacto}
                onChange={(e) => setContacto(e.target.value)}
                maxLength={200}
              />
            </div>

            <textarea
              className={`${campo} min-h-[90px] resize-y`}
              placeholder="¿Qué observaste? (estado de la nieve, viento, avalanchas, etc.)"
              value={comentarios}
              onChange={(e) => setComentarios(e.target.value)}
              maxLength={4000}
              required
            />

            <label className="text-xs text-white/60">
              Fecha de la observación
              <input
                type="date"
                className={`${campo} mt-1`}
                value={fecha}
                max={hoyISO()}
                onChange={(e) => setFecha(e.target.value)}
              />
            </label>

            {/* Ubicación GPS o manual */}
            <div className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm">
              <p className="mb-1.5 text-xs text-white/60">Ubicación de la observación</p>
              {ubicacion === null && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={pedirGPS}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-sky-500/20 px-3 py-1.5 text-sky-300 hover:bg-sky-500/30"
                  >
                    <LocateFixed className="h-3.5 w-3.5" /> Usar GPS
                  </button>
                  <button
                    type="button"
                    onClick={() => setUbicacion('manual')}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-white/60 hover:bg-white/20"
                  >
                    <MapPin className="h-3.5 w-3.5" /> Ingresar manual
                  </button>
                </div>
              )}
              {ubicacion === 'buscando' && (
                <div className="flex items-center gap-2 text-white/50">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Obteniendo ubicación…
                </div>
              )}
              {ubicacion && ubicacion !== 'buscando' && ubicacion !== 'manual' && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-emerald-400">
                    <MapPin className="mr-1 inline h-3 w-3" />
                    {ubicacion.lat.toFixed(5)}, {ubicacion.lon.toFixed(5)}
                    {ubicacion.precision && (
                      <span className="ml-1 text-white/40">(±{Math.round(ubicacion.precision)} m)</span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => setUbicacion(null)}
                    className="text-xs text-white/40 hover:text-white/70"
                  >
                    Cambiar
                  </button>
                </div>
              )}
              {ubicacion === 'manual' && (
                <div className="flex gap-2">
                  <input
                    className="w-1/2 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-xs text-white placeholder-white/30 outline-none focus:border-sky-400/60"
                    placeholder="Latitud (-33.4567)"
                    value={latManual}
                    onChange={(e) => setLatManual(e.target.value)}
                    inputMode="decimal"
                  />
                  <input
                    className="w-1/2 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-xs text-white placeholder-white/30 outline-none focus:border-sky-400/60"
                    placeholder="Longitud (-70.1234)"
                    value={lonManual}
                    onChange={(e) => setLonManual(e.target.value)}
                    inputMode="decimal"
                  />
                  <button
                    type="button"
                    onClick={() => setUbicacion(null)}
                    className="shrink-0 text-xs text-white/40 hover:text-white/70"
                  >
                    GPS
                  </button>
                </div>
              )}
            </div>

            <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-white/20 bg-white/5 px-3 py-2 text-sm text-white/70 hover:bg-white/10">
              <ImagePlus className="h-4 w-4" />
              {fotos.length > 0 ? `${fotos.length} foto(s) seleccionada(s)` : `Agregar fotos (máx. ${MAX_FOTOS})`}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                onChange={seleccionarFotos}
              />
            </label>

            {error && <p className="text-xs text-rose-300">{error}</p>}

            <button
              type="submit"
              disabled={estado === 'enviando'}
              className="flex items-center justify-center gap-2 rounded-xl bg-sky-500/80 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-60"
            >
              {estado === 'enviando' ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Enviando…
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" /> Enviar observación
                </>
              )}
            </button>

            <p className="text-center text-[10px] text-white/40">
              ¿Prefieres correo? Escríbenos a{' '}
              <a href={`mailto:${CORREO_CONTACTO}`} className="underline hover:text-white/70">
                {CORREO_CONTACTO}
              </a>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
