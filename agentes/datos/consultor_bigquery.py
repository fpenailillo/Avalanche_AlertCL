"""
Consultor de BigQuery para el Sistema de Predicción de Avalanchas

Clase centralizada que accede a las 5 tablas de datos del proyecto
climas-chileno y retorna diccionarios compatibles con tool_use de Anthropic.

Reglas:
- Todos los métodos retornan dict (nunca DataFrame)
- Nunca lanzar excepciones — siempre retornar {"error": "..."} si falla
- Timeout de 30 segundos por query
- Consultas parametrizadas (nunca f-strings con SQL)
- Logging del tiempo de ejecución
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import concurrent.futures

from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions


# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Variable global de fecha de referencia para consultas históricas.
# El orquestador puede establecerla antes de ejecutar subagentes para que
# ConsultorBigQuery use esa fecha en lugar de CURRENT_TIMESTAMP().
# Las tools de subagentes instancian ConsultorBigQuery sin pasar fecha_referencia,
# pero si esta variable está establecida, se usará automáticamente.
_fecha_referencia_global: Optional[datetime] = None


def establecer_fecha_referencia_global(fecha: Optional[datetime]) -> None:
    """
    Establece la fecha de referencia global para todas las instancias de ConsultorBigQuery.

    Úsala en el orquestador antes de ejecutar subagentes para análisis histórico.
    Llama con None para restablecer al comportamiento normal (CURRENT_TIMESTAMP).

    Args:
        fecha: datetime de referencia, o None para usar la fecha actual
    """
    global _fecha_referencia_global
    _fecha_referencia_global = fecha
    if fecha is not None:
        logger.info(
            f"ConsultorBigQuery: fecha de referencia global establecida → {fecha.isoformat()}"
        )
    else:
        logger.info("ConsultorBigQuery: fecha de referencia global restablecida a None (actual)")


def obtener_fecha_referencia_global() -> Optional[datetime]:
    """
    Retorna la fecha de referencia global actualmente establecida.

    Returns:
        datetime de referencia o None si se usa la fecha actual
    """
    return _fecha_referencia_global


class ErrorConexionBigQuery(Exception):
    """Excepción para errores de conexión con BigQuery."""
    pass


class ConsultorBigQuery:
    """
    Acceso centralizado a las tablas de BigQuery del proyecto climas-chileno.

    Todos los métodos retornan dict para compatibilidad con tool_use de Anthropic.
    Nunca lanzan excepciones: errores se retornan como {"error": "mensaje"}.
    """

    GCP_PROJECT = os.environ.get("GCP_PROJECT") or os.environ.get("ID_PROYECTO", "climas-chileno")
    DATASET = os.environ.get("DATASET_ID", "clima")
    TIMEOUT_SEGUNDOS = 30

    def __init__(self):
        """Inicializa el cliente de BigQuery con Application Default Credentials."""
        try:
            self.cliente = bigquery.Client(project=self.GCP_PROJECT)
            logger.info(f"ConsultorBigQuery inicializado para proyecto: {self.GCP_PROJECT}")
        except Exception as e:
            logger.error(f"Error al inicializar cliente BigQuery: {e}")
            raise ErrorConexionBigQuery(f"No se pudo conectar a BigQuery: {e}")

    def _ejecutar_query(self, sql: str, parametros: list) -> list:
        """
        Ejecuta una query parametrizada con timeout.

        Args:
            sql: Consulta SQL con placeholders @nombre
            parametros: Lista de bigquery.ScalarQueryParameter

        Returns:
            Lista de filas como dicts

        Raises:
            Exception: Si la query falla (manejado por los métodos públicos)
        """
        config_job = bigquery.QueryJobConfig(
            query_parameters=parametros
        )

        inicio = time.time()
        job = self.cliente.query(sql, job_config=config_job)
        filas = list(job.result(timeout=self.TIMEOUT_SEGUNDOS))
        duracion = round(time.time() - inicio, 2)

        logger.info(f"Query ejecutada en {duracion}s — {len(filas)} filas obtenidas")
        return [dict(fila) for fila in filas]

    def obtener_condiciones_actuales(
        self,
        ubicacion: str,
        fecha_referencia: Optional[datetime] = None
    ) -> dict:
        """
        Última fila de condiciones_actuales para la ubicación. Max antigüedad: 12h.

        Args:
            ubicacion: Nombre exacto de la ubicación
            fecha_referencia: datetime de referencia para datos históricos.
                Si es None, usa CURRENT_TIMESTAMP() (comportamiento normal).
                Si se provee, filtra datos respecto a esa fecha.

        Returns:
            dict con campos climáticos actuales, o {"disponible": False, "razon": "..."}
        """
        logger.info(f"Consultando condiciones actuales para: {ubicacion}")
        # Resolver fecha de referencia: parámetro explícito tiene prioridad sobre global
        fecha_referencia = fecha_referencia or _fecha_referencia_global
        try:
            if fecha_referencia is None:
                sql = """
                    SELECT
                        temperatura,
                        sensacion_termica,
                        velocidad_viento,
                        direccion_viento,
                        precipitacion_acumulada,
                        probabilidad_precipitacion,
                        humedad_relativa,
                        presion_aire,
                        cobertura_nubes,
                        condicion_clima,
                        hora_actual,
                        es_dia,
                        datos_json_crudo
                    FROM `{proyecto}.{dataset}.condiciones_actuales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_actual >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 HOUR)
                    ORDER BY hora_actual DESC
                    LIMIT 1
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
                ]
            else:
                sql = """
                    SELECT
                        temperatura,
                        sensacion_termica,
                        velocidad_viento,
                        direccion_viento,
                        precipitacion_acumulada,
                        probabilidad_precipitacion,
                        humedad_relativa,
                        presion_aire,
                        cobertura_nubes,
                        condicion_clima,
                        hora_actual,
                        es_dia,
                        datos_json_crudo
                    FROM `{proyecto}.{dataset}.condiciones_actuales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_actual >= TIMESTAMP_SUB(TIMESTAMP(@fecha_ref), INTERVAL 12 HOUR)
                      AND hora_actual <= TIMESTAMP_ADD(TIMESTAMP(@fecha_ref), INTERVAL 12 HOUR)
                    ORDER BY hora_actual DESC
                    LIMIT 1
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter(
                        "fecha_ref", "TIMESTAMP", fecha_referencia
                    ),
                ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                logger.warning(f"Sin condiciones actuales recientes para: {ubicacion}")
                return {
                    "disponible": False,
                    "razon": "Sin datos en las últimas 12 horas"
                }

            resultado = filas[0]
            resultado["disponible"] = True

            # FIX-WIND-UNITS (bug_021): condiciones_actuales.velocidad_viento se almacena
            # en km/h por todas las rutas de ingesta. Normalizar a m/s aquí para que los
            # consumers (_clasificar_viento, detectar_ventanas_criticas, fuente_open_meteo,
            # tool_clima_reciente) usen sus umbrales Beaufort correctamente, y almacenador
            # vuelva a km/h con el ×3.6 ya existente.
            _vw = resultado.get("velocidad_viento")
            if _vw is not None:
                resultado["velocidad_viento"] = round(_vw / 3.6, 2)

            # FIX-CR19 + FIX-IMIS-EXT (v20.0): extraer señales IMIS de datos_json_crudo.
            crudo_str = resultado.pop("datos_json_crudo", None)
            if crudo_str:
                import json as _json
                try:
                    crudo = _json.loads(crudo_str)
                    # HN24 (original CR-19)
                    nieve_cm = crudo.get("nieve_nueva_cm") or crudo.get("HN24_cm")
                    if nieve_cm is not None:
                        resultado["nieve_nueva_cm"] = float(nieve_cm)
                    # FIX-IMIS-EXT: variables adicionales con filtro de outliers.
                    # Prioridad sobre ERA5 cuando disponibles (ver subagente S3).
                    imis: dict = {}
                    for key, k_imis, lo, hi in [
                        ("hs_cm",      "HS_cm",       0,   600),
                        ("ta_imis_c",  "TA_C",      -40,    30),
                        ("vw_imis_ms", "VW_ms",       0,    60),
                        ("vw_max_ms",  "VW_max_ms",   0,    80),
                    ]:
                        v = crudo.get(k_imis)
                        if v is not None:
                            try:
                                fv = float(v)
                                if lo <= fv <= hi:
                                    imis[key] = fv
                            except (ValueError, TypeError):
                                pass
                    if imis:
                        resultado["imis_directo"] = imis
                except Exception:
                    pass

            # Serializar tipos especiales
            if resultado.get("hora_actual") and hasattr(resultado["hora_actual"], "isoformat"):
                resultado["hora_actual"] = resultado["hora_actual"].isoformat()

            return resultado

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar condiciones actuales para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando condiciones actuales para {ubicacion}: {e}")
            return {"error": str(e)}

    def _tendencia_desde_imis(
        self,
        ubicacion: str,
        fecha_referencia,
    ) -> dict | None:
        """
        Fallback v14.0: construye tendencia meteorológica desde condiciones_actuales
        cuando pronostico_horas está vacío (fechas DEAPSnow 2018-2020).

        Solo activa si hay un registro IMIS (fuente='IMIS_DEAPSnow_RF2') en
        condiciones_actuales para la ubicación y fecha de referencia.
        """
        import json as _json

        try:
            sql = """
                SELECT
                    temperatura, velocidad_viento, precipitacion_acumulada,
                    humedad_relativa, datos_json_crudo
                FROM `{proyecto}.{dataset}.condiciones_actuales`
                WHERE nombre_ubicacion = @ubicacion
                  AND hora_actual >= TIMESTAMP_SUB(TIMESTAMP(@fecha_ref), INTERVAL 12 HOUR)
                  AND hora_actual <= TIMESTAMP_ADD(TIMESTAMP(@fecha_ref), INTERVAL 12 HOUR)
                  AND JSON_VALUE(datos_json_crudo, '$.fuente') = 'IMIS_DEAPSnow_RF2'
                ORDER BY hora_actual DESC
                LIMIT 1
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            parametros = [
                bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                bigquery.ScalarQueryParameter("fecha_ref", "TIMESTAMP", fecha_referencia),
            ]
            filas = self._ejecutar_query(sql, parametros)
            if not filas:
                return None

            fila = filas[0]
            ta = fila.get("temperatura")
            vw_kmh = fila.get("velocidad_viento")
            vw_ms = round(vw_kmh / 3.6, 2) if vw_kmh is not None else None

            # HN24 del JSON crudo para estimar precipitación 72h
            crudo = fila.get("datos_json_crudo") or "{}"
            if isinstance(crudo, str):
                crudo = _json.loads(crudo)
            hn24_cm = crudo.get("HN24_cm")
            precip_proxy = round(hn24_cm / 10.0, 2) if (hn24_cm is not None and hn24_cm > 0) else 0.0

            alertas = []
            if precip_proxy > 10:
                alertas.append({"tipo": "PRECIPITACION_CRITICA", "valor": f"{precip_proxy}mm (proxy IMIS)"})
            if vw_ms and vw_ms > 15:
                alertas.append({"tipo": "VIENTO_FUERTE", "valor": f"{round(vw_ms, 1)} m/s"})

            logger.info(
                f"[IMIS fallback] tendencia desde condiciones_actuales: "
                f"{ubicacion} TA={ta}°C VW={vw_kmh}km/h HN24={hn24_cm}cm"
            )
            return {
                "disponible": True,
                "fuente": "IMIS_DEAPSnow_RF2_proxy",
                "temp_min_72h": ta,
                "temp_max_72h": ta,
                "precip_total_acumulada_mm": precip_proxy,
                "viento_max_ms": vw_ms,
                "hora_viento_max": None,
                "horas_con_precipitacion": 1 if precip_proxy > 0 else 0,
                "tendencia_temperatura": "estable",
                "alertas": alertas,
            }

        except Exception as e:
            logger.warning(f"[IMIS fallback] error en _tendencia_desde_imis: {e}")
            return None

    def obtener_tendencia_meteorologica(
        self,
        ubicacion: str,
        fecha_referencia: Optional[datetime] = None
    ) -> dict:
        """
        Resumen estadístico de las últimas 72h de pronostico_horas + próximas 48h.

        Args:
            ubicacion: Nombre exacto de la ubicación
            fecha_referencia: datetime de referencia para datos históricos.
                Si es None, usa CURRENT_TIMESTAMP() (comportamiento normal).
                Si se provee, calcula el intervalo respecto a esa fecha.

        Returns:
            dict con estadísticas resumidas de temperatura, viento, precipitación y alertas
        """
        logger.info(f"Consultando tendencia meteorológica para: {ubicacion}")
        # Resolver fecha de referencia: parámetro explícito tiene prioridad sobre global
        fecha_referencia = fecha_referencia or _fecha_referencia_global
        try:
            if fecha_referencia is None:
                # Query de las últimas 72h
                sql_pasado = """
                    SELECT
                        temperatura,
                        velocidad_viento,
                        cantidad_precipitacion,
                        hora_inicio
                    FROM `{proyecto}.{dataset}.pronostico_horas`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_inicio >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
                      AND hora_inicio <= CURRENT_TIMESTAMP()
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY hora_inicio
                        ORDER BY marca_tiempo_ingestion DESC
                    ) = 1
                    ORDER BY hora_inicio ASC
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                # Query de las próximas 48h
                sql_futuro = """
                    SELECT
                        temperatura,
                        velocidad_viento,
                        cantidad_precipitacion,
                        hora_inicio
                    FROM `{proyecto}.{dataset}.pronostico_horas`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_inicio > CURRENT_TIMESTAMP()
                      AND hora_inicio <= TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY hora_inicio
                        ORDER BY marca_tiempo_ingestion DESC
                    ) = 1
                    ORDER BY hora_inicio ASC
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
                ]
            else:
                # Query de las últimas 72h respecto a fecha_referencia
                sql_pasado = """
                    SELECT
                        temperatura,
                        velocidad_viento,
                        cantidad_precipitacion,
                        hora_inicio
                    FROM `{proyecto}.{dataset}.pronostico_horas`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_inicio >= TIMESTAMP_SUB(TIMESTAMP(@fecha_ref), INTERVAL 72 HOUR)
                      AND hora_inicio <= TIMESTAMP(@fecha_ref)
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY hora_inicio
                        ORDER BY marca_tiempo_ingestion DESC
                    ) = 1
                    ORDER BY hora_inicio ASC
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                # Query de las próximas 48h respecto a fecha_referencia
                sql_futuro = """
                    SELECT
                        temperatura,
                        velocidad_viento,
                        cantidad_precipitacion,
                        hora_inicio
                    FROM `{proyecto}.{dataset}.pronostico_horas`
                    WHERE nombre_ubicacion = @ubicacion
                      AND hora_inicio > TIMESTAMP(@fecha_ref)
                      AND hora_inicio <= TIMESTAMP_ADD(TIMESTAMP(@fecha_ref), INTERVAL 48 HOUR)
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY hora_inicio
                        ORDER BY marca_tiempo_ingestion DESC
                    ) = 1
                    ORDER BY hora_inicio ASC
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter(
                        "fecha_ref", "TIMESTAMP", fecha_referencia
                    ),
                ]

            filas_pasado = self._ejecutar_query(sql_pasado, parametros)
            filas_futuro = self._ejecutar_query(sql_futuro, parametros)

            if not filas_pasado and not filas_futuro:
                # FIX-IMIS-TENDENCIA (v14.0): fallback a condiciones_actuales con IMIS
                imis_tendencia = self._tendencia_desde_imis(ubicacion, fecha_referencia)
                if imis_tendencia:
                    return imis_tendencia
                return {
                    "disponible": False,
                    "razon": "Sin datos de pronóstico horario"
                }

            todas_filas = filas_pasado + filas_futuro

            # Calcular estadísticas
            temperaturas = [f["temperatura"] for f in todas_filas if f.get("temperatura") is not None]
            vientos = [f["velocidad_viento"] for f in todas_filas if f.get("velocidad_viento") is not None]
            precipitaciones = [f["cantidad_precipitacion"] for f in todas_filas if f.get("cantidad_precipitacion") is not None]

            temp_min_72h = min(temperaturas) if temperaturas else None
            temp_max_72h = max(temperaturas) if temperaturas else None
            precip_total_acumulada_mm = sum(precipitaciones) if precipitaciones else 0
            viento_max_ms = max(vientos) if vientos else None

            # Hora de viento máximo
            hora_viento_max = None
            if vientos and viento_max_ms is not None:
                for f in todas_filas:
                    if f.get("velocidad_viento") == viento_max_ms:
                        if f.get("hora_inicio") and hasattr(f["hora_inicio"], "isoformat"):
                            hora_viento_max = f["hora_inicio"].isoformat()
                        elif f.get("hora_inicio"):
                            hora_viento_max = str(f["hora_inicio"])
                        break

            # Horas con precipitación (cantidad > 0.5mm)
            horas_con_precipitacion = sum(
                1 for f in todas_filas
                if (f.get("cantidad_precipitacion") or 0) > 0.5
            )

            # Tendencia de temperatura (últimas vs primeras horas disponibles)
            tendencia_temperatura = "estable"
            if len(temperaturas) >= 6:
                tercio = len(temperaturas) // 3
                temp_inicio = sum(temperaturas[:tercio]) / tercio
                temp_fin = sum(temperaturas[-tercio:]) / tercio
                diferencia = temp_fin - temp_inicio
                if diferencia < -2:
                    tendencia_temperatura = "bajando"
                elif diferencia > 2:
                    tendencia_temperatura = "subiendo"

            # Alertas automáticas
            alertas = []
            if precip_total_acumulada_mm > 30:
                alertas.append({
                    "tipo": "PRECIPITACION_CRITICA",
                    "valor": f"{round(precip_total_acumulada_mm, 1)}mm en 72h"
                })
            if viento_max_ms and viento_max_ms > 15:
                alertas.append({
                    "tipo": "VIENTO_FUERTE",
                    "hora": hora_viento_max,
                    "valor": f"{round(viento_max_ms, 1)} m/s ({round(viento_max_ms * 3.6, 1)} km/h)"
                })
            if temp_min_72h is not None and temp_max_72h is not None:
                if abs(temp_max_72h - temp_min_72h) > 15:
                    alertas.append({
                        "tipo": "CAMBIO_TERMICO",
                        "valor": f"variación de {round(abs(temp_max_72h - temp_min_72h), 1)}°C"
                    })

            return {
                "disponible": True,
                "temp_min_72h": round(temp_min_72h, 1) if temp_min_72h is not None else None,
                "temp_max_72h": round(temp_max_72h, 1) if temp_max_72h is not None else None,
                "precip_total_acumulada_mm": round(precip_total_acumulada_mm, 1),
                "viento_max_ms": round(viento_max_ms, 1) if viento_max_ms is not None else None,
                "hora_viento_max": hora_viento_max,
                "horas_con_precipitacion": horas_con_precipitacion,
                "tendencia_temperatura": tendencia_temperatura,
                "alertas": alertas
            }

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar tendencia meteorológica para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando tendencia meteorológica para {ubicacion}: {e}")
            return {"error": str(e)}

    def obtener_pronostico_proximos_dias(
        self,
        ubicacion: str,
        fecha_referencia: Optional[datetime] = None
    ) -> dict:
        """
        Próximos 3 días de pronostico_dias.

        Args:
            ubicacion: Nombre exacto de la ubicación
            fecha_referencia: datetime de referencia para datos históricos.
                Si es None, usa CURRENT_DATE() (comportamiento normal).
                Si se provee, filtra desde esa fecha.

        Returns:
            dict con lista de 3 días de pronóstico
        """
        logger.info(f"Consultando pronóstico de días para: {ubicacion}")
        # Resolver fecha de referencia: parámetro explícito tiene prioridad sobre global
        fecha_referencia = fecha_referencia or _fecha_referencia_global
        try:
            if fecha_referencia is None:
                sql = """
                    SELECT
                        fecha_inicio,
                        fecha_fin,
                        temp_max_dia,
                        temp_min_dia,
                        diurno_condicion,
                        nocturno_condicion,
                        diurno_prob_precipitacion,
                        nocturno_prob_precipitacion,
                        diurno_velocidad_viento,
                        nocturno_velocidad_viento
                    FROM `{proyecto}.{dataset}.pronostico_dias`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha_inicio >= TIMESTAMP(CURRENT_DATE())
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY DATE(fecha_inicio)
                        ORDER BY marca_tiempo_extraccion DESC
                    ) = 1
                    ORDER BY fecha_inicio ASC
                    LIMIT 5
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
                ]
            else:
                sql = """
                    SELECT
                        fecha_inicio,
                        fecha_fin,
                        temp_max_dia,
                        temp_min_dia,
                        diurno_condicion,
                        nocturno_condicion,
                        diurno_prob_precipitacion,
                        nocturno_prob_precipitacion,
                        diurno_velocidad_viento,
                        nocturno_velocidad_viento
                    FROM `{proyecto}.{dataset}.pronostico_dias`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha_inicio >= TIMESTAMP(DATE(@fecha_ref))
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY DATE(fecha_inicio)
                        ORDER BY marca_tiempo_extraccion DESC
                    ) = 1
                    ORDER BY fecha_inicio ASC
                    LIMIT 5
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter(
                        "fecha_ref", "TIMESTAMP", fecha_referencia
                    ),
                ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible": False,
                    "razon": "Sin pronóstico de días disponible"
                }

            # Serializar fechas
            dias = []
            for fila in filas:
                dia = dict(fila)
                for campo in ["fecha_inicio", "fecha_fin"]:
                    if dia.get(campo) and hasattr(dia[campo], "isoformat"):
                        dia[campo] = dia[campo].isoformat()
                    elif dia.get(campo):
                        dia[campo] = str(dia[campo])

                # Calcular prob_precipitacion_dia (máximo entre diurno y nocturno)
                prob_dia = dia.get("diurno_prob_precipitacion")
                prob_noche = dia.get("nocturno_prob_precipitacion")
                if prob_dia is not None and prob_noche is not None:
                    dia["prob_precipitacion_dia"] = max(prob_dia, prob_noche)
                elif prob_dia is not None:
                    dia["prob_precipitacion_dia"] = prob_dia
                elif prob_noche is not None:
                    dia["prob_precipitacion_dia"] = prob_noche

                # viento_max (máximo entre diurno y nocturno)
                viento_dia = dia.get("diurno_velocidad_viento")
                viento_noche = dia.get("nocturno_velocidad_viento")
                if viento_dia is not None and viento_noche is not None:
                    dia["viento_max"] = max(viento_dia, viento_noche)
                elif viento_dia is not None:
                    dia["viento_max"] = viento_dia
                elif viento_noche is not None:
                    dia["viento_max"] = viento_noche

                # condicion_dia (priorizar diurna)
                dia["condicion_dia"] = dia.get("diurno_condicion") or dia.get("nocturno_condicion")

                dias.append(dia)

            return {
                "disponible": True,
                "dias": dias
            }

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar pronóstico de días para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando pronóstico de días para {ubicacion}: {e}")
            return {"error": str(e)}

    def obtener_estado_satelital(
        self,
        ubicacion: str,
        fecha_referencia: Optional[datetime] = None
    ) -> dict:
        """
        Última fila de imagenes_satelitales. Max antigüedad: 48h.

        Args:
            ubicacion: Nombre exacto de la ubicación
            fecha_referencia: datetime de referencia para datos históricos.
                Si es None, usa CURRENT_DATE() (comportamiento normal).
                Si se provee, filtra datos respecto a esa fecha.

        Returns:
            dict con estado del manto nival, o {"disponible": False, "razon": "..."}
        """
        logger.info(f"Consultando estado satelital para: {ubicacion}")
        # Resolver fecha de referencia: parámetro explícito tiene prioridad sobre global
        fecha_referencia = fecha_referencia or _fecha_referencia_global
        try:
            if fecha_referencia is None:
                sql = """
                    SELECT
                        pct_cobertura_nieve,
                        ndsi_medio,
                        lst_dia_celsius,
                        lst_noche_celsius,
                        ciclo_diurno_amplitud,
                        snowline_elevacion_m,
                        delta_pct_nieve_24h,
                        tipo_cambio_nieve,
                        ami_7d,
                        ami_3d,
                        sar_disponible,
                        sar_pct_nieve_humeda,
                        transporte_eolico_activo,
                        viento_altura_vel_kmh,
                        fecha_captura
                    FROM `{proyecto}.{dataset}.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha_captura >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
                ]
            else:
                sql = """
                    SELECT
                        pct_cobertura_nieve,
                        ndsi_medio,
                        lst_dia_celsius,
                        lst_noche_celsius,
                        ciclo_diurno_amplitud,
                        snowline_elevacion_m,
                        delta_pct_nieve_24h,
                        tipo_cambio_nieve,
                        ami_7d,
                        ami_3d,
                        sar_disponible,
                        sar_pct_nieve_humeda,
                        transporte_eolico_activo,
                        viento_altura_vel_kmh,
                        fecha_captura
                    FROM `{proyecto}.{dataset}.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha_captura >= DATE_SUB(DATE(@fecha_ref), INTERVAL 2 DAY)
                      AND fecha_captura <= DATE(@fecha_ref)
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter(
                        "fecha_ref", "TIMESTAMP", fecha_referencia
                    ),
                ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                logger.warning(f"Sin datos satelitales recientes (<48h) para: {ubicacion}")
                return {
                    "disponible": False,
                    "razon": "sin datos <48h"
                }

            resultado = filas[0]
            resultado["disponible"] = True

            # Normalizar NDSI: BQ almacena en escala 0-100 (MODIS/Sentinel-2 escalado)
            # Los tools usan umbrales en escala [-1, 1] → dividir por 100
            for campo in ("ndsi_medio", "ndsi_max"):
                valor = resultado.get(campo)
                if valor is not None:
                    resultado[campo] = round(valor / 100.0, 4)

            # Serializar fecha
            if resultado.get("fecha_captura") and hasattr(resultado["fecha_captura"], "isoformat"):
                resultado["fecha_captura"] = resultado["fecha_captura"].isoformat()

            return resultado

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar estado satelital para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando estado satelital para {ubicacion}: {e}")
            return {"error": str(e)}

    def obtener_perfil_topografico(self, ubicacion: str) -> dict:
        """
        Última fila de zonas_avalancha. Puede tener hasta 45 días de antigüedad.

        Args:
            ubicacion: Nombre exacto de la ubicación

        Returns:
            dict con perfil topográfico e índice de riesgo base EAWS
        """
        logger.info(f"Consultando perfil topográfico para: {ubicacion}")
        try:
            sql = """
                SELECT
                    indice_riesgo_topografico,
                    clasificacion_riesgo,
                    peligro_eaws_base,
                    frecuencia_estimada_eaws,
                    tamano_estimado_eaws,
                    zona_inicio_ha,
                    zona_inicio_pct,
                    pendiente_max_inicio,
                    pendiente_media_inicio,
                    desnivel_inicio_deposito,
                    aspecto_predominante_inicio,
                    descripcion_riesgo,
                    fecha_analisis,
                    latitud,
                    hemisferio
                FROM `{proyecto}.{dataset}.zonas_avalancha`
                WHERE nombre_ubicacion = @ubicacion
                ORDER BY fecha_analisis DESC
                LIMIT 1
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            parametros = [
                bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
            ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible": False,
                    "razon": "Sin análisis topográfico disponible"
                }

            resultado = filas[0]
            resultado["disponible"] = True

            # Serializar fecha
            if resultado.get("fecha_analisis") and hasattr(resultado["fecha_analisis"], "isoformat"):
                resultado["fecha_analisis"] = resultado["fecha_analisis"].isoformat()

            # Computar campos derivados desde eaws_constantes
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../datos/analizador_avalanchas'))
            try:
                from eaws_constantes import categorizar_aspecto, es_aspecto_sombra, detectar_hemisferio
                aspecto = resultado.get("aspecto_predominante_inicio")
                latitud = resultado.get("latitud", -33.0)  # Andes chilenos como default
                hemisferio = resultado.get("hemisferio") or detectar_hemisferio(latitud)

                if aspecto is not None:
                    resultado["categoria_aspecto"] = categorizar_aspecto(aspecto)
                    resultado["es_aspecto_sombra"] = es_aspecto_sombra(aspecto, hemisferio)
                else:
                    resultado["categoria_aspecto"] = None
                    resultado["es_aspecto_sombra"] = None
            except ImportError as e:
                logger.warning(f"No se pudo importar eaws_constantes: {e}")
                resultado["categoria_aspecto"] = None
                resultado["es_aspecto_sombra"] = None

            return resultado

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar perfil topográfico para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando perfil topográfico para {ubicacion}: {e}")
            return {"error": str(e)}

    def obtener_pendientes_detalladas(self, ubicacion: str) -> dict:
        """
        Última fila de pendientes_detalladas para la ubicación.

        Contiene métricas detalladas de pendiente y aspecto calculadas con
        NASADEM via Earth Engine: distribución EAWS, histograma, índice de
        riesgo compuesto y áreas en hectáreas.

        Args:
            ubicacion: Nombre exacto de la ubicación

        Returns:
            dict con campos enriquecidos para el subagente topográfico,
            o {"disponible": False, "razon": "..."} si no hay datos
        """
        logger.info(f"Consultando pendientes detalladas para: {ubicacion}")
        try:
            sql = """
                SELECT
                    pct_optimo_avalancha,
                    pct_laderas_sur,
                    indice_riesgo_topografico,
                    pendiente_media,
                    pendiente_max,
                    pendiente_p90,
                    histograma_pendientes,
                    area_avalancha_ha,
                    pct_area_avalancha,
                    pct_terreno_moderado,
                    pct_inicio_posible,
                    pct_severo,
                    pct_paredes,
                    pendiente_p50,
                    elevacion_min,
                    elevacion_max,
                    elevacion_media,
                    desnivel_m,
                    aspecto_predominante,
                    area_total_ha,
                    fuente_dem,
                    resolucion_m,
                    radio_analisis_m,
                    fecha_analisis
                FROM `{proyecto}.{dataset}.pendientes_detalladas`
                WHERE nombre_ubicacion = @ubicacion
                ORDER BY fecha_analisis DESC
                LIMIT 1
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            parametros = [
                bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
            ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible": False,
                    "razon": "Sin análisis de pendientes detalladas disponible"
                }

            resultado = filas[0]
            resultado["disponible"] = True

            # Serializar fecha
            if resultado.get("fecha_analisis") and hasattr(resultado["fecha_analisis"], "isoformat"):
                resultado["fecha_analisis"] = resultado["fecha_analisis"].isoformat()

            # Deserializar histograma_pendientes (almacenado como JSON string)
            histograma_raw = resultado.get("histograma_pendientes")
            if histograma_raw and isinstance(histograma_raw, str):
                try:
                    import json
                    resultado["histograma_pendientes"] = json.loads(histograma_raw)
                except (ValueError, TypeError) as e_json:
                    logger.warning(
                        f"No se pudo deserializar histograma_pendientes para {ubicacion}: {e_json}"
                    )
                    resultado["histograma_pendientes"] = None

            return resultado

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error(f"Timeout al consultar pendientes detalladas para: {ubicacion}")
            return {"error": f"Timeout después de {self.TIMEOUT_SEGUNDOS}s"}
        except Exception as e:
            logger.error(f"Error consultando pendientes detalladas para {ubicacion}: {e}")
            return {"error": str(e)}

    def obtener_atributos_tagee_ae(self, ubicacion: str) -> dict:
        """
        Atributos TAGEE y embeddings AlphaEarth desde pendientes_detalladas.

        Columnas añadidas por el script actualizar_glo30_tagee_ae.py:
          - curvatura_horizontal_promedio, curvatura_vertical_promedio (TAGEE)
          - zonas_convergencia_runout  (conteo de celdas con curvatura positiva)
          - northness_promedio, eastness_promedio (TAGEE índices de aspecto)
          - embedding_centroide_zona   (ARRAY<FLOAT64>, 64 dimensiones AlphaEarth)
          - similitud_anios_previos    (JSON con drift interanual)
          - dem_fuente                 (COPERNICUS/DEM/GLO30 vs NASADEM)

        Retorna {"disponible": False} si las columnas no existen todavía
        (datos aún no generados con el script EE).
        """
        logger.info(f"Consultando atributos TAGEE+AE para: {ubicacion}")
        try:
            sql = """
                SELECT
                    curvatura_horizontal_promedio,
                    curvatura_vertical_promedio,
                    zonas_convergencia_runout,
                    northness_promedio,
                    eastness_promedio,
                    embedding_centroide_zona,
                    similitud_anios_previos,
                    dem_fuente,
                    fecha_analisis
                FROM `{proyecto}.{dataset}.pendientes_detalladas`
                WHERE nombre_ubicacion = @ubicacion
                  AND dem_fuente = 'COPERNICUS/DEM/GLO30'
                ORDER BY fecha_analisis DESC
                LIMIT 1
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            parametros = [
                bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion)
            ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible": False,
                    "razon": (
                        "Sin datos GLO-30/TAGEE/AlphaEarth. "
                        "Ejecutar: python agentes/datos/backfill/actualizar_glo30_tagee_ae.py"
                    )
                }

            resultado = filas[0]
            resultado["disponible"] = True

            # Deserializar embedding (almacenado como JSON string o lista)
            emb = resultado.get("embedding_centroide_zona")
            if emb and isinstance(emb, str):
                import json
                try:
                    resultado["embedding_centroide_zona"] = json.loads(emb)
                except (ValueError, TypeError):
                    resultado["embedding_centroide_zona"] = None

            # Deserializar similitud interanual
            sim = resultado.get("similitud_anios_previos")
            if sim and isinstance(sim, str):
                import json
                try:
                    resultado["similitud_anios_previos"] = json.loads(sim)
                except (ValueError, TypeError):
                    resultado["similitud_anios_previos"] = {}

            if resultado.get("fecha_analisis") and hasattr(resultado["fecha_analisis"], "isoformat"):
                resultado["fecha_analisis"] = resultado["fecha_analisis"].isoformat()

            return resultado

        except Exception as e:
            # Columnas nuevas aún no en schema → retorno gracioso
            if "Unrecognized name" in str(e) or "Not found" in str(e):
                return {
                    "disponible": False,
                    "razon": "Columnas TAGEE/AE no existen aún en pendientes_detalladas"
                }
            logger.error(f"Error consultando TAGEE/AE para {ubicacion}: {e}")
            return {"disponible": False, "razon": str(e)}

    def listar_ubicaciones_con_datos(self) -> list:
        """
        Ubicaciones con condiciones_actuales en las últimas 24h.

        Returns:
            Lista de nombres de ubicaciones con datos recientes
        """
        logger.info("Listando ubicaciones con datos recientes")
        try:
            sql = """
                SELECT DISTINCT nombre_ubicacion
                FROM `{proyecto}.{dataset}.condiciones_actuales`
                WHERE hora_actual >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                ORDER BY nombre_ubicacion ASC
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            filas = self._ejecutar_query(sql, [])
            ubicaciones = [f["nombre_ubicacion"] for f in filas]

            logger.info(f"Se encontraron {len(ubicaciones)} ubicaciones con datos recientes")
            return ubicaciones

        except (google_exceptions.DeadlineExceeded, concurrent.futures.TimeoutError):
            logger.error("Timeout al listar ubicaciones")
            return []
        except Exception as e:
            logger.error(f"Error listando ubicaciones: {e}")
            return []

    def obtener_relatos_ubicacion(self, ubicacion: str, limite: int = 20) -> dict:
        """
        Rutas Andeshandbook para la ubicación o zona cercana.

        Busca por similitud en location/name/sector con LIKE para encontrar
        rutas aunque el nombre no sea exacto.

        Args:
            ubicacion: Nombre de la ubicación (busca coincidencias parciales)
            limite: Número máximo de rutas a retornar (default: 20)

        Returns:
            dict con lista de rutas y metadatos de búsqueda
        """
        logger.info(f"Buscando rutas para ubicación: {ubicacion}")
        try:
            # Extraer palabra clave de la ubicación (ej: "La Parva Sector Bajo" → "La Parva")
            palabras = ubicacion.split()
            termino_busqueda = " ".join(palabras[:3]) if len(palabras) >= 3 else ubicacion

            sql = """
                SELECT
                    route_id,
                    name,
                    location,
                    sector,
                    SUBSTR(description, 1, 500) as fragmento_descripcion,
                    avalanche_info,
                    has_avalanche_info,
                    is_alta_montana,
                    llm_nivel_riesgo,
                    llm_puntuacion_riesgo,
                    llm_resumen,
                    url,
                    scraped_timestamp
                FROM `{proyecto}.{dataset}.relatos_montanistas`
                WHERE
                    LOWER(location) LIKE LOWER(@termino)
                    OR LOWER(name) LIKE LOWER(@termino)
                    OR LOWER(sector) LIKE LOWER(@termino)
                ORDER BY scraped_timestamp DESC
                LIMIT @limite
            """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

            parametros = [
                bigquery.ScalarQueryParameter("termino", "STRING", f"%{termino_busqueda}%"),
                bigquery.ScalarQueryParameter("limite", "INT64", limite),
            ]

            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                # Si no hay resultados exactos, buscar por primera palabra (zona general)
                primera_palabra = palabras[0]
                sql_amplio = sql.replace("@termino", "@termino_amplio")
                parametros_amplio = [
                    bigquery.ScalarQueryParameter("termino_amplio", "STRING", f"%{primera_palabra}%"),
                    bigquery.ScalarQueryParameter("limite", "INT64", limite),
                ]
                filas = self._ejecutar_query(sql_amplio, parametros_amplio)

            # Serializar timestamps
            for fila in filas:
                if fila.get("scraped_timestamp") and hasattr(fila["scraped_timestamp"], "isoformat"):
                    fila["scraped_timestamp"] = fila["scraped_timestamp"].isoformat()

            logger.info(f"  {len(filas)} rutas encontradas para: {ubicacion}")
            return {
                "disponible": True,
                "relatos": filas,
                "total_encontrados": len(filas),
                "termino_busqueda": termino_busqueda,
                "fuente": "andeshandbook_rutas",
            }

        except Exception as e:
            tabla_msg = "relatos_montanistas no existe" if "Not found" in str(e) else str(e)
            logger.warning(f"Error buscando rutas para {ubicacion}: {tabla_msg}")
            return {
                "disponible": False,
                "relatos": [],
                "total_encontrados": 0,
                "razon": tabla_msg,
            }

    def obtener_stats_terreno_st(self, ubicacion: str) -> dict:
        """
        Calcula estadísticas de terreno usando ST_REGIONSTATS directamente en BigQuery.

        Usa NASADEM (NASA/NASADEM_HGT/001) como DEM de referencia rápida, sin
        necesidad de exportar desde Earth Engine. Complementa obtener_atributos_tagee_ae()
        con estadísticas adicionales disponibles en tiempo real.

        Args:
            ubicacion: Nombre de la zona objetivo

        Returns:
            dict con elevacion_media, elevacion_std, elevacion_min, elevacion_max,
            area_km2 y metadatos de zona desde zonas_objetivo.
        """
        inicio = time.time()
        logger.info(f"[ConsultorBigQuery] ST_REGIONSTATS terreno → {ubicacion}")
        try:
            sql = """
                SELECT
                  z.nombre_zona,
                  z.lat_centroide,
                  z.lon_centroide,
                  z.elevacion_min_m,
                  z.elevacion_max_m,
                  z.exposicion_predominante,
                  z.region_eaws,
                  ROUND(ST_AREA(z.geometria) / 1e6, 2) AS area_km2,
                  ROUND(ST_REGIONSTATS(
                    z.geometria,
                    'ee://NASA/NASADEM_HGT/001',
                    'elevation'
                  ).mean, 1) AS nasadem_elevacion_media_m,
                  ROUND(ST_REGIONSTATS(
                    z.geometria,
                    'ee://NASA/NASADEM_HGT/001',
                    'elevation'
                  ).stddev, 1) AS nasadem_elevacion_std_m,
                  ROUND(ST_REGIONSTATS(
                    z.geometria,
                    'ee://USGS/SRTMGL1_003',
                    'elevation'
                  ).mean, 1) AS srtm_elevacion_media_m
                FROM `climas-chileno.clima.zonas_objetivo` z
                WHERE z.nombre_zona = @zona
                LIMIT 1
            """
            parametros_st = [
                bigquery.ScalarQueryParameter("zona", "STRING", ubicacion),
            ]
            filas = self._ejecutar_query(sql, parametros_st)
            if not filas:
                return {"disponible": False, "razon": f"Zona '{ubicacion}' no encontrada en zonas_objetivo"}

            fila = dict(filas[0])
            fila["disponible"] = True
            fila["fuente_dem"] = "NASADEM+SRTM via ST_REGIONSTATS"
            fila["latencia_ms"] = round((time.time() - inicio) * 1000)
            logger.info(
                f"  ST_REGIONSTATS OK: elev_media={fila.get('nasadem_elevacion_media_m')}m "
                f"({fila['latencia_ms']}ms)"
            )
            return fila

        except Exception as exc:
            logger.warning(f"Error ST_REGIONSTATS para {ubicacion}: {exc}")
            return {"disponible": False, "razon": str(exc)}

    def obtener_zona_geografica(self, ubicacion: str) -> dict:
        """
        Retorna metadata geográfica de la zona desde la tabla zonas_objetivo.

        Útil para obtener el polígono, área, centroide y elevaciones de referencia
        sin necesidad de hardcodear coordenadas en los subagentes.

        Args:
            ubicacion: Nombre de la zona objetivo

        Returns:
            dict con nombre_zona, geometria (GeoJSON), lat/lon centroide, área y metadata
        """
        logger.info(f"[ConsultorBigQuery] zona geográfica → {ubicacion}")
        try:
            sql = """
                SELECT
                  nombre_zona,
                  ST_AsGeoJSON(geometria) AS geometria_geojson,
                  lat_centroide,
                  lon_centroide,
                  ROUND(ST_AREA(geometria) / 1e6, 2) AS area_km2,
                  elevacion_min_m,
                  elevacion_max_m,
                  exposicion_predominante,
                  region_eaws
                FROM `climas-chileno.clima.zonas_objetivo`
                WHERE nombre_zona = @zona
                LIMIT 1
            """
            parametros = [
                bigquery.ScalarQueryParameter("zona", "STRING", ubicacion),
            ]
            filas = self._ejecutar_query(sql, parametros)
            if not filas:
                return {"disponible": False, "razon": f"Zona '{ubicacion}' no encontrada"}

            fila = dict(filas[0])
            fila["disponible"] = True
            return fila

        except Exception as exc:
            logger.warning(f"Error obteniendo zona geográfica {ubicacion}: {exc}")
            return {"disponible": False, "razon": str(exc)}

    def obtener_historial_boletines(self, ubicacion: str, n_dias: int = 7) -> dict:
        """
        Retorna los últimos N días de boletines propios para calcular features de persistencia.

        Usado por tool_historial_ubicacion (S5) para detectar calma sostenida vs calma puntual.

        Args:
            ubicacion: nombre de la ubicación
            n_dias: ventana temporal en días (default: 7)

        Returns:
            dict con lista de boletines ordenados por fecha DESC y métricas derivadas
        """
        logger.info(f"[ConsultorBigQuery] historial boletines → {ubicacion} (últimos {n_dias} días)")
        try:
            fecha_ref = _fecha_referencia_global or datetime.now(timezone.utc)
            sql = """
                SELECT
                    DATE(fecha_emision) AS fecha,
                    nivel_eaws_24h,
                    factor_meteorologico,
                    confianza
                FROM `climas-chileno.clima.boletines_riesgo`
                WHERE nombre_ubicacion = @ubicacion
                  AND fecha_emision >= TIMESTAMP_SUB(@fecha_ref, INTERVAL @n_dias DAY)
                  AND fecha_emision < @fecha_ref
                ORDER BY fecha_emision DESC
                LIMIT 14
            """
            parametros_hist = [
                bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                bigquery.ScalarQueryParameter("fecha_ref", "TIMESTAMP", fecha_ref),
                bigquery.ScalarQueryParameter("n_dias", "INT64", n_dias),
            ]
            filas = self._ejecutar_query(sql, parametros_hist)

            if not filas:
                return {
                    "disponible": True,
                    "boletines": [],
                    "n_boletines": 0,
                    "dias_consecutivos_nivel_bajo": 0,
                    "nivel_promedio_7d": None,
                    "tendencia_historica": 0,
                    "sin_historial": True,
                }

            boletines = []
            for f in filas:
                boletines.append({
                    "fecha": str(f["fecha"]),
                    "nivel_eaws_24h": int(f["nivel_eaws_24h"]) if f["nivel_eaws_24h"] else None,
                    "factor_meteorologico": f.get("factor_meteorologico", "ESTABLE"),
                    "confianza": f.get("confianza", "Media"),
                })

            niveles = [b["nivel_eaws_24h"] for b in boletines if b["nivel_eaws_24h"] is not None]

            # días consecutivos con nivel ≤ 2 (desde el más reciente hacia atrás)
            dias_bajos = 0
            for b in boletines:
                if b["nivel_eaws_24h"] is not None and b["nivel_eaws_24h"] <= 2:
                    dias_bajos += 1
                else:
                    break

            nivel_promedio = round(sum(niveles) / len(niveles), 2) if niveles else None

            # tendencia: nivel más reciente - nivel más antiguo de la ventana (negativo = bajando)
            tendencia = int(niveles[0] - niveles[-1]) if len(niveles) >= 2 else 0

            return {
                "disponible": True,
                "boletines": boletines,
                "n_boletines": len(boletines),
                "dias_consecutivos_nivel_bajo": dias_bajos,
                "nivel_promedio_7d": nivel_promedio,
                "tendencia_historica": tendencia,
                "sin_historial": False,
            }

        except Exception as exc:
            logger.warning(f"Error historial boletines {ubicacion}: {exc}")
            return {
                "disponible": False,
                "boletines": [],
                "n_boletines": 0,
                "dias_consecutivos_nivel_bajo": 0,
                "nivel_promedio_7d": None,
                "tendencia_historica": 0,
                "razon": str(exc),
            }

    def obtener_sar_baseline(
        self,
        ubicacion: str,
        n_dias_reciente: int = 7,
        n_dias_baseline: int = 45,
    ) -> dict:
        """
        Calcula el índice de humedad SAR Sentinel-1 comparando VV reciente vs baseline estacional.

        Estrategia:
          - Baseline: media de sar_vv_medio_db en ventana [n_dias_baseline, n_dias_reciente] días atrás
            (excluye la semana más reciente para que el baseline no sea afectado por el evento actual)
          - Reciente: VV más reciente dentro de los últimos n_dias_reciente días
          - Delta: vv_reciente - baseline_vv (negativo → más húmedo → manto activado)

        Interpretación EAWS:
          delta < -3 dB → superficie húmeda → manto activo → riesgo nieve húmeda
          delta estable o positivo → superficie seca → manto consolidado

        Args:
            ubicacion: nombre de la ubicación
            n_dias_reciente: ventana de búsqueda de SAR más reciente en días (default: 7)
            n_dias_baseline: ventana para calcular el baseline estacional en días (default: 45)

        Returns:
            dict con sar_vv_db_reciente, sar_baseline_vv, sar_delta_baseline,
            sar_pct_nieve_humeda, humedad_activa, disponible
        """
        logger.info(
            f"[ConsultorBigQuery] SAR baseline → {ubicacion} "
            f"(reciente ≤{n_dias_reciente}d, baseline {n_dias_reciente}-{n_dias_baseline}d)"
        )
        try:
            _fref = _fecha_referencia_global
            if _fref is not None:
                sql_reciente = """
                    SELECT
                        sar_vv_medio_db,
                        sar_pct_nieve_humeda,
                        sar_pct_nieve_seca,
                        fecha_captura
                    FROM `climas-chileno.clima.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND sar_disponible = TRUE
                      AND fecha_captura >= DATE_SUB(DATE(@fecha_ref), INTERVAL @n_reciente DAY)
                      AND fecha_captura <= DATE(@fecha_ref)
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                """
                parametros_reciente = [
                    bigquery.ScalarQueryParameter("ubicacion",  "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_reciente", "INT64",  n_dias_reciente),
                    bigquery.ScalarQueryParameter("fecha_ref",  "TIMESTAMP", _fref),
                ]
                sql_baseline = """
                    SELECT AVG(sar_vv_medio_db) AS baseline_vv
                    FROM `climas-chileno.clima.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND sar_disponible = TRUE
                      AND fecha_captura >= DATE_SUB(DATE(@fecha_ref), INTERVAL @n_baseline DAY)
                      AND fecha_captura <  DATE_SUB(DATE(@fecha_ref), INTERVAL @n_reciente DAY)
                """
                parametros_baseline = [
                    bigquery.ScalarQueryParameter("ubicacion",  "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_baseline", "INT64",  n_dias_baseline),
                    bigquery.ScalarQueryParameter("n_reciente", "INT64",  n_dias_reciente),
                    bigquery.ScalarQueryParameter("fecha_ref",  "TIMESTAMP", _fref),
                ]
            else:
                sql_reciente = """
                    SELECT
                        sar_vv_medio_db,
                        sar_pct_nieve_humeda,
                        sar_pct_nieve_seca,
                        fecha_captura
                    FROM `climas-chileno.clima.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND sar_disponible = TRUE
                      AND fecha_captura >= DATE_SUB(CURRENT_DATE(), INTERVAL @n_reciente DAY)
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                """
                parametros_reciente = [
                    bigquery.ScalarQueryParameter("ubicacion",  "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_reciente", "INT64",  n_dias_reciente),
                ]
                sql_baseline = """
                    SELECT AVG(sar_vv_medio_db) AS baseline_vv
                    FROM `climas-chileno.clima.imagenes_satelitales`
                    WHERE nombre_ubicacion = @ubicacion
                      AND sar_disponible = TRUE
                      AND fecha_captura >= DATE_SUB(CURRENT_DATE(), INTERVAL @n_baseline DAY)
                      AND fecha_captura <  DATE_SUB(CURRENT_DATE(), INTERVAL @n_reciente DAY)
                """
                parametros_baseline = [
                    bigquery.ScalarQueryParameter("ubicacion",  "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_baseline", "INT64",  n_dias_baseline),
                    bigquery.ScalarQueryParameter("n_reciente", "INT64",  n_dias_reciente),
                ]
            filas_reciente = self._ejecutar_query(sql_reciente, parametros_reciente)
            filas_baseline = self._ejecutar_query(sql_baseline, parametros_baseline)

            if not filas_reciente:
                return {
                    "disponible":          False,
                    "razon":               "sin datos SAR recientes en imagenes_satelitales",
                    "sar_vv_db_reciente":  None,
                    "sar_baseline_vv":     None,
                    "sar_delta_baseline":  None,
                    "sar_pct_nieve_humeda": None,
                    "humedad_activa":      False,
                }

            vv_reciente = filas_reciente[0].get("sar_vv_medio_db")
            pct_humeda  = filas_reciente[0].get("sar_pct_nieve_humeda")

            baseline_vv = None
            if filas_baseline and filas_baseline[0].get("baseline_vv") is not None:
                baseline_vv = round(float(filas_baseline[0]["baseline_vv"]), 3)

            delta = None
            if vv_reciente is not None and baseline_vv is not None:
                delta = round(float(vv_reciente) - float(baseline_vv), 3)

            # VV cae >3 dB respecto al baseline → humedad superficial activa (Nagler 2016)
            humedad_activa = delta is not None and delta < -3.0

            logger.info(
                f"[ConsultorBigQuery] SAR '{ubicacion}': "
                f"VV_reciente={vv_reciente} dB, baseline={baseline_vv} dB, "
                f"delta={delta} dB, humedad_activa={humedad_activa}"
            )

            return {
                "disponible":           True,
                "sar_vv_db_reciente":   round(float(vv_reciente), 3) if vv_reciente else None,
                "sar_baseline_vv":      baseline_vv,
                "sar_delta_baseline":   delta,
                "sar_pct_nieve_humeda": round(float(pct_humeda), 2) if pct_humeda else None,
                "humedad_activa":       humedad_activa,
                "fecha_sar":            str(filas_reciente[0].get("fecha_captura", "")),
            }

        except Exception as exc:
            logger.warning(f"Error SAR baseline {ubicacion}: {exc}")
            return {
                "disponible":          False,
                "razon":               str(exc),
                "sar_vv_db_reciente":  None,
                "sar_baseline_vv":     None,
                "sar_delta_baseline":  None,
                "sar_pct_nieve_humeda": None,
                "humedad_activa":      False,
            }

    def obtener_estado_manto(self, ubicacion: str, n_dias: int = 7) -> dict:
        """
        Consulta estado térmico del manto: MODIS LST + ERA5-Land temperatura suelo.

        Usado por tool_estado_manto (S2) para detectar señales positivas de estabilidad:
        manto frío sostenido, activación térmica y metamorfismo cinético.

        Args:
            ubicacion: nombre de la ubicación
            n_dias: ventana temporal en días (default: 7)

        Returns:
            dict con lst_celsius_medio_7d, dias_lst_positivo, gradiente_termico_medio,
            manto_frio (bool), metamorfismo_cinetico_posible (bool), disponible
        """
        logger.info(f"[ConsultorBigQuery] estado manto → {ubicacion} (últimos {n_dias} días)")
        try:
            _fref = _fecha_referencia_global
            _cols = """
                    fecha,
                    lst_celsius,
                    temp_suelo_l1_celsius,
                    temp_suelo_l2_celsius,
                    gradiente_termico,
                    cobertura_nubosa_pct,
                    fuente_lst"""
            if _fref is not None:
                sql = f"""
                    SELECT{_cols}
                    FROM `climas-chileno.clima.estado_manto_gee`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha >= DATE_SUB(DATE(@fecha_ref), INTERVAL @n_dias DAY)
                      AND fecha <= DATE(@fecha_ref)
                    ORDER BY fecha DESC
                    LIMIT 14
                """
                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_dias", "INT64", n_dias),
                    bigquery.ScalarQueryParameter("fecha_ref", "TIMESTAMP", _fref),
                ]
            else:
                sql = f"""
                    SELECT{_cols}
                    FROM `climas-chileno.clima.estado_manto_gee`
                    WHERE nombre_ubicacion = @ubicacion
                      AND fecha >= DATE_SUB(CURRENT_DATE(), INTERVAL @n_dias DAY)
                    ORDER BY fecha DESC
                    LIMIT 14
                """
                parametros = [
                    bigquery.ScalarQueryParameter("ubicacion", "STRING", ubicacion),
                    bigquery.ScalarQueryParameter("n_dias", "INT64", n_dias),
                ]
            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible":               False,
                    "sin_datos":                True,
                    "razon":                    "sin registros en estado_manto_gee para esta ubicación",
                    "lst_celsius_medio_7d":     None,
                    "dias_lst_positivo":        0,
                    "gradiente_termico_medio":  None,
                }

            lst_vals  = [f["lst_celsius"] for f in filas if f.get("lst_celsius") is not None]
            grad_vals = [f["gradiente_termico"] for f in filas if f.get("gradiente_termico") is not None]

            # días consecutivos con LST > 0°C desde el más reciente hacia atrás
            dias_lst_positivo = 0
            for fila in filas:
                if fila.get("lst_celsius") is not None and fila["lst_celsius"] > 0.0:
                    dias_lst_positivo += 1
                else:
                    break

            lst_medio  = round(sum(lst_vals) / len(lst_vals), 2) if lst_vals else None
            grad_medio = round(sum(grad_vals) / len(grad_vals), 3) if grad_vals else None

            manto_frio   = lst_medio is not None and lst_medio < -3.0
            metamorfismo = grad_medio is not None and grad_medio < -1.0

            return {
                "disponible":                   True,
                "sin_datos":                    False,
                "n_registros":                  len(filas),
                "lst_celsius_medio_7d":         lst_medio,
                "dias_lst_positivo":            dias_lst_positivo,
                "gradiente_termico_medio":      grad_medio,
                "temp_suelo_l1_celsius":        filas[0].get("temp_suelo_l1_celsius"),
                "temp_suelo_l2_celsius":        filas[0].get("temp_suelo_l2_celsius"),
                "manto_frio":                   manto_frio,
                "metamorfismo_cinetico_posible": metamorfismo,
                "fuente_lst":                   filas[0].get("fuente_lst"),
                "registros": [
                    {
                        "fecha":             str(f["fecha"]),
                        "lst_celsius":       f.get("lst_celsius"),
                        "gradiente_termico": f.get("gradiente_termico"),
                    }
                    for f in filas[:5]
                ],
            }

        except Exception as exc:
            logger.warning(f"Error consultando estado manto {ubicacion}: {exc}")
            return {
                "disponible":               False,
                "sin_datos":                True,
                "razon":                    str(exc),
                "lst_celsius_medio_7d":     None,
                "dias_lst_positivo":        0,
                "gradiente_termico_medio":  None,
            }

    def buscar_relatos_condiciones(self, terminos: list, limite: int = 10) -> dict:
        """
        Busca relatos que mencionen términos específicos de condiciones de riesgo.

        Útil para el AgenteSituationalBriefing para encontrar patrones históricos relacionados
        con condiciones actuales (ej: "placa", "viento", "nieve blanda").

        Args:
            terminos: Lista de palabras clave a buscar en el texto de relatos
            limite: Número máximo de relatos por término (default: 10)

        Returns:
            dict con fragmentos relevantes, frecuencias y patrones detectados
        """
        logger.info(f"Buscando relatos con términos: {terminos}")
        if not terminos:
            return {"disponible": False, "razon": "Lista de términos vacía"}

        try:
            resultados_por_termino = {}
            todos_los_ids = set()

            for termino in terminos[:8]:  # Limitar a 8 términos para no saturar BQ
                sql = """
                    SELECT
                        route_id,
                        name,
                        location,
                        SUBSTR(COALESCE(avalanche_info, description, ''), 1, 300) as fragmento,
                        scraped_timestamp,
                        location as ubicacion_mencionada,
                        @termino as termino_encontrado
                    FROM `{proyecto}.{dataset}.relatos_montanistas`
                    WHERE LOWER(description) LIKE LOWER(CONCAT('%', @termino, '%'))
                       OR LOWER(avalanche_info) LIKE LOWER(CONCAT('%', @termino, '%'))
                       OR LOWER(mountain_characteristics) LIKE LOWER(CONCAT('%', @termino, '%'))
                    ORDER BY scraped_timestamp DESC
                    LIMIT @limite
                """.format(proyecto=self.GCP_PROJECT, dataset=self.DATASET)

                parametros = [
                    bigquery.ScalarQueryParameter("termino", "STRING", termino),
                    bigquery.ScalarQueryParameter("limite", "INT64", limite),
                ]

                filas = self._ejecutar_query(sql, parametros)

                # Serializar timestamps
                for fila in filas:
                    if fila.get("scraped_timestamp") and hasattr(fila["scraped_timestamp"], "isoformat"):
                        fila["scraped_timestamp"] = fila["scraped_timestamp"].isoformat()
                    todos_los_ids.add(str(fila.get("route_id", "")))

                if filas:
                    resultados_por_termino[termino] = filas
                    logger.info(f"  '{termino}': {len(filas)} coincidencias")

            # Calcular índice de riesgo histórico basado en frecuencia de términos críticos
            terminos_criticos = {"alud", "avalancha", "placa", "peligroso", "inestable", "grieta"}
            frecuencia_criticos = sum(
                len(v) for k, v in resultados_por_termino.items()
                if k.lower() in terminos_criticos
            )
            total_menciones = sum(len(v) for v in resultados_por_termino.values())
            indice_riesgo = min(1.0, frecuencia_criticos / max(total_menciones, 1))

            return {
                "disponible": True,
                "resultados_por_termino": resultados_por_termino,
                "total_relatos_unicos": len(todos_los_ids),
                "total_menciones": total_menciones,
                "frecuencia_terminos_criticos": frecuencia_criticos,
                "indice_riesgo_calculado": round(indice_riesgo, 3),
                "terminos_buscados": terminos,
            }

        except Exception as e:
            tabla_msg = "relatos_montanistas no existe" if "Not found" in str(e) else str(e)
            logger.warning(f"Error buscando relatos por condiciones: {tabla_msg}")
            return {
                "disponible": False,
                "resultados_por_termino": {},
                "total_relatos_unicos": 0,
                "indice_riesgo_calculado": 0.0,
                "razon": tabla_msg,
            }

    def obtener_snow_depth_caro(
        self,
        estacion: str,
        fecha_inicio: str,
        fecha_fin: str,
        qc_status: str = "clean",
        apply_qc: bool = False,
    ) -> dict:
        """
        Consulta observaciones de profundidad de nieve del dataset Caro et al. 2026.

        Referencia: Medina & Caro (2026), doi:10.5281/zenodo.20089265

        Args:
            estacion: station_name o station_id de la estación.
            fecha_inicio: fecha inicio ISO 'YYYY-MM-DD'.
            fecha_fin: fecha fin ISO 'YYYY-MM-DD'.
            qc_status: 'raw' | 'clean' (default: 'clean').
            apply_qc: si True, aplica pipeline QC de datos/qc/snow_depth_qc.py
                      sobre la serie retornada (solo útil para qc_status='raw').

        Returns:
            dict con: disponible, estacion, n_observaciones, observaciones (lista),
                      metadata_estacion, pci (si apply_qc=True).
        """
        logger.info(
            f"[ConsultorBigQuery] snow_depth_caro → {estacion} "
            f"({fecha_inicio}–{fecha_fin}, qc_status={qc_status})"
        )
        try:
            sql = """
                SELECT
                  station_id, station_name, basin, andean_zone, elevation_m,
                  observation_date, snow_depth_cm, data_source, sensor_model
                FROM `climas-chileno.clima.snow_depth_caro_2026`
                WHERE (station_name = @estacion OR station_id = @estacion)
                  AND qc_status = @qc_status
                  AND observation_date BETWEEN @fecha_inicio AND @fecha_fin
                ORDER BY observation_date
            """
            parametros = [
                bigquery.ScalarQueryParameter("estacion", "STRING", estacion),
                bigquery.ScalarQueryParameter("qc_status", "STRING", qc_status),
                bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
                bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
            ]
            filas = self._ejecutar_query(sql, parametros)

            if not filas:
                return {
                    "disponible": False,
                    "sin_datos": True,
                    "razon": f"Sin observaciones para '{estacion}' en rango {fecha_inicio}–{fecha_fin}",
                }

            meta = {
                k: filas[0].get(k)
                for k in ["station_id", "station_name", "basin", "andean_zone", "elevation_m", "data_source"]
            }
            observaciones = [
                {"fecha": str(f["observation_date"]), "snow_depth_cm": f["snow_depth_cm"]}
                for f in filas
            ]

            resultado: dict = {
                "disponible": True,
                "estacion": meta["station_name"],
                "n_observaciones": len(observaciones),
                "metadata_estacion": meta,
                "observaciones": observaciones,
                "qc_status": qc_status,
            }

            if apply_qc:
                # Importación lazy: no afecta a módulos que no usan pandas
                import pandas as pd
                from datos.qc.snow_depth_qc import PARAMETROS_POR_ZONA, aplicar_pipeline_qc

                zona_map = {
                    "Mediterranean": "mediterranea",
                    "Arid": "arida",
                    "Wet": "humeda",
                }
                zona_clave = zona_map.get(meta.get("andean_zone", ""), "mediterranea")
                params_qc = PARAMETROS_POR_ZONA[zona_clave]

                indice = pd.to_datetime([obs["fecha"] for obs in observaciones])
                serie = pd.Series(
                    [obs["snow_depth_cm"] for obs in observaciones],
                    index=indice,
                    dtype=float,
                )
                serie_qc = aplicar_pipeline_qc(serie, params_qc)

                n_original = serie.notna().sum()
                n_qc = serie_qc.notna().sum()
                n_spikes = int(n_original - n_qc)
                pct_removido = round(n_spikes / max(n_original, 1) * 100, 2)

                logger.info(
                    f"[ConsultorBigQuery] QC aplicado → spikes={n_spikes} pct_removido={pct_removido}%"
                )

                # Actualizar observaciones con valores post-QC
                resultado["observaciones"] = [
                    {"fecha": str(d.date()), "snow_depth_cm": (None if pd.isna(v) else v)}
                    for d, v in zip(serie_qc.index, serie_qc.values)
                ]
                resultado["qc_aplicado"] = True
                resultado["qc_metricas"] = {
                    "n_spikes_detectados": n_spikes,
                    "pct_removido": pct_removido,
                    "zona_parametros": zona_clave,
                }

            return resultado

        except Exception as e:
            logger.warning(f"[ConsultorBigQuery] Error obteniendo snow_depth_caro: {e}")
            return {
                "disponible": False,
                "razon": str(e),
            }
