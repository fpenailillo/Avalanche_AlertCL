// Datos estructurales — Avalanche_AlertCL
// Todo el contenido real proviene del pipeline GCP (boletin_activo.json,
// series_wn2.json, series_horas.json). Este archivo solo define la identidad
// de cada centro y el andamiaje mínimo que fusion.js necesita para combinar
// los datos en línea.

export const ESCALA_EAWS = {
  1: { nombre: 'Débil',        color: '#CCFF66', texto: '#1a2e05' },
  2: { nombre: 'Moderado',     color: '#FFFF00', texto: '#3f3500' },
  3: { nombre: 'Considerable', color: '#FF9900', texto: '#451a03' },
  4: { nombre: 'Alto',         color: '#FF0000', texto: '#ffffff' },
  5: { nombre: 'Muy Alto',     color: '#9B1C1C', texto: '#ffffff' },
}

// 12 tramos de 6 h — fusionarTimeline() los sobreescribe con datos reales.
const TIMELINE_NEUTRO = Array.from({ length: 12 }, () => ({
  hora: '',
  icono: 'cloud',
  temp: null,
  nivel: 1,
}))

// Estado neutro: fusionarEstadoActual() lo sobreescribe desde boletin_activo.json.
const ESTADO_NEUTRO = {
  nivelEAWS:    1,
  descripcionIA: null,
  temperatura:  null,
  vientoKmh:    null,
  fechaBoletin: null,
  validoHasta:  null,
}

// Topográfico y satelital vacíos; fusionarTopografico/fusionarSatelital los completan.
const TOPOGRAFICO_NEUTRO = {
  estadoManto:  null,
  estable:      null,
  profundidadCm: null,
  capaDebil:    null,
  ultimaCorrida: null,
  confianza:    null,
}

const SATELITAL_NEUTRO = {
  ndsi:         null,
  coberturaPct: null,
  fechaPasada:  null,
  tile:         null,
  tendencia:    null,
}

const COMUNIDAD_NEUTRO = {
  resumenNLP:      null,
  reportes:        [],
  totalReportes48h: 0,
}

// Fábrica de centros: solo identidad + andamiaje estructural mínimo.
function mkCentro(id, nombre, zona, elevacion, exposicion) {
  return {
    id,
    nombre,
    zona,
    elevacion,
    exposicion,
    estadoActual: { ...ESTADO_NEUTRO },
    problemas:    [],
    timeline:     TIMELINE_NEUTRO.map((t) => ({ ...t })),
    pronostico15: [],
    satelital:    { ...SATELITAL_NEUTRO },
    topografico:  { ...TOPOGRAFICO_NEUTRO },
    comunidad:    { ...COMUNIDAD_NEUTRO, reportes: [] },
  }
}

// ─── Centros monitoreados (orden norte → sur) ─────────────────────────────────

export const CENTROS = {
  'ski-arpa':            mkCentro('ski-arpa',            'Ski Arpa',                    'Andes del Aconcagua',    '2.600 – 3.700 m', 'S'),
  portillo:              mkCentro('portillo',             'Portillo',                    'Valle del Aconcagua',    '2.580 – 3.310 m', 'NE'),
  'la-parva':            mkCentro('la-parva',             'La Parva',                    'Andes Centrales',        '2.200 – 4.500 m', 'SE'),
  'valle-nevado':        mkCentro('valle-nevado',         'Valle Nevado',                'Andes Centrales',        '2.800 – 4.500 m', 'NO'),
  'el-colorado':         mkCentro('el-colorado',          'El Colorado / Farellones',    'Andes Centrales',        '2.400 – 4.100 m', 'O'),
  lagunillas:            mkCentro('lagunillas',           'Lagunillas',                  'Cajón del Maipo',        '2.250 – 2.700 m', 'SO'),
  'valle-de-las-arenas': mkCentro('valle-de-las-arenas', 'Valle de las Arenas',          'Cajón del Maipo',        '2.200 – 3.200 m', 'SO'),
  'chapa-verde':         mkCentro('chapa-verde',          'Chapa Verde',                 "Andes de O'Higgins",     '2.700 – 3.100 m', 'SO'),
  'termas-del-flaco':    mkCentro('termas-del-flaco',    'Termas del Flaco',             "Andes de O'Higgins",     '1.700 – 2.800 m', 'SO'),
  'planchon-peteroa':    mkCentro('planchon-peteroa',    'Planchón-Peteroa',             'Andes del Maule',        '1.720 – 3.000 m', 'N'),
  'laguna-del-maule':    mkCentro('laguna-del-maule',    'Laguna del Maule',             'Andes del Maule',        '2.100 – 3.200 m', 'E'),
  'nevados-de-chillan':  mkCentro('nevados-de-chillan',  'Nevados de Chillán',           'Andes de Biobío',        '1.530 – 2.400 m', 'SO'),
  antuco:                mkCentro('antuco',               'Antuco',                      'Andes de Biobío',        '1.400 – 1.850 m', 'NO'),
  corralco:              mkCentro('corralco',             'Corralco',                    'Andes de La Araucanía',  '1.550 – 2.400 m', 'NE'),
  'los-arenales':        mkCentro('los-arenales',        'Los Arenales',                 'Andes de La Araucanía',  '1.500 – 1.845 m', 'S'),
  'las-araucarias':      mkCentro('las-araucarias',      'Las Araucarias',               'Andes de La Araucanía',  '1.550 – 1.942 m', 'O'),
  'ski-pucon':           mkCentro('ski-pucon',            'Pillán (ex Ski Pucón)',        'Andes de La Araucanía',  '1.380 – 2.100 m', 'SO'),
  'mocho-choshuenco':    mkCentro('mocho-choshuenco',   'Mocho-Choshuenco',             'Andes de Los Ríos',      '1.700 – 2.422 m', 'SO'),
  antillanca:            mkCentro('antillanca',           'Antillanca',                  'Andes de Los Lagos',     '1.040 – 1.540 m', 'SE'),
  'volcan-osorno':       mkCentro('volcan-osorno',       'Volcán Osorno',                'Andes de Los Lagos',     '1.230 – 1.760 m', 'SO'),
  'ski-chaiten':         mkCentro('ski-chaiten',         'Ski Chaitén',                  'Andes de Los Lagos',     '600 – 1.500 m',   'N'),
  'el-fraile':           mkCentro('el-fraile',           'El Fraile',                    'Andes de Aysén',         '980 – 1.280 m',   'N'),
  'cerro-mirador':       mkCentro('cerro-mirador',       'Cerro Mirador',                'Andes de Magallanes',    '380 – 570 m',     'SE'),
}

// Orden geográfico norte → sur: desde Aconcagua hasta Magallanes
const ORDEN_GEOGRAFICO = [
  'ski-arpa', 'portillo', 'la-parva', 'valle-nevado', 'el-colorado', 'lagunillas',
  'valle-de-las-arenas', 'chapa-verde', 'termas-del-flaco', 'planchon-peteroa', 'laguna-del-maule',
  'nevados-de-chillan', 'antuco', 'corralco', 'los-arenales', 'las-araucarias',
  'ski-pucon', 'mocho-choshuenco', 'antillanca', 'volcan-osorno', 'ski-chaiten',
  'el-fraile', 'cerro-mirador',
]

export const CENTROS_LISTA = ORDEN_GEOGRAFICO.map((id) => CENTROS[id])
