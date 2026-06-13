// Envío de observaciones de la comunidad a la arquitectura GCP del proyecto.
// POST → Cloud Function receptor-observaciones → GCS (fotos) + BigQuery.

const URL_RECEPTOR =
  import.meta.env.VITE_RECEPTOR_OBSERVACIONES_URL ??
  'https://receptor-observaciones-hyf7y447pa-uc.a.run.app'

export const MAX_FOTOS = 2
export const MAX_BYTES_FOTO = 6 * 1024 * 1024 // 6 MB
export const TIPOS_FOTO = ['image/jpeg', 'image/png', 'image/webp']

// Lee un File como data URL base64 (lo que espera la Cloud Function).
export function leerArchivoBase64(file) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader()
    lector.onload = () => resolve({ tipo: file.type, datos_base64: lector.result })
    lector.onerror = () => reject(new Error('No se pudo leer la imagen'))
    lector.readAsDataURL(file)
  })
}

export async function enviarObservacion({ nombre, contacto, comentarios, centro, fechaObservacion, fotos = [] }) {
  const fotosBase64 = await Promise.all(fotos.map(leerArchivoBase64))

  const respuesta = await fetch(URL_RECEPTOR, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nombre,
      contacto,
      comentarios,
      centro,
      fecha_observacion: fechaObservacion,
      fotos: fotosBase64,
    }),
  })

  const cuerpo = await respuesta.json().catch(() => ({}))
  if (!respuesta.ok) {
    throw new Error(cuerpo.error || `Error al enviar (HTTP ${respuesta.status})`)
  }
  return cuerpo
}
