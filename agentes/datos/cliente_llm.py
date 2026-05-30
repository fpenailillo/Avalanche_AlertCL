"""
cliente_llm.py — Abstracción multi-proveedor de cliente LLM.

Soporta dos proveedores:
  - "anthropic"  → Claude (pago, reservado para validación final)
  - "databricks" → Databricks AI Gateway / OpenAI-compatible (gratuito, uso general)

Normaliza las respuestas de Databricks al formato Anthropic para que
base_subagente.py no requiera cambios en el agentic loop.

Variables de entorno:
    DATABRICKS_TOKEN    — token de acceso Databricks (dapi...)
    DATABRICKS_BASE_URL — URL del AI Gateway (con /mlflow/v1)
    DATABRICKS_MODEL    — nombre del modelo (por defecto: qwen3-next-80b-a3b-instruct)
    ANTHROPIC_API_KEY   — clave Anthropic (solo para validación)
    CLAUDE_CODE_OAUTH_TOKEN — token OAuth Claude (alternativa a API key)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# ─── Estructuras de respuesta normalizadas (formato Anthropic) ────────────────


@dataclass
class BloqueTexto:
    text: str
    type: str = "text"


@dataclass
class BloqueThought:
    """Pensamiento interno de Gemini 3.x — debe preservarse entre turnos."""
    text: str
    thought_signature: Optional[str] = None
    type: str = "thought"


@dataclass
class BloqueToolUse:
    id: str
    name: str
    input: dict
    type: str = "tool_use"
    thought_signature: Optional[bytes] = None  # Gemini 3.x: preservar entre turnos


@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class RespuestaNormalizada:
    """Respuesta normalizada al formato Anthropic para uso en base_subagente."""
    stop_reason: str       # "end_turn" | "tool_use"
    content: List[Any]     # lista de BloqueTexto | BloqueToolUse
    usage: _Usage


# ─── Cliente Anthropic ────────────────────────────────────────────────────────

class ClienteAnthropic:
    """Wrapper del SDK Anthropic. Retorna respuestas nativas (sin normalizar)."""

    def __init__(self):
        import anthropic
        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        self._sdk = anthropic
        if token:
            self._cliente = anthropic.Anthropic(auth_token=token)
        else:
            self._cliente = anthropic.Anthropic()
        logger.debug("ClienteAnthropic inicializado")

    @property
    def errores_recuperables(self):
        """Tupla de excepciones que se deben reintentar."""
        return (
            self._sdk.RateLimitError,
            self._sdk.APIConnectionError,
        )

    @property
    def error_servidor(self):
        return self._sdk.APIStatusError

    def crear_mensaje(self, *, model, max_tokens, system, tools, messages):
        # FIX-LLM-DETER (v20.0): temperature=0.0 para runs determinísticos.
        # Anthropic no soporta seed; top_k=1 compensa parcialmente.
        return self._cliente.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            temperature=0.0,
        )


# ─── Cliente Databricks (OpenAI-compatible) ───────────────────────────────────

class ClienteDatabricks:
    """
    Wrapper del SDK OpenAI apuntando al Databricks AI Gateway.
    Convierte tool definitions Anthropic → OpenAI y normaliza la respuesta
    de vuelta al formato Anthropic para que base_subagente.py no cambie.
    """

    MODELO_DEFAULT = "databricks-qwen3-next-80b-a3b-instruct"
    BASE_URL_DEFAULT = (
        "https://2113388677481041.ai-gateway.cloud.databricks.com/mlflow/v1"
    )
    SECRET_NAME = "projects/climas-chileno/secrets/databricks-token/versions/latest"

    def __init__(self):
        try:
            from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError
        except ImportError as exc:
            raise ImportError(
                "Paquete 'openai' requerido para ClienteDatabricks. "
                "Instalar con: pip install openai"
            ) from exc

        self._RateLimitError = RateLimitError
        self._APIConnectionError = APIConnectionError
        self._APIStatusError = APIStatusError

        token = os.environ.get("DATABRICKS_TOKEN")
        if not token:
            try:
                from google.cloud import secretmanager
                sm = secretmanager.SecretManagerServiceClient()
                resp = sm.access_secret_version(name=self.SECRET_NAME)
                token = resp.payload.data.decode("utf-8").strip()
                logger.debug("ClienteDatabricks: token cargado desde Secret Manager")
            except Exception as exc:
                raise ValueError(
                    "DATABRICKS_TOKEN no encontrado en variables de entorno ni en "
                    f"Secret Manager ({self.SECRET_NAME}): {exc}"
                ) from exc

        base_url = os.environ.get("DATABRICKS_BASE_URL", self.BASE_URL_DEFAULT)
        self._modelo = os.environ.get("DATABRICKS_MODEL", self.MODELO_DEFAULT)

        import socket
        import httpx
        # TCP_KEEPIDLE en Linux; TCP_KEEPALIVE en macOS
        _keepidle_opt = getattr(socket, 'TCP_KEEPIDLE', None) or getattr(socket, 'TCP_KEEPALIVE', None)
        _keepalive_opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
        if _keepidle_opt:
            _keepalive_opts += [
                (socket.IPPROTO_TCP, _keepidle_opt, 30),
                (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10),
                (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6),
            ]
        self._cliente = OpenAI(
            api_key=token,
            base_url=base_url,
            max_retries=0,
            http_client=httpx.Client(
                timeout=httpx.Timeout(120.0, connect=10.0),
                transport=httpx.HTTPTransport(socket_options=_keepalive_opts),
            ),
        )
        logger.debug(
            f"ClienteDatabricks inicializado → modelo: {self._modelo}, "
            f"base_url: {base_url}"
        )

    @property
    def errores_recuperables(self):
        return (self._RateLimitError, self._APIConnectionError)

    @property
    def error_servidor(self):
        return self._APIStatusError

    # ── Conversiones Anthropic → OpenAI ──────────────────────────────────────

    def _tools_a_openai(self, tools: list) -> list:
        """Convierte definición de tools Anthropic → OpenAI."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get(
                        "input_schema",
                        {"type": "object", "properties": {}},
                    ),
                },
            }
            for t in tools
        ]

    def _mensajes_a_openai(self, system: str, messages: list) -> list:
        """Convierte historial de mensajes Anthropic → OpenAI."""
        resultado = [{"role": "system", "content": system}]

        for msg in messages:
            rol = msg["role"]
            contenido = msg["content"]

            if rol == "user":
                if isinstance(contenido, str):
                    resultado.append({"role": "user", "content": contenido})
                elif isinstance(contenido, list):
                    # Lista: puede mezclar tool_results y texto
                    tool_results = []
                    texto_extra = []
                    for item in contenido:
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "tool_result"
                        ):
                            tool_results.append({
                                "role": "tool",
                                "tool_call_id": item["tool_use_id"],
                                "content": item["content"],
                            })
                        else:
                            texto_extra.append(str(item))
                    resultado.extend(tool_results)
                    if texto_extra:
                        resultado.append({
                            "role": "user",
                            "content": " ".join(texto_extra),
                        })

            elif rol == "assistant":
                if isinstance(contenido, list):
                    texto = ""
                    tool_calls = []
                    for bloque in contenido:
                        tipo = (
                            bloque.type
                            if hasattr(bloque, "type")
                            else bloque.get("type", "")
                        )
                        if tipo == "text":
                            texto += (
                                bloque.text
                                if hasattr(bloque, "text")
                                else bloque.get("text", "")
                            )
                        elif tipo == "tool_use":
                            nombre = (
                                bloque.name
                                if hasattr(bloque, "name")
                                else bloque.get("name", "")
                            )
                            inp = (
                                bloque.input
                                if hasattr(bloque, "input")
                                else bloque.get("input", {})
                            )
                            bid = (
                                bloque.id
                                if hasattr(bloque, "id")
                                else bloque.get("id", "")
                            )
                            tool_calls.append({
                                "id": bid,
                                "type": "function",
                                "function": {
                                    "name": nombre,
                                    "arguments": json.dumps(
                                        inp, ensure_ascii=False
                                    ),
                                },
                            })
                    msg_asistente: dict = {
                        "role": "assistant",
                        "content": texto or None,
                    }
                    if tool_calls:
                        msg_asistente["tool_calls"] = tool_calls
                    resultado.append(msg_asistente)
                else:
                    resultado.append({
                        "role": "assistant",
                        "content": str(contenido),
                    })

        return resultado

    # ── Normalización OpenAI → Anthropic ─────────────────────────────────────

    def _normalizar_respuesta(self, resp) -> RespuestaNormalizada:
        """Convierte respuesta OpenAI → RespuestaNormalizada (formato Anthropic)."""
        choice = resp.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        bloques: list = []

        if message.content:
            bloques.append(BloqueTexto(text=message.content))

        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {"_raw": tc.function.arguments}
                bloques.append(BloqueToolUse(
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                ))

        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"
        uso = _Usage(
            input_tokens=getattr(
                getattr(resp, "usage", None), "prompt_tokens", 0
            ),
            output_tokens=getattr(
                getattr(resp, "usage", None), "completion_tokens", 0
            ),
        )
        return RespuestaNormalizada(
            stop_reason=stop_reason,
            content=bloques,
            usage=uso,
        )

    TIMEOUT_SEGUNDOS = 120  # 2 minutos por llamada LLM (httpx.Client ya tiene 120s)

    def crear_mensaje(self, *, model, max_tokens, system, tools, messages):
        tools_oi = self._tools_a_openai(tools)
        messages_oi = self._mensajes_a_openai(system, messages)
        # FIX-LLM-DETER (v20.0): temperature=0.0 para determinismo.
        # seed=42 eliminado — Databricks Qwen3-80B rechaza el campo (HTTP 400).
        resp = self._cliente.chat.completions.create(
            model=self._modelo,
            max_tokens=max_tokens,
            tools=tools_oi,
            messages=messages_oi,
            timeout=self.TIMEOUT_SEGUNDOS,
            temperature=0.0,
        )
        return self._normalizar_respuesta(resp)


# ─── Cliente Gemini (Vertex AI OpenAI-compatible) ─────────────────────────────

class ClienteGemini:
    """
    Wrapper de Vertex AI Gemini vía endpoint OpenAI-compatible.
    Usa Application Default Credentials (gcloud auth / service account).
    Convierte tools Anthropic → OpenAI (mismo patrón que ClienteDatabricks).

    Variables de entorno:
        GEMINI_GCP_PROJECT  — proyecto GCP con créditos Gemini (default: project-c742757f-1731-44cd-a40)
        GEMINI_GCP_LOCATION — región Vertex AI (default: global)
        GEMINI_MODEL        — nombre del modelo (default: google/gemini-3.1-pro-preview)
    """

    GCP_PROJECT_DEFAULT = "project-c742757f-1731-44cd-a40"
    GCP_LOCATION_DEFAULT = "global"
    MODELO_DEFAULT = "google/gemini-3.1-pro-preview"

    def __init__(self):
        try:
            from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError
        except ImportError as exc:
            raise ImportError(
                "Paquete 'openai' requerido para ClienteGemini. "
                "Instalar con: pip install openai"
            ) from exc

        self._RateLimitError = RateLimitError
        self._APIConnectionError = APIConnectionError
        self._APIStatusError = APIStatusError
        self._OpenAI = OpenAI

        self._project = os.environ.get("GEMINI_GCP_PROJECT", self.GCP_PROJECT_DEFAULT)
        self._location = os.environ.get("GEMINI_GCP_LOCATION", self.GCP_LOCATION_DEFAULT)
        self._modelo = os.environ.get("GEMINI_MODEL", self.MODELO_DEFAULT)
        # global usa hostname sin prefijo regional (v1beta1)
        if self._location == "global":
            self._base_url = (
                f"https://aiplatform.googleapis.com/v1beta1/projects/"
                f"{self._project}/locations/global/endpoints/openapi"
            )
        else:
            self._base_url = (
                f"https://{self._location}-aiplatform.googleapis.com/v1/projects/"
                f"{self._project}/locations/{self._location}/endpoints/openapi"
            )

        # Cargar credenciales ADC (se refrescan en cada llamada si expiran)
        import google.auth
        import google.auth.transport.requests
        self._creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._auth_req = google.auth.transport.requests.Request()
        self._creds.refresh(self._auth_req)

        import httpx
        self._httpx = httpx
        logger.info(
            f"ClienteGemini inicializado → modelo: {self._modelo}, "
            f"project: {self._project}, location: {self._location}"
        )

    def _token_fresco(self) -> str:
        """Refresca el token ADC si está vencido y lo retorna."""
        if not self._creds.valid:
            self._creds.refresh(self._auth_req)
        return self._creds.token

    @property
    def errores_recuperables(self):
        return (self._RateLimitError, self._APIConnectionError)

    @property
    def error_servidor(self):
        return self._APIStatusError

    def _tools_a_openai(self, tools: list) -> list:
        """Convierte definición de tools Anthropic → OpenAI."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get(
                        "input_schema",
                        {"type": "object", "properties": {}},
                    ),
                },
            }
            for t in tools
        ]

    def _mensajes_a_openai(self, system: str, messages: list) -> list:
        """Convierte historial de mensajes Anthropic → OpenAI."""
        resultado = [{"role": "system", "content": system}]
        for msg in messages:
            rol = msg["role"]
            contenido = msg["content"]
            if rol == "user":
                if isinstance(contenido, str):
                    resultado.append({"role": "user", "content": contenido})
                elif isinstance(contenido, list):
                    tool_results = []
                    texto_extra = []
                    for item in contenido:
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "tool_result"
                        ):
                            tool_results.append({
                                "role": "tool",
                                "tool_call_id": item["tool_use_id"],
                                "content": item["content"],
                            })
                        else:
                            texto_extra.append(str(item))
                    resultado.extend(tool_results)
                    if texto_extra:
                        resultado.append({
                            "role": "user",
                            "content": " ".join(texto_extra),
                        })
            elif rol == "assistant":
                if isinstance(contenido, list):
                    texto = ""
                    tool_calls = []
                    for bloque in contenido:
                        tipo = (
                            bloque.type
                            if hasattr(bloque, "type")
                            else bloque.get("type", "")
                        )
                        if tipo == "text":
                            texto += (
                                bloque.text
                                if hasattr(bloque, "text")
                                else bloque.get("text", "")
                            )
                        elif tipo == "tool_use":
                            nombre = (
                                bloque.name
                                if hasattr(bloque, "name")
                                else bloque.get("name", "")
                            )
                            inp = (
                                bloque.input
                                if hasattr(bloque, "input")
                                else bloque.get("input", {})
                            )
                            bid = (
                                bloque.id
                                if hasattr(bloque, "id")
                                else bloque.get("id", "")
                            )
                            tool_calls.append({
                                "id": bid,
                                "type": "function",
                                "function": {
                                    "name": nombre,
                                    "arguments": json.dumps(inp, ensure_ascii=False),
                                },
                            })
                    msg_asistente: dict = {
                        "role": "assistant",
                        "content": texto or None,
                    }
                    if tool_calls:
                        msg_asistente["tool_calls"] = tool_calls
                    resultado.append(msg_asistente)
                else:
                    resultado.append({
                        "role": "assistant",
                        "content": str(contenido),
                    })
        return resultado

    def _normalizar_respuesta(self, resp) -> RespuestaNormalizada:
        """Convierte respuesta OpenAI → RespuestaNormalizada (formato Anthropic)."""
        choice = resp.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason
        bloques: list = []
        if message.content:
            bloques.append(BloqueTexto(text=message.content))
        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {"_raw": tc.function.arguments}
                bloques.append(BloqueToolUse(
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                ))
        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"
        uso = _Usage(
            input_tokens=getattr(
                getattr(resp, "usage", None), "prompt_tokens", 0
            ),
            output_tokens=getattr(
                getattr(resp, "usage", None), "completion_tokens", 0
            ),
        )
        return RespuestaNormalizada(stop_reason=stop_reason, content=bloques, usage=uso)

    def crear_mensaje(self, *, model, max_tokens, system, tools, messages):
        # Construir cliente con token fresco en cada llamada (expira en ~1h)
        cliente = self._OpenAI(
            api_key=self._token_fresco(),
            base_url=self._base_url,
            max_retries=0,
            http_client=self._httpx.Client(
                timeout=self._httpx.Timeout(120.0, connect=10.0)
            ),
        )
        tools_oi = self._tools_a_openai(tools)
        messages_oi = self._mensajes_a_openai(system, messages)
        # FIX-LLM-DETER (v20.0): temperature=0.0 para determinismo.
        # seed omitido — Databricks rechaza el campo; mantener consistencia entre clientes.
        kwargs_det: dict = {"temperature": 0.0}
        resp = cliente.chat.completions.create(
            model=self._modelo,
            max_tokens=max_tokens,
            tools=tools_oi,
            messages=messages_oi,
            timeout=120,
            **kwargs_det,
        )
        return self._normalizar_respuesta(resp)


# ─── Cliente Gemini Nativo (google-genai SDK) ─────────────────────────────────

class ClienteGeminiNativo:
    """
    Wrapper del SDK nativo google-genai para Vertex AI.
    Usa Application Default Credentials (ADC) — api_key ignorado con vertexai=True.
    Soporta thinking, Google Search y streaming.

    Variables de entorno:
        GEMINI_GCP_PROJECT  — proyecto GCP (default: project-c742757f-1731-44cd-a40)
        GEMINI_GCP_LOCATION — región Vertex AI (default: us-central1)
        GEMINI_MODEL        — modelo (default: gemini-3.1-pro)
    """

    GCP_PROJECT_DEFAULT = "project-c742757f-1731-44cd-a40"
    GCP_LOCATION_DEFAULT = "global"
    MODELO_DEFAULT = "gemini-3.1-pro-preview"

    def __init__(self):
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ImportError(
                "Paquete 'google-genai' requerido para ClienteGeminiNativo. "
                "Instalar con: pip install google-genai"
            ) from exc

        self._genai = genai
        self._types = genai_types

        self._project = os.environ.get("GEMINI_GCP_PROJECT", self.GCP_PROJECT_DEFAULT)
        self._location = os.environ.get("GEMINI_GCP_LOCATION", self.GCP_LOCATION_DEFAULT)
        self._modelo = os.environ.get("GEMINI_MODEL", self.MODELO_DEFAULT)

        # vertexai=True → usa ADC, api_key ignorado (bloqueado por política de org)
        self._client = genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
        )
        logger.info(
            f"ClienteGeminiNativo inicializado → modelo: {self._modelo}, "
            f"project: {self._project}, location: {self._location}"
        )

    def generar(
        self,
        prompt: str,
        *,
        system: str = "",
        temperatura: float = 1.0,
        max_tokens: int = 16384,
        thinking_level: str = "MEDIUM",
        google_search: bool = False,
        safety_off: bool = True,
    ) -> str:
        """
        Genera respuesta de texto con streaming.

        Args:
            prompt: texto de entrada
            system: instrucción de sistema
            temperatura: temperatura de muestreo
            max_tokens: tokens máximos totales (incluye tokens de thinking)
            thinking_level: "LOW" | "MEDIUM" | "HIGH" (Gemini 3.x)
                            Gemini 2.x usa thinking_budget internamente (auto-detectado)
            google_search: activar grounding con Google Search
            safety_off: desactivar filtros de seguridad (para análisis técnico)

        Returns:
            Texto generado completo (sin incluir bloques de thinking internos)
        """
        types = self._types

        tools = []
        if google_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        safety_settings = []
        if safety_off:
            for cat in [
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_HARASSMENT",
            ]:
                safety_settings.append(
                    types.SafetySetting(category=cat, threshold="OFF")
                )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ]

        # Gemini 3.x usa thinking_level; Gemini 2.x usa thinking_budget (legacy)
        es_gemini3 = self._modelo.startswith("gemini-3")
        if es_gemini3:
            thinking_cfg = types.ThinkingConfig(thinking_level=thinking_level)
        else:
            _budget_map = {"LOW": 512, "MEDIUM": 1024, "HIGH": 4096}
            thinking_cfg = types.ThinkingConfig(
                thinking_budget=_budget_map.get(thinking_level, 1024)
            )

        config_kwargs: dict = {
            "temperature": temperatura,
            "top_p": 0.95,
            "max_output_tokens": max_tokens,
            "safety_settings": safety_settings,
            "thinking_config": thinking_cfg,
        }
        if tools:
            config_kwargs["tools"] = tools
        if system:
            config_kwargs["system_instruction"] = system

        config = types.GenerateContentConfig(**config_kwargs)

        # Non-streaming: más confiable con modelos de thinking (evita cortes en streaming)
        resp = self._client.models.generate_content(
            model=self._modelo,
            contents=contents,
            config=config,
        )
        texto = ""
        if resp.candidates and resp.candidates[0].content:
            for part in resp.candidates[0].content.parts:
                if hasattr(part, "text") and part.text and not getattr(part, "thought", False):
                    texto += part.text

        return texto


# ─── Cliente Gemini 3.x Nativo — agentic loop con thought_signatures ─────────

class ClienteGemini3:
    """
    Cliente nativo google-genai para Gemini 3.x en el agentic loop.
    Preserva thought_signatures entre turnos (requisito de Gemini 3.1+).
    Compatible con la interfaz BaseSubagente.crear_mensaje().

    Variables de entorno:
        GEMINI_GCP_PROJECT  — proyecto GCP (default: project-c742757f-1731-44cd-a40)
        GEMINI_GCP_LOCATION — región Vertex AI (default: global)
        GEMINI_MODEL        — modelo (default: gemini-3.1-pro-preview)
    """

    GCP_PROJECT_DEFAULT = "project-c742757f-1731-44cd-a40"
    GCP_LOCATION_DEFAULT = "global"
    MODELO_DEFAULT = "gemini-3.1-pro-preview"

    def __init__(self):
        try:
            from google import genai
            from google.genai import types as genai_types
            from google.genai import errors as genai_errors
        except ImportError as exc:
            raise ImportError("pip install google-genai") from exc

        self._genai = genai
        self._types = genai_types
        self._errors = genai_errors

        self._project = os.environ.get("GEMINI_GCP_PROJECT", self.GCP_PROJECT_DEFAULT)
        self._location = os.environ.get("GEMINI_GCP_LOCATION", self.GCP_LOCATION_DEFAULT)
        self._modelo = os.environ.get("GEMINI_MODEL", self.MODELO_DEFAULT)

        self._client = genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
        )
        logger.info(
            f"ClienteGemini3 inicializado → modelo: {self._modelo}, "
            f"project: {self._project}, location: {self._location}"
        )

    @property
    def errores_recuperables(self):
        return (self._errors.ServerError,)

    @property
    def error_servidor(self):
        return self._errors.ClientError

    # ── Conversión de tools ───────────────────────────────────────────────────

    def _tools_a_gemini(self, tools: list) -> list:
        types = self._types

        def _schema(s: dict) -> dict:
            if not s:
                return {}
            r: dict = {}
            if "type" in s:
                r["type"] = s["type"].upper()
            if "description" in s:
                r["description"] = s["description"]
            if "properties" in s:
                r["properties"] = {k: _schema(v) for k, v in s["properties"].items()}
            if "required" in s:
                r["required"] = s["required"]
            if "items" in s:
                r["items"] = _schema(s["items"])
            if "enum" in s:
                r["enum"] = s["enum"]
            return r

        decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=_schema(
                    t.get("input_schema", {"type": "object", "properties": {}})
                ),
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=decls)]

    # ── Conversión de mensajes ────────────────────────────────────────────────

    def _mensajes_a_gemini(self, system: str, messages: list) -> list:
        types = self._types

        # Mapa tool_use_id → nombre para resolver FunctionResponse
        id_to_name: dict = {}
        for msg in messages:
            if msg["role"] == "assistant":
                for b in (msg["content"] if isinstance(msg["content"], list) else []):
                    tipo = b.type if hasattr(b, "type") else b.get("type", "")
                    if tipo == "tool_use":
                        bid = b.id if hasattr(b, "id") else b.get("id", "")
                        nombre = b.name if hasattr(b, "name") else b.get("name", "")
                        id_to_name[bid] = nombre

        contents = []
        for msg in messages:
            rol = msg["role"]
            contenido = msg["content"]

            if rol == "user":
                if isinstance(contenido, str):
                    contents.append(types.Content(
                        role="user", parts=[types.Part(text=contenido)]
                    ))
                elif isinstance(contenido, list):
                    parts = []
                    for item in contenido:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            nombre = id_to_name.get(item["tool_use_id"], item["tool_use_id"])
                            resultado = item.get("content", "")
                            if isinstance(resultado, list):
                                resultado = " ".join(
                                    b.get("text", "") if isinstance(b, dict) else str(b)
                                    for b in resultado
                                )
                            parts.append(types.Part(
                                function_response=types.FunctionResponse(
                                    name=nombre,
                                    response={"result": str(resultado)},
                                )
                            ))
                        elif isinstance(item, dict) and item.get("type") == "text":
                            parts.append(types.Part(text=item.get("text", "")))
                        elif isinstance(item, str):
                            parts.append(types.Part(text=item))
                    if parts:
                        contents.append(types.Content(role="user", parts=parts))

            elif rol == "assistant":
                if isinstance(contenido, list):
                    parts = []
                    for b in contenido:
                        tipo = b.type if hasattr(b, "type") else b.get("type", "")
                        if tipo == "thought":
                            # Preservar thought_signature para Gemini 3.x
                            sig = (
                                b.thought_signature if hasattr(b, "thought_signature")
                                else b.get("thought_signature")
                            )
                            txt = b.text if hasattr(b, "text") else b.get("text", "")
                            part_kw: dict = {"thought": True}
                            if txt:
                                part_kw["text"] = txt
                            if sig:
                                part_kw["thought_signature"] = sig
                            parts.append(types.Part(**part_kw))
                        elif tipo == "text":
                            txt = b.text if hasattr(b, "text") else b.get("text", "")
                            if txt:
                                parts.append(types.Part(text=txt))
                        elif tipo == "tool_use":
                            nombre = b.name if hasattr(b, "name") else b.get("name", "")
                            inp = b.input if hasattr(b, "input") else b.get("input", {})
                            sig = (
                                b.thought_signature if hasattr(b, "thought_signature")
                                else b.get("thought_signature")
                            )
                            part_kw: dict = {
                                "function_call": types.FunctionCall(name=nombre, args=inp)
                            }
                            if sig is not None:
                                part_kw["thought_signature"] = sig
                            parts.append(types.Part(**part_kw))
                    if parts:
                        contents.append(types.Content(role="model", parts=parts))
                elif contenido:
                    contents.append(types.Content(
                        role="model", parts=[types.Part(text=str(contenido))]
                    ))

        return contents

    # ── Normalización ─────────────────────────────────────────────────────────

    def _normalizar_respuesta(self, resp) -> RespuestaNormalizada:
        candidate = resp.candidates[0]
        parts = candidate.content.parts if candidate.content else []

        bloques: list = []
        for i, part in enumerate(parts):
            fc = getattr(part, "function_call", None)
            if fc is not None:
                # thought_signature va en el mismo Part que el function_call (Gemini 3.x)
                sig = getattr(part, "thought_signature", None)
                bloques.append(BloqueToolUse(
                    id=f"{fc.name}_{i}",
                    name=fc.name,
                    input=dict(fc.args) if fc.args else {},
                    thought_signature=sig,
                ))
            elif getattr(part, "thought", False):
                bloques.append(BloqueThought(
                    text=getattr(part, "text", "") or "",
                    thought_signature=getattr(part, "thought_signature", None),
                ))
            elif getattr(part, "text", None):
                bloques.append(BloqueTexto(text=part.text))

        stop_reason = (
            "tool_use" if any(isinstance(b, BloqueToolUse) for b in bloques)
            else "end_turn"
        )
        uso = _Usage(
            input_tokens=getattr(
                getattr(resp, "usage_metadata", None), "prompt_token_count", 0
            ),
            output_tokens=getattr(
                getattr(resp, "usage_metadata", None), "candidates_token_count", 0
            ),
        )
        return RespuestaNormalizada(stop_reason=stop_reason, content=bloques, usage=uso)

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def crear_mensaje(self, *, model, max_tokens, system, tools, messages):
        types = self._types
        gemini_tools = self._tools_a_gemini(tools) if tools else None
        contents = self._mensajes_a_gemini(system, messages)

        config_kw: dict = {
            "max_output_tokens": max_tokens,
            "temperature": 1.0,
            "thinking_config": types.ThinkingConfig(thinking_level="LOW"),
        }
        if system:
            config_kw["system_instruction"] = system
        if gemini_tools:
            config_kw["tools"] = gemini_tools

        config = types.GenerateContentConfig(**config_kw)

        resp = self._client.models.generate_content(
            model=self._modelo,
            contents=contents,
            config=config,
        )
        return self._normalizar_respuesta(resp)


# ─── Factory ──────────────────────────────────────────────────────────────────

def crear_cliente(proveedor: str = "databricks"):
    """
    Crea el cliente LLM según el proveedor.

    Args:
        proveedor: "databricks" | "anthropic" | "gemini" | "gemini_nativo" | "gemini3"

    Returns:
        ClienteDatabricks | ClienteAnthropic | ClienteGemini | ClienteGeminiNativo | ClienteGemini3
    """
    if proveedor == "anthropic":
        return ClienteAnthropic()
    if proveedor == "gemini":
        return ClienteGemini()
    if proveedor == "gemini_nativo":
        return ClienteGeminiNativo()
    if proveedor == "gemini3":
        return ClienteGemini3()
    return ClienteDatabricks()
