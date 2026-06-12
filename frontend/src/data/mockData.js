// Mock data — Prueba de Concepto Avalanche_AlertCL
// Temporada invierno 2026 · Andes Centrales (Chile)
// Centros monitoreados en GCP: La Parva, Valle Nevado, El Colorado
// (coherente con agentes/datos/constantes_zonas.py del sistema multi-agente)

export const ESCALA_EAWS = {
  1: { nombre: 'Débil', color: '#CCFF66', texto: '#1a2e05' },
  2: { nombre: 'Moderado', color: '#FFFF00', texto: '#3f3500' },
  3: { nombre: 'Considerable', color: '#FF9900', texto: '#451a03' },
  4: { nombre: 'Alto', color: '#FF0000', texto: '#ffffff' },
  5: { nombre: 'Muy Alto', color: '#9B1C1C', texto: '#ffffff' },
}

// ─── Bases compartidas (se ajustan por centro) ────────────────────────────────

const TIMELINE_BASE = [
  { hora: 'Ahora', icono: 'sun', temp: -4 },
  { hora: '14:00', icono: 'wind', temp: -2 },
  { hora: '20:00', icono: 'wind', temp: -6 },
  { hora: '02:00', icono: 'cloud', temp: -8 },
  { hora: '08:00', icono: 'cloud-snow', temp: -7, etiqueta: 'Jue' },
  { hora: '14:00', icono: 'cloud-snow', temp: -5 },
  { hora: '20:00', icono: 'snowflake', temp: -9 },
  { hora: '02:00', icono: 'snowflake', temp: -11 },
  { hora: '08:00', icono: 'cloud-snow', temp: -10, etiqueta: 'Vie' },
  { hora: '14:00', icono: 'cloud', temp: -6 },
  { hora: '20:00', icono: 'moon', temp: -9 },
  { hora: '02:00', icono: 'moon', temp: -12 },
]

const PRONOSTICO_BASE = [
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

const ajustarTimeline = (dTemp, niveles) =>
  TIMELINE_BASE.map((p, i) => ({ ...p, temp: p.temp + dTemp, nivel: niveles[i] }))

const ajustarPronostico = (dTemp, factorNieve) =>
  PRONOSTICO_BASE.map((d) => ({
    ...d,
    min: d.min + dTemp,
    max: d.max + dTemp,
    nieveCm: Math.round(d.nieveCm * factorNieve),
  }))

// ─── Centros de montaña monitoreados (GCP / BigQuery) ─────────────────────────

export const CENTROS = {
  'la-parva': {
    id: 'la-parva',
    nombre: 'La Parva',
    zona: 'Andes Centrales',
    elevacion: '2.200 – 4.500 m',
    exposicion: 'SE',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Condiciones estables en la mañana. Vientos fuertes del noroeste incrementan el riesgo de placas de viento en laderas de sotavento durante la tarde, especialmente sobre los 3.000 m.',
      vientoKmh: 45,
      temperatura: -4,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
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
    ],
    timeline: ajustarTimeline(0, [2, 2, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2]),
    pronostico15: ajustarPronostico(0, 1),
    satelital: {
      ndsi: 0.8,
      coberturaPct: 87,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCC',
      tendencia: 'En aumento',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 142,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.91,
    },
    comunidad: {
      resumenNLP:
        'Los reportes de las últimas 48 h describen nieve venteada sobre los 3.200 m y acumulaciones duras en canaletas de orientación sur. Sin actividad de avalanchas observada.',
      reportes: [
        { autor: 'C. Hernández', hace: 'hace 5 h', texto: 'Placas de viento en la cara sur de Falsa Parva.' },
        { autor: 'Ski Patrol La Parva', hace: 'hace 12 h', texto: 'Manto consolidado bajo los 2.900 m.' },
        { autor: 'M. Rojas', hace: 'hace 1 d', texto: 'Buena estabilidad en El Cepo, viento en cumbres.' },
      ],
      totalReportes48h: 14,
    },
  },

  'valle-nevado': {
    id: 'valle-nevado',
    nombre: 'Valle Nevado',
    zona: 'Andes Centrales',
    elevacion: '2.800 – 4.500 m',
    exposicion: 'NO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 3,
      descripcionIA:
        'Riesgo considerable por placas de viento extensas en cotas altas. La nevada prevista para el jueves cargará pendientes de sotavento; se esperan desprendimientos espontáneos sobre los 3.500 m.',
      vientoKmh: 62,
      temperatura: -7,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wind-slab',
        nombre: 'Placas de viento',
        cotas: 'Sobre 3.200 m',
        orientaciones: 'S – SE (sotavento)',
        detalle: 'Placas gruesas formadas por viento NO sostenido; fáciles de gatillar.',
      },
      {
        id: 'persistent-weak-layer',
        nombre: 'Capa débil persistente',
        cotas: 'Sobre 3.400 m',
        orientaciones: 'S (umbría)',
        detalle: 'Facetas enterradas detectadas por el modelo PINN a ~60 cm de profundidad.',
      },
    ],
    timeline: ajustarTimeline(-3, [3, 3, 3, 4, 4, 4, 4, 3, 3, 3, 3, 3]),
    pronostico15: ajustarPronostico(-2, 1.25),
    satelital: {
      ndsi: 0.83,
      coberturaPct: 91,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCC',
      tendencia: 'En aumento',
    },
    topografico: {
      estadoManto: 'Tensionado',
      estable: false,
      profundidadCm: 168,
      capaDebil: 'Detectada (~60 cm)',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.84,
    },
    comunidad: {
      resumenNLP:
        'Reportes recientes mencionan fisuras al cruzar lomas venteadas sobre los 3.400 m y un "whumpf" aislado en el sector Tres Puntas. Precaución en terreno expuesto.',
      reportes: [
        { autor: 'A. Fuenzalida', hace: 'hace 3 h', texto: 'Fisuras de 5 m al entrar a una loma cargada en Tres Puntas.' },
        { autor: 'Ski Patrol Valle Nevado', hace: 'hace 9 h', texto: 'Trabajo de control con explosivos en cotas altas.' },
        { autor: 'J. Pereira', hace: 'hace 1 d', texto: 'Viento blanco sobre 3.500 m, visibilidad reducida.' },
      ],
      totalReportes48h: 21,
    },
  },

  'el-colorado': {
    id: 'el-colorado',
    nombre: 'El Colorado',
    zona: 'Andes Centrales',
    elevacion: '2.400 – 4.100 m',
    exposicion: 'O',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Manto mayormente consolidado en pistas y cotas medias. Humedecimiento superficial en solanas de orientación oeste durante la tarde; nieve nueva esperada desde el jueves.',
      vientoKmh: 38,
      temperatura: -3,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 2.600 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Acumulaciones moderadas previstas; evaluar tras cada nevada.',
      },
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 2.800 m',
        orientaciones: 'O – NO (solanas)',
        detalle: 'Humedecimiento superficial vespertino por radiación; sluffs puntuales.',
      },
    ],
    timeline: ajustarTimeline(1, [2, 2, 2, 3, 3, 3, 3, 3, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(1, 0.9),
    satelital: {
      ndsi: 0.76,
      coberturaPct: 82,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCC',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 118,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.89,
    },
    comunidad: {
      resumenNLP:
        'Los reportes destacan buenas condiciones en pistas y nieve primavera en solanas hacia el mediodía. Sin señales de inestabilidad en cotas medias.',
      reportes: [
        { autor: 'P. Salinas', hace: 'hace 4 h', texto: 'Nieve compacta y agarre firme en Cono Este.' },
        { autor: 'Ski Patrol El Colorado', hace: 'hace 10 h', texto: 'Solanas con costra de rehielo matinal.' },
        { autor: 'R. Tapia', hace: 'hace 2 d', texto: 'Acumulación venteada leve cerca de la antena.' },
      ],
      totalReportes48h: 9,
    },
  },
}

export const CENTROS_LISTA = Object.values(CENTROS)
