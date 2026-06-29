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

  'laguna-del-maule': {
    id: 'laguna-del-maule',
    nombre: 'Laguna del Maule',
    zona: 'Andes del Maule',
    elevacion: '2.100 – 3.200 m',
    exposicion: 'E',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Complejo volcánico con excelente manto nival. Alta actividad de esquí de travesía y backcountry. Nuevas nevadas desde el jueves reforzarán la cobertura existente; precaución en pendientes volcánicas abruptas orientadas al este.',
      vientoKmh: 38,
      temperatura: -3,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 2.400 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Acumulaciones moderadas en sector cumbrero del complejo volcánico; evaluar pendientes abruptas.',
      },
      {
        id: 'wind-slab',
        nombre: 'Placa de viento',
        cotas: 'Sobre 2.800 m',
        orientaciones: 'E – SE (orientación dominante)',
        detalle: 'Vientos del oeste consolidan placas en hombros volcánicos orientados al este.',
      },
    ],
    timeline: ajustarTimeline(3, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(3, 1.3),
    satelital: {
      ndsi: 0.74,
      coberturaPct: 80,
      fechaPasada: '09 jun 2026 · 14:25 UTC',
      tile: 'T19HAC',
      tendencia: 'Mejorando',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 92,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.91,
    },
    comunidad: {
      resumenNLP:
        'Alta actividad de esquiadores de travesía y montañistas en Laguna del Maule. Temporada con excelente cobertura nival en el complejo volcánico.',
      reportes: [
        { autor: 'Grupo Travesía Maule', hace: 'hace 4 h', texto: 'Nieve excelente en el borde de la laguna. Calzado de crampones sobre los 2.800 m.' },
        { autor: 'F. Leiva', hace: 'hace 2 d', texto: 'Paisaje volcánico único, manto profundo y compacto. Recomendado para ski touring.' },
      ],
      totalReportes48h: 7,
    },
  },

  'nevados-de-chillan': {
    id: 'nevados-de-chillan',
    nombre: 'Nevados de Chillán',
    zona: 'Andes de Biobío',
    elevacion: '1.530 – 2.400 m',
    exposicion: 'SO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Manto húmedo en cotas bajas. Las nevadas previstas desde el jueves generarán problemas de nieve nueva sobre los 1.800 m, especialmente en vertientes suroeste. Vigilar lluvia sobre nieve en el sector base del volcán.',
      vientoKmh: 30,
      temperatura: -1,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.800 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Precipitaciones intensas esperadas desde el jueves; evaluar estabilidad tras cada evento.',
      },
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 2.000 m',
        orientaciones: 'NO – O (solanas del volcán)',
        detalle: 'Lluvia sobre nieve posible en base; riesgo de aludes de nieve húmeda en pendientes.',
      },
    ],
    timeline: ajustarTimeline(4, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(4, 1.5),
    satelital: {
      ndsi: 0.62,
      coberturaPct: 68,
      fechaPasada: '09 jun 2026 · 14:20 UTC',
      tile: 'T19HAB',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 78,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.88,
    },
    comunidad: {
      resumenNLP:
        'Reportes de esquiadores destacan buena cobertura en pistas altas del volcán. Base húmeda y pesada en sectores bajos de las termas.',
      reportes: [
        { autor: 'Ski Patrol Chillán', hace: 'hace 5 h', texto: 'Pistas en buen estado desde la mitad hacia arriba. Base blanda abajo.' },
        { autor: 'Club Andino Chillán', hace: 'hace 1 d', texto: 'Acceso a cumbre con nieve compacta desde los 2.200 m.' },
      ],
      totalReportes48h: 6,
    },
  },

  antuco: {
    id: 'antuco',
    nombre: 'Antuco',
    zona: 'Andes de Biobío',
    elevacion: '1.400 – 1.850 m',
    exposicion: 'NO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Condiciones moderadas en el Volcán Antuco. Cobertura nival justa en pistas bajas; mejora sobre los 1.600 m. Lluvia sobre nieve posible por debajo del centro en caso de alzas térmicas.',
      vientoKmh: 25,
      temperatura: 0,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 1.600 m',
        orientaciones: 'N – NE (solanas)',
        detalle: 'Humedecimiento durante las horas cálidas; aludes espontáneos posibles en pendientes orientadas al norte.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.700 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Nevadas moderadas en los próximos días; precaución en hombros venteados.',
      },
    ],
    timeline: ajustarTimeline(5, [2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(5, 1.4),
    satelital: {
      ndsi: 0.58,
      coberturaPct: 64,
      fechaPasada: '09 jun 2026 · 14:15 UTC',
      tile: 'T19HAA',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 62,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.85,
    },
    comunidad: {
      resumenNLP:
        'Pocos reportes esta semana. Esquiadores mencionan nieve pesada en pistas bajas y mejor calidad en las zonas altas del volcán.',
      reportes: [
        { autor: 'Club de Montaña Los Ángeles', hace: 'hace 8 h', texto: 'Buena base en zona cumbre; base gruesa abajo.' },
        { autor: 'J. Muñoz', hace: 'hace 2 d', texto: 'Nieve pesada en la bajada, cuidado con zonas de lluvia.' },
      ],
      totalReportes48h: 3,
    },
  },

  corralco: {
    id: 'corralco',
    nombre: 'Corralco',
    zona: 'Andes de La Araucanía',
    elevacion: '1.550 – 2.400 m',
    exposicion: 'NE',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Condiciones favorables en Corralco con nevadas recientes que mejoran la cobertura. Placas de viento posibles en hombros del Volcán Lonquimay sobre los 2.000 m; cotas altas con excelente calidad de nieve.',
      vientoKmh: 35,
      temperatura: -1,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.800 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Acumulaciones significativas en últimas 48 h; evaluar estabilidad en pendientes abruptas.',
      },
      {
        id: 'wind-slab',
        nombre: 'Placa de viento',
        cotas: 'Sobre 2.000 m',
        orientaciones: 'NE – E (sotavento del oeste)',
        detalle: 'Vientos del oeste consolidan placas frágiles en hombros del volcán.',
      },
    ],
    timeline: ajustarTimeline(4, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(4, 1.8),
    satelital: {
      ndsi: 0.67,
      coberturaPct: 73,
      fechaPasada: '09 jun 2026 · 14:10 UTC',
      tile: 'T19GVV',
      tendencia: 'Mejorando',
    },
    topografico: {
      estadoManto: 'Estable',
      estable: true,
      profundidadCm: 84,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.9,
    },
    comunidad: {
      resumenNLP:
        'Temporada con buen inicio en Corralco. Reportes positivos sobre la calidad de nieve en cotas altas del Lonquimay.',
      reportes: [
        { autor: 'Ski Patrol Corralco', hace: 'hace 4 h', texto: 'Excelente nieve polvo sobre los 2.000 m. Cuidado con hombros venteados.' },
        { autor: 'C. Ríos', hace: 'hace 1 d', texto: 'Increíble nieve; acceso al volcán bien señalizado.' },
      ],
      totalReportes48h: 8,
    },
  },

  'las-araucarias': {
    id: 'las-araucarias',
    nombre: 'Las Araucarias',
    zona: 'Andes de La Araucanía',
    elevacion: '1.550 – 1.942 m',
    exposicion: 'O',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Centro familiar al pie del Volcán Llaima con buena cobertura nival. Alta precipitación acumulada; nieve húmeda activa en las últimas horas. Precaución en pendientes orientadas al oeste durante la tarde.',
      vientoKmh: 32,
      temperatura: 0,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Todas las cotas',
        orientaciones: 'O – SO (exposición dominante)',
        detalle: 'Influencia oceánica genera humedecimiento desde mediodía; aludes de nieve mojada posibles.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.700 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Nevadas frecuentes; pendientes abruptas bajo cornisas merecen atención.',
      },
    ],
    timeline: ajustarTimeline(5, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(5, 1.8),
    satelital: {
      ndsi: 0.61,
      coberturaPct: 69,
      fechaPasada: '09 jun 2026 · 14:05 UTC',
      tile: 'T19GVU',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 72,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.86,
    },
    comunidad: {
      resumenNLP:
        'Reportes familiares describen pistas bien preparadas. Nieve pesada en la tarde como característica habitual del centro.',
      reportes: [
        { autor: 'Instructor Araucarias', hace: 'hace 6 h', texto: 'Clases de esquí con buena nieve en pistas bajas. Pesada desde las 14:00.' },
        { autor: 'Familia Torres', hace: 'hace 1 d', texto: 'Muy buen día, nieve perfecta en la mañana.' },
      ],
      totalReportes48h: 5,
    },
  },

  'ski-pucon': {
    id: 'ski-pucon',
    nombre: 'Ski Pucón',
    zona: 'Andes de La Araucanía',
    elevacion: '1.380 – 2.100 m',
    exposicion: 'SO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Condiciones variables en el Volcán Villarrica por influencia marítima intensa. Lluvia sobre nieve en sectores bajos; nieve de calidad sobre los 1.700 m. Supervisar alertas volcánicas de SERNAGEOMIN.',
      vientoKmh: 40,
      temperatura: 0,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 1.700 m',
        orientaciones: 'SO – O (orientación dominante)',
        detalle: 'Lluvia sobre nieve frecuente en base del volcán; aludes espontáneos en pendientes abruptas.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.700 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Nevadas copiosas esperadas; acumulaciones rápidas en laderas del cono volcánico.',
      },
    ],
    timeline: ajustarTimeline(5, [2, 2, 2, 3, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(5, 1.8),
    satelital: {
      ndsi: 0.63,
      coberturaPct: 71,
      fechaPasada: '09 jun 2026 · 13:58 UTC',
      tile: 'T19GVT',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 78,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.87,
    },
    comunidad: {
      resumenNLP:
        'Alta actividad de reportes en Pucón. Esquiadores destacan la cobertura desde la mitad del volcán hacia arriba; lluvia en la mañana en el sector bajo.',
      reportes: [
        { autor: 'MCP Mountain Pucón', hace: 'hace 3 h', texto: 'Apertura completa desde los 1.700 m. Lluvia abajo, nieve arriba.' },
        { autor: 'P. Alvarado', hace: 'hace 18 h', texto: 'Cumbre espectacular con vista al lago Villarrica. Nieve polvo sobre los 1.900 m.' },
      ],
      totalReportes48h: 11,
    },
  },

  antillanca: {
    id: 'antillanca',
    nombre: 'Antillanca',
    zona: 'Andes de Los Lagos',
    elevacion: '1.040 – 1.540 m',
    exposicion: 'SE',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Centro con mayor precipitación nival de Chile, influencia marítima extrema. Nevadas frecuentes y abundantes; manto saturado en cotas bajas. Precaución en las pendientes del Volcán Casablanca tras cada evento de precipitación.',
      vientoKmh: 45,
      temperatura: 2,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Todas las cotas',
        orientaciones: 'SE – E (orientación del centro)',
        detalle: 'Influencia oceánica permanente; humedecimiento del manto incluso en cotas altas.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.200 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Nevadas intensas y frecuentes propias del Parque Nacional Puyehue; acumulaciones rápidas.',
      },
    ],
    timeline: ajustarTimeline(7, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(7, 2.2),
    satelital: {
      ndsi: 0.52,
      coberturaPct: 61,
      fechaPasada: '09 jun 2026 · 13:50 UTC',
      tile: 'T19GUS',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 56,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.84,
    },
    comunidad: {
      resumenNLP:
        'Antillanca con temporada activa. Reportes destacan la abundante precipitación nival, aunque la nieve es pesada y húmeda por el clima oceánico del Parque Puyehue.',
      reportes: [
        { autor: 'Ski Patrol Antillanca', hace: 'hace 4 h', texto: 'Mucha nieve pero muy pesada. Pistas bien marcadas para seguridad.' },
        { autor: 'CONAF Puyehue', hace: 'hace 1 d', texto: 'Acceso expedito hasta la base. Condiciones volcánicas normales.' },
      ],
      totalReportes48h: 7,
    },
  },

  'volcan-osorno': {
    id: 'volcan-osorno',
    nombre: 'Volcán Osorno',
    zona: 'Andes de Los Lagos',
    elevacion: '1.230 – 1.760 m',
    exposicion: 'SO',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 2,
      descripcionIA:
        'Icónico volcán patagónico con precipitación muy alta. Manto húmedo en toda la extensión del centro. Las acumulaciones recientes requieren precaución en pendientes del cono volcánico sobre los 1.500 m.',
      vientoKmh: 50,
      temperatura: 1,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Todas las cotas',
        orientaciones: 'SO – O – NO',
        detalle: 'Clima oceánico con alta humedad; nieve húmeda activa en amplias franjas horarias.',
      },
      {
        id: 'new-snow',
        nombre: 'Nieve nueva',
        cotas: 'Sobre 1.400 m',
        orientaciones: 'Todas las orientaciones',
        detalle: 'Nevadas abundantes en el sector del Lago Llanquihue; evaluar pendientes abruptas del cono.',
      },
    ],
    timeline: ajustarTimeline(6, [2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2]),
    pronostico15: ajustarPronostico(6, 2.0),
    satelital: {
      ndsi: 0.55,
      coberturaPct: 63,
      fechaPasada: '09 jun 2026 · 13:44 UTC',
      tile: 'T19GUR',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 60,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.85,
    },
    comunidad: {
      resumenNLP:
        'Reportes de escaladores y esquiadores describen nieve pesada y vientos fuertes del Pacífico. Vistas al Lago Llanquihue cuando despeja.',
      reportes: [
        { autor: 'MCP Mountain Osorno', hace: 'hace 5 h', texto: 'Centro operativo con buena nieve. Viento fuerte en la tarde.' },
        { autor: 'R. Espinoza', hace: 'hace 2 d', texto: 'Subida al volcán con crampones; nieve dura y compacta sobre los 1.600 m.' },
      ],
      totalReportes48h: 5,
    },
  },

  'el-fraile': {
    id: 'el-fraile',
    nombre: 'El Fraile',
    zona: 'Andes de Aysén',
    elevacion: '980 – 1.280 m',
    exposicion: 'N',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 1,
      descripcionIA:
        'Condiciones favorables en El Fraile, único centro de esquí de Coyhaique. Elevaciones bajas con manto nival moderado. Vientos patagónicos fuertes del oeste pueden generar placas en los hombros del cerro.',
      vientoKmh: 55,
      temperatura: 3,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Bajo 1.100 m',
        orientaciones: 'N – NE (exposición del centro)',
        detalle: 'Cotas muy bajas propensas a lluvia-sobre-nieve; verificar temperatura en acceso.',
      },
    ],
    timeline: ajustarTimeline(8, [1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1]),
    pronostico15: ajustarPronostico(8, 1.2),
    satelital: {
      ndsi: 0.48,
      coberturaPct: 56,
      fechaPasada: '09 jun 2026 · 13:35 UTC',
      tile: 'T18GWJ',
      tendencia: 'Estable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 45,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.82,
    },
    comunidad: {
      resumenNLP:
        'Centro patagónico con ambiente familiar. Pocos reportes pero positivos; la temporada corta concentra esquiadores locales de Coyhaique.',
      reportes: [
        { autor: 'Club Andino Coyhaique', hace: 'hace 6 h', texto: 'Centro abierto con buenas condiciones. Viento fuerte en la cresta.' },
        { autor: 'M. Bahamondes', hace: 'hace 3 d', texto: 'Paisaje patagónico increíble con los lenga nevados.' },
      ],
      totalReportes48h: 3,
    },
  },

  'cerro-mirador': {
    id: 'cerro-mirador',
    nombre: 'Cerro Mirador',
    zona: 'Andes de Magallanes',
    elevacion: '380 – 570 m',
    exposicion: 'SE',
    estadoActual: {
      fechaBoletin: 'Miércoles 10 de junio de 2026 · 08:00',
      nivelEAWS: 1,
      descripcionIA:
        'El centro de esquí más austral del mundo opera con condiciones subantárticas. Elevaciones muy bajas; la nieve es frecuente pero la cobertura es variable. Vientos intensos del estrecho son la principal condición a monitorear.',
      vientoKmh: 60,
      temperatura: 5,
      validoHasta: 'Válido hasta el 11-06-2026 · 08:00',
    },
    problemas: [
      {
        id: 'wet-snow',
        nombre: 'Nieve húmeda',
        cotas: 'Todas las cotas',
        orientaciones: 'SE – E',
        detalle: 'Elevación muy baja con transiciones frecuentes nieve–lluvia; superficie variable según temperatura.',
      },
    ],
    timeline: ajustarTimeline(11, [1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1]),
    pronostico15: ajustarPronostico(11, 0.7),
    satelital: {
      ndsi: 0.42,
      coberturaPct: 50,
      fechaPasada: '09 jun 2026 · 13:20 UTC',
      tile: 'T18CWH',
      tendencia: 'Variable',
    },
    topografico: {
      estadoManto: 'Húmedo',
      estable: true,
      profundidadCm: 32,
      capaDebil: 'No detectada',
      ultimaCorrida: '10 jun 2026 · 06:00',
      confianza: 0.78,
    },
    comunidad: {
      resumenNLP:
        'Cerro Mirador, el centro más austral del mundo, opera con condiciones subantárticas únicas. Reportes de esquiadores locales de Punta Arenas y turistas que visitan el estrecho.',
      reportes: [
        { autor: 'Ski Club Punta Arenas', hace: 'hace 7 h', texto: 'Centro abierto; nieve compacta pero viento muy fuerte al mediodía.' },
        { autor: 'T. Mansilla', hace: 'hace 2 d', texto: 'Experiencia única esquiando con vista al Estrecho de Magallanes.' },
      ],
      totalReportes48h: 4,
    },
  },
}

// Orden geográfico norte → sur: desde Aconcagua hasta Magallanes
const ORDEN_GEOGRAFICO = [
  'ski-arpa',
  'portillo',
  'la-parva',
  'valle-nevado',
  'lagunillas',
  'chapa-verde',
  'laguna-del-maule',
  'nevados-de-chillan',
  'antuco',
  'corralco',
  'las-araucarias',
  'ski-pucon',
  'antillanca',
  'volcan-osorno',
  'el-fraile',
  'cerro-mirador',
]

export const CENTROS_LISTA = ORDEN_GEOGRAFICO.map((id) => CENTROS[id])
