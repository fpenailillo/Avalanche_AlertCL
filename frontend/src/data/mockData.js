// Mock data — Prueba de Concepto Avalanche_AlertCL
// Temporada invierno 2026 · La Parva, Andes Centrales (Chile)
// Datos coherentes con la semana del 10 de junio de 2026.

export const ESCALA_EAWS = {
  1: { nombre: 'Débil', color: '#CCFF66', texto: '#1a2e05' },
  2: { nombre: 'Moderado', color: '#FFFF00', texto: '#3f3500' },
  3: { nombre: 'Considerable', color: '#FF9900', texto: '#451a03' },
  4: { nombre: 'Alto', color: '#FF0000', texto: '#ffffff' },
  5: { nombre: 'Muy Alto', color: '#9B1C1C', texto: '#ffffff' },
}

export const ESTADO_ACTUAL = {
  ubicacion: 'La Parva',
  zona: 'Andes Centrales',
  fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
  nivelEAWS: 2,
  descripcionIA:
    'Condiciones estables en la mañana. Vientos fuertes del noroeste incrementan el riesgo de placas de viento en laderas de sotavento durante la tarde, especialmente sobre los 3.000 m.',
  vientoKmh: 45,
  temperatura: -4,
  validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
}

// Problemas de avalancha activos (tipología estándar EAWS)
export const PROBLEMAS_AVALANCHA = [
  {
    id: 'wind-slab',
    nombre: 'Placas de viento',
    cotas: 'Sobre 3.000 m',
    orientaciones: 'S – SE (sotavento)',
    detalle: 'Acumulaciones recientes por viento NO; reactivas al paso de un esquiador.',
  },
  {
    id: 'new-snow',
    nombre: 'Nieve nueva',
    cotas: 'Sobre 2.500 m',
    orientaciones: 'Todas las orientaciones',
    detalle: 'Nevadas previstas para las próximas 48 h sin consolidar.',
  },
]

// Evolución del riesgo y clima — próximas 72 horas (cada 6 h)
export const TIMELINE_72H = [
  { hora: 'Ahora', icono: 'sun', temp: -4, nivel: 2 },
  { hora: '14:00', icono: 'wind', temp: -2, nivel: 2 },
  { hora: '20:00', icono: 'wind', temp: -6, nivel: 3 },
  { hora: '02:00', icono: 'cloud', temp: -8, nivel: 3 },
  { hora: '08:00', icono: 'cloud-snow', temp: -7, nivel: 3, etiqueta: 'Jue' },
  { hora: '14:00', icono: 'cloud-snow', temp: -5, nivel: 3 },
  { hora: '20:00', icono: 'snowflake', temp: -9, nivel: 3 },
  { hora: '02:00', icono: 'snowflake', temp: -11, nivel: 3 },
  { hora: '08:00', icono: 'cloud-snow', temp: -10, nivel: 3, etiqueta: 'Vie' },
  { hora: '14:00', icono: 'cloud', temp: -6, nivel: 2 },
  { hora: '20:00', icono: 'moon', temp: -9, nivel: 2 },
  { hora: '02:00', icono: 'moon', temp: -12, nivel: 2 },
]

// Pronóstico extendido a 15 días — fuente: WeatherNext 2 (Google DeepMind)
export const PRONOSTICO_15_DIAS = [
  { dia: 'Hoy', fecha: '10 jun', icono: 'wind', min: -8, max: -2, nieveCm: 0, isotermaM: 2300 },
  { dia: 'Jue', fecha: '11 jun', icono: 'cloud-snow', min: -11, max: -5, nieveCm: 18, isotermaM: 2100 },
  { dia: 'Vie', fecha: '12 jun', icono: 'cloud-snow', min: -12, max: -6, nieveCm: 12, isotermaM: 2000 },
  { dia: 'Sáb', fecha: '13 jun', icono: 'cloud', min: -10, max: -3, nieveCm: 2, isotermaM: 2200 },
  { dia: 'Dom', fecha: '14 jun', icono: 'cloud-snow', min: -9, max: -4, nieveCm: 25, isotermaM: 1900 },
  { dia: 'Lun', fecha: '15 jun', icono: 'snowflake', min: -14, max: -7, nieveCm: 40, isotermaM: 1750 },
  { dia: 'Mar', fecha: '16 jun', icono: 'snowflake', min: -15, max: -8, nieveCm: 22, isotermaM: 1800 },
  { dia: 'Mié', fecha: '17 jun', icono: 'cloud', min: -12, max: -4, nieveCm: 4, isotermaM: 2050 },
  { dia: 'Jue', fecha: '18 jun', icono: 'sun', min: -10, max: -1, nieveCm: 0, isotermaM: 2400 },
  { dia: 'Vie', fecha: '19 jun', icono: 'sun', min: -8, max: 1, nieveCm: 0, isotermaM: 2600 },
  { dia: 'Sáb', fecha: '20 jun', icono: 'cloud', min: -7, max: 0, nieveCm: 0, isotermaM: 2500 },
  { dia: 'Dom', fecha: '21 jun', icono: 'wind', min: -9, max: -2, nieveCm: 3, isotermaM: 2350 },
  { dia: 'Lun', fecha: '22 jun', icono: 'cloud-snow', min: -11, max: -5, nieveCm: 15, isotermaM: 2100 },
  { dia: 'Mar', fecha: '23 jun', icono: 'cloud-snow', min: -13, max: -6, nieveCm: 20, isotermaM: 1950 },
  { dia: 'Mié', fecha: '24 jun', icono: 'sun', min: -12, max: -3, nieveCm: 0, isotermaM: 2250 },
]

// Subagente S2 — Observación satelital (Sentinel-2)
export const SATELITAL_S2 = {
  ndsi: 0.8,
  coberturaPct: 87,
  fechaPasada: '09 jun 2026 · 14:32 UTC',
  tile: 'T19HCC',
  tendencia: 'En aumento',
}

// Subagente S1 — Modelo físico del manto (PINN)
export const TOPOGRAFICO_S1 = {
  estadoManto: 'Estable',
  profundidadCm: 142,
  capaDebil: 'No detectada',
  ultimaCorrida: '10 jun 2026 · 06:00',
  confianza: 0.91,
}

// Subagente S4 — Comunidad (resumen NLP de reportes)
export const COMUNIDAD_S4 = {
  resumenNLP:
    'Los reportes de las últimas 48 h describen nieve venteada sobre los 3.200 m y acumulaciones duras en canaletas de orientación sur. Sin actividad de avalanchas observada.',
  reportes: [
    { autor: 'C. Hernández', hace: 'hace 5 h', texto: 'Placas de viento en la cara sur de Falsa Parva.' },
    { autor: 'Ski Patrol La Parva', hace: 'hace 12 h', texto: 'Manto consolidado bajo los 2.900 m.' },
    { autor: 'M. Rojas', hace: 'hace 1 d', texto: 'Buena estabilidad en El Cepo, viento en cumbres.' },
  ],
  totalReportes48h: 14,
}
