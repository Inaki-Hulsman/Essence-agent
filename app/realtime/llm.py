import json
from typing import List, Dict, Any, AsyncGenerator
from app.config import VLLM_BASE_URL, GEMMA_CHAT_MODEL

from openai import AsyncOpenAI

# ⚠️ vLLM debe estar levantado en modo OpenAI-compatible con:
# python -m vllm.entrypoints.openai.api_server \
#   --model google/gemma-3-27b-it \
#   --enable-auto-tool-choice \
#   --tool-call-parser pythonic   ← Gemma usa formato pythonic

MODEL_NAME = GEMMA_CHAT_MODEL
MAX_TOOL_ITERATIONS = 5  # Evita loops infinitos

client = AsyncOpenAI(
    base_url=VLLM_BASE_URL,
    api_key="not-needed"
)


# -----------------------
# 🧰 TOOL SCHEMA BUILDER
# -----------------------

def build_router_schema(tool_names: list[str]) -> Dict[str, Any]:
    """
    Schema mínimo para la decisión binaria: ¿necesito tool o no?
    Separar el router del executor reduce alucinaciones en Gemma.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "routing_decision",
            "schema": {
                "type": "object",
                "properties": {
                    "needs_tool": {"type": "boolean"},
                    "tool_name": {
                        "type": "string",
                        "enum": tool_names + ["none"]
                    },
                    "reason": {"type": "string"}
                },
                "required": ["needs_tool", "tool_name"],
                "additionalProperties": False
            }
        }
    }


def build_tool_schema(tool_name: str, tools: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schema específico por tool — mucho más preciso que un schema genérico.
    Gemma sigue mejor instrucciones cuando el schema es concreto.
    """
    # Buscar el schema de parámetros en TOOL_SCHEMAS
    tool_def = next((t for t in TOOL_SCHEMAS if t["name"] == tool_name), None)
    if not tool_def:
        # Fallback genérico
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "tool_call",
                "schema": {
                    "type": "object",
                    "properties": {
                        "arguments": {"type": "object", "additionalProperties": True}
                    },
                    "required": ["arguments"],
                    "additionalProperties": False
                }
            }
        }

    params_schema = tool_def.get("parameters", {"type": "object", "properties": {}})

    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{tool_name}_call",
            "schema": params_schema
        }
    }


# -----------------------
# 📋 SYSTEM PROMPTS
# -----------------------

SYSTEM_PROMPT = """Eres un asistente DE VOZ que ayuda a rellenar formularios.

Tienes acceso a las siguientes herramientas:
- get_form: Obtiene el formulario actual o uno nuevo vacío
- extract_and_update: Extrae información del usuario y actualiza secciones del formulario
- is_uploaded_image: Verifica si hay una imagen subida

Cuando el usuario proporcione información o pida algo relacionado con el formulario, usa las herramientas apropiadas.
Cuando solo sea una conversación general o pregunta, responde directamente sin herramientas. En este caso, responde de forma clara y concisa, y no uses el caracter *.
Manten la conversación centrada en ayudar al usuario a completar el formulario, preguntándole por secciones aún sin completar"""


ROUTER_PROMPT = """Analiza el mensaje y el contexto. Decide si necesitas una herramienta.

Herramientas disponibles: {tool_names}

Responde con JSON indicando si necesitas tool y cuál. Si no necesitas ninguna, tool_name = "none"."""

EXECUTOR_PROMPT = """Basándote en el mensaje del usuario y el historial, genera los argumentos exactos para llamar a: {tool_name}

Descripción: {tool_description}
Parámetros requeridos: {required_params}

Genera SOLO los argumentos en JSON, sin texto adicional."""


# -----------------------
# 📚 TOOL DEFINITIONS
# -----------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_form",
        "description": "Obtiene el formulario actual o uno nuevo vacío",
        "parameters": {
            "type": "object",
            "properties": {
                "new": {
                    "type": "boolean",
                    "description": "Si es True, devuelve un formulario vacío"
                }
            },
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "extract_and_update",
        "description": "Extrae información del mensaje del usuario para secciones seleccionadas y actualiza el formulario",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensaje del usuario con la información a extraer"
                },
                "selected_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rutas completas de secciones del formulario, ej: ['produccion.vision_estrategica.posicionamiento']"
                },
                "use_loaded_image": {
                    "type": "boolean",
                    "description": "True si hay imagen del usuario relevante para estos campos"
                }
            },
            "required": ["message", "selected_sections"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "is_uploaded_image",
        "description": "Verifica si hay una imagen subida por el usuario",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]


# -----------------------
# 🧠 GENERACIÓN
# -----------------------

async def generate_text_stream(messages: list) -> AsyncGenerator[str, None]:
    """Streaming normal de texto."""
    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,
        temperature=0.3,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


async def route_decision(messages: list, tool_names: list[str]) -> Dict[str, Any]:
    """
    Paso 1: Decidir SI usar tool y CUÁL.
    Schema pequeño y binario → mucho más fiable en Gemma.
    """
    schema = build_router_schema(tool_names)
    router_messages = messages + [{
        "role": "user",
        "content": ROUTER_PROMPT.format(tool_names=", ".join(tool_names))
    }]

    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=router_messages,
        temperature=0,
        max_tokens=100,  # La decisión es corta
        response_format=schema,  # type: ignore
    )

    content = response.choices[0].message.content
    if not content:
        return {"needs_tool": False, "tool_name": "none"}

    try:
        return json.loads(content)
    except Exception:
        return {"needs_tool": False, "tool_name": "none"}


async def execute_tool_call(
    messages: list,
    tool_name: str,
    tools: Dict[str, Any]
) -> Dict[str, Any] | None:
    """
    Paso 2: Generar argumentos para la tool elegida.
    Schema específico por tool → argumentos más precisos.
    """
    tool_def = next((t for t in TOOL_SCHEMAS if t["name"] == tool_name), None)
    if not tool_def:
        return None

    schema = build_tool_schema(tool_name, tools)
    required = tool_def["parameters"].get("required", [])

    executor_messages = messages + [{
        "role": "user",
        "content": EXECUTOR_PROMPT.format(
            tool_name=tool_name,
            tool_description=tool_def["description"],
            required_params=required if required else "ninguno"
        )
    }]

    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=executor_messages,
        temperature=0,
        max_tokens=500,
        response_format=schema,  # type: ignore
    )

    content = response.choices[0].message.content
    if not content:
        return None

    try:
        return json.loads(content)
    except Exception:
        return None


def format_tool_result(tool_name: str, result: Any) -> str:
    """Formatea el resultado de una tool para el historial del modelo."""
    return f"[Resultado de {tool_name}]:\n{result}"


# -----------------------
# 🧠 PIPELINE PRINCIPAL
# -----------------------

async def stream_llm_response(
    conversation: List[Dict[str, Any]],
    tools: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Pipeline de agente con tool-calling desacoplado en dos pasos:
    1. Router: decide si usar tool y cuál (schema pequeño, rápido)
    2. Executor: genera argumentos para la tool (schema específico, preciso)
    3. Loop: permite encadenar múltiples tool calls antes de responder
    """

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation
    tool_names = list(tools.keys())

    for iteration in range(MAX_TOOL_ITERATIONS):

        # ─── Paso 1: ¿Necesito tool? ──────────────────────────────────────────

        decision = await route_decision(messages, tool_names)

        if not decision.get("needs_tool") or decision.get("tool_name") == "none":
            # ─── Respuesta final en texto ──────────────────────────────────────
            full_response = ""

            async for chunk in generate_text_stream(messages):
                full_response += chunk
                yield chunk

            conversation.append({
                "role": "assistant",
                "content": full_response
            })
            return

        # ─── Paso 2: Generar argumentos ───────────────────────────────────────

        tool_name = decision["tool_name"]

        if tool_name not in tools:
            yield f"[Error]: Tool '{tool_name}' no está disponible."
            return

        args = await execute_tool_call(messages, tool_name, tools)
        if args is None:
            # Fallback a texto si no pudo generar argumentos
            async for chunk in generate_text_stream(messages):
                yield chunk
            return

        # ─── Paso 3: Ejecutar tool ────────────────────────────────────────────

        try:
            result = await tools[tool_name](**args)
        except TypeError as e:
            result = f"Argumentos inválidos para {tool_name}: {e}"
        except Exception as e:
            result = f"Error ejecutando {tool_name}: {e}"

        # ─── Actualizar historial ─────────────────────────────────────────────
        # Usar role "assistant" + "user" en lugar de "tool" para máxima
        # compatibilidad con vLLM sin tool-call-parser configurado

        messages.append({
            "role": "assistant",
            "content": json.dumps({
                "action": "tool_call",
                "tool": tool_name,
                "arguments": args
            }, ensure_ascii=False)
        })

        messages.append({
            "role": "user",
            "content": format_tool_result(tool_name, result)
        })

        # También actualizar conversation para persistencia externa
        conversation.append({
            "role": "assistant",
            "content": json.dumps({"tool": tool_name, "arguments": args}, ensure_ascii=False)
        })
        conversation.append({
            "role": "user",
            "content": format_tool_result(tool_name, result)
        })

        # 🔁 Continúa el loop → el modelo decide si necesita otra tool o responder

    # Seguridad: si se agotaron las iteraciones, responder con lo que hay
    async for chunk in generate_text_stream(messages):
        yield chunk