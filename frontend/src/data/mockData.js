// Mock data — Prueba de Concepto Avalanche_AlertCL
// Temporada invierno 2026 · Andes Centrales (Chile)
// Centros monitoreados en GCP: La Parva y Valle Nevado (+ centros mock adicionales)
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

  'portillo': {
    id: 'portillo',
    nombre: 'Portillo',
    zona: 'Valle del Aconcagua',
    elevacion: '2.580 – 3.310 m',
    exposicion: 'NE',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 3,
      descripcionIA:
        'Viento intenso en el paso fronterizo forma placas duras en canaletas sobre la Laguna del Inca. Riesgo considerable en terreno empinado fuera de pista; deslizamientos basales en losas lisas de Roca Jack.',
      vientoKmh: 70,
      temperatura: -6,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wind-slab',
        nombre: 'Placas de viento',
        cotas: 'Sobre 2.900 m',
        orientaciones: 'E – SE (sotavento)',
        detalle: 'Placas duras por viento O persistente del paso Los Libertadores.',
      },
      {
        id: 'gliding-snow',
        nombre: 'Nieve deslizante',
        cotas: '2.600 – 3.000 m',
        orientaciones: 'NE (losas rocosas)',
        detalle: 'Grietas de reptación visibles sobre losas lisas; evitar permanecer debajo.',
      },
    ],
    timeline: ajustarTimeline(-1, [3, 3, 3, 3, 4, 4, 3, 3, 3, 3, 2, 2]),
    pronostico15: ajustarPronostico(-1, 1.1),
    satelital: {
      ndsi: 0.81,
      coberturaPct: 88,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCD',
      tendencia: 'En aumento',
    },
    topografico: {
      estadoManto: 'Tensionado',
      estable: false,
      profundidadCm: 155,
      capaDebil: 'Detectada (~45 cm)',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.86,
    },
    comunidad: {
      resumenNLP:
        'Guías reportan placas que suenan huecas en el Superior C y grietas de reptación sobre la laguna. Tránsito por el paso con viento blanco intermitente.',
      reportes: [
        { autor: 'G. Olivares (guía)', hace: 'hace 2 h', texto: 'Placa hueca de 30 cm en la entrada del Superior C.' },
        { autor: 'Ski Patrol Portillo', hace: 'hace 8 h', texto: 'Control con explosivos en Roca Jack y Cara Cara.' },
        { autor: 'T. Saavedra', hace: 'hace 1 d', texto: 'Grietas de gliding bajo el Plateau.' },
      ],
      totalReportes48h: 17,
    },
  },

  'ski-arpa': {
    id: 'ski-arpa',
    nombre: 'Ski Arpa',
    zona: 'Valle del Aconcagua',
    elevacion: '2.600 – 3.700 m',
    exposicion: 'S',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 3,
      descripcionIA:
        'Terreno de alta montaña sin control: facetas enterradas persisten en umbrías sobre los 3.200 m. La nevada del jueves aumentará la carga sobre capas débiles; viajar con espaciamiento amplio.',
      vientoKmh: 55,
      temperatura: -8,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'persistent-weak-layer',
        nombre: 'Capa débil persistente',
        cotas: 'Sobre 3.200 m',
        orientaciones: 'S – SE (umbría)',
        detalle: 'Facetas de principios de temporada aún reactivas en tests de columna.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 2.800 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Acumulaciones importantes previstas; inestabilidad inicial alta.',
      },
    ],
    timeline: ajustarTimeline(-2, [3, 3, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3]),
    pronostico15: ajustarPronostico(-2, 1.2),
    satelital: {
      ndsi: 0.84,
      coberturaPct: 92,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCD',
      tendencia: 'En aumento',
    },
    topografico: {
      estadoManto: 'Frágil',
      estable: false,
      profundidadCm: 175,
      capaDebil: 'Detectada (~70 cm)',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.82,
    },
    comunidad: {
      resumenNLP:
        'Operación de cat-ski reporta resultados reactivos en tests de estabilidad en El Arpa alto y prefiere laderas de baja inclinación mientras persistan las facetas.',
      reportes: [
        { autor: 'Arpa Cats', hace: 'hace 6 h', texto: 'ECTP12 sobre facetas a 70 cm en cara sur, 3.350 m.' },
        { autor: 'F. Madrid (guía)', hace: 'hace 1 d', texto: 'Buen esquí en lomas suaves; evitamos lo cargado.' },
        { autor: 'C. Búsquets', hace: 'hace 2 d', texto: 'Viento moderado en el filo, nieve transportada.' },
      ],
      totalReportes48h: 7,
    },
  },

  'lagunillas': {
    id: 'lagunillas',
    nombre: 'Lagunillas',
    zona: 'Cajón del Maipo',
    elevacion: '2.250 – 2.700 m',
    exposicion: 'SO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 1,
      descripcionIA:
        'Manto delgado pero consolidado en cotas medias. Riesgo débil generalizado; humedecimiento superficial hacia el mediodía en solanas. La nevada del jueves mejorará la cobertura.',
      vientoKmh: 25,
      temperatura: -1,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 2.500 m',
        orientaciones: 'N – NO (solanas)',
        detalle: 'Sluffs superficiales puntuales con el calentamiento diurno.',
      },
    ],
    timeline: ajustarTimeline(3, [1, 1, 1, 2, 2, 2, 2, 2, 1, 1, 1, 1]),
    pronostico15: ajustarPronostico(3, 0.6),
    satelital: {
      ndsi: 0.62,
      coberturaPct: 68,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HCC',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 74,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.93,
    },
    comunidad: {
      resumenNLP:
        'Pocos reportes esta semana: cobertura justa en pistas bajas, nieve de primavera temprana en solanas y buena base en los sectores altos del centro.',
      reportes: [
        { autor: 'Club Andino', hace: 'hace 7 h', texto: 'Pistas superiores con base firme y pasto asomando abajo.' },
        { autor: 'V. Carrasco', hace: 'hace 2 d', texto: 'Nieve blanda al mediodía en la ladera norte.' },
      ],
      totalReportes48h: 4,
    },
  },

  'chapa-verde': {
    id: 'chapa-verde',
    nombre: 'Chapa Verde',
    zona: 'Andes de O’Higgins',
    elevacion: '2.700 – 3.100 m',
    exposicion: 'SO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Condiciones mayormente favorables dentro del centro. Acumulaciones de nieve nueva desde el jueves exigirán precaución en hombros venteados sobre los 2.900 m.',
      vientoKmh: 35,
      temperatura: -2,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 2.800 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Acumulaciones moderadas previstas; evaluar tras cada nevada.',
      },
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 2.900 m',
        orientaciones: 'O – NO (solanas)',
        detalle: 'Humedecimiento vespertino con cielos despejados.',
      },
    ],
    timeline: ajustarTimeline(2, [2, 2, 2, 2, 3, 3, 3, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(2, 0.75),
    satelital: {
      ndsi: 0.71,
      coberturaPct: 76,
      fechaPasada: '09 jun 2026 · 14:32 UTC',
      tile: 'T19HBB',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 96,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.9,
    },
    comunidad: {
      resumenNLP:
        'Reportes de esquiadores locales describen nieve compacta en pistas y acumulación venteada leve cerca del filo superior. Sin incidentes registrados.',
      reportes: [
        { autor: 'Ski Patrol Chapa Verde', hace: 'hace 6 h', texto: 'Pistas en buen estado; filo superior con sastrugi.' },
        { autor: 'L. Moreno', hace: 'hace 1 d', texto: 'Buena nieve a primera hora, pesada en la tarde.' },
      ],
      totalReportes48h: 5,
    },
  },
}

// Orden geográfico norte → sur: Aconcagua, Farellones, Cajón del Maipo, O'Higgins
const ORDEN_GEOGRAFICO = [
  'ski-arpa',
  'portillo',
  'la-parva',
  'valle-nevado',
  'lagunillas',
  'chapa-verde',
]

export const CENTROS_LISTA = ORDEN_GEOGRAFICO.map((id) => CENTROS[id])
