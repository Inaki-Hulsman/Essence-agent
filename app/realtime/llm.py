import json
from typing import List, Dict, Any, AsyncGenerator
from app.config import GEMMA_CHAT_MODEL
from openai import AsyncOpenAI
from app.services.schemas import EXECUTOR_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT, TOOL_SCHEMAS, build_router_schema, build_tool_schema

from langfuse import observe
from pydantic import BaseModel
from app.config import CHAT_MODEL
from app.services.observability import openai_client, async_client, langfuse
from app.services.utils import encode_file

# ⚠️ vLLM debe estar levantado en modo OpenAI-compatible con:
# python -m vllm.entrypoints.openai.api_server \
#   --model google/gemma-3-27b-it \
#   --enable-auto-tool-choice \
#   --tool-call-parser pythonic   ← Gemma usa formato pythonic

MODEL_NAME = GEMMA_CHAT_MODEL
MAX_TOOL_ITERATIONS = 5  # Evita loops infinitos


# -----------------------
# 🧠 LLAMDAS BÁSICAS
# -----------------------
@observe(name="llm-call", as_type="span")
def call_llm(state: dict, recent_messages: list, changes: list = []) -> str:

    prompt = langfuse.get_prompt("Essence-main-chat")

    compiled_prompt = prompt.compile(
        form=state,
        changes=changes,
        chat=recent_messages
    )
   
    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages= compiled_prompt ,# type: ignore
    )

    content = response.choices[0].message.content # type: ignore

    if content is None: return "I couldn't generate a response based on your query."
    return content


@observe(name="extract-section-info", as_type="span")
def extract_section_info(user_message: list, new_form : dict, form_class: type, image = None, image_type = None) -> BaseModel:

    # print(f"Extracting info for section with message: {user_message} and form: {new_form}")
    # Build prompt
    prompt = langfuse.get_prompt("Extract_section_info")

    compiled_prompt : list= prompt.compile(
        form=new_form,
        chat=user_message
    ) # type: ignore

    # print("Compiled prompt for extraction:", compiled_prompt)

    print(f"Image provided: {image is not None}, image type: {image_type}")

    if image and image_type:
        content_type = image_type
        base64_image = encode_file(image)

        compiled_prompt = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": compiled_prompt[0]["content"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ] + compiled_prompt
       
    response = openai_client.chat.completions.parse(
        model=CHAT_MODEL,
        messages=compiled_prompt, # type: ignore
        response_format=form_class
    )

    parsed = response.choices[0].message.parsed # type: ignore

    if parsed is None:
        # fallback defensivo
        return form_class()

    return parsed



# -----------------------
# 🧠 GENERACIÓN
# -----------------------

async def generate_text_stream(messages: list) -> AsyncGenerator[str, None]:
    """Streaming normal de texto."""
    stream = await async_client.chat.completions.create(
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

    response = await async_client.chat.completions.create(
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

    response = await async_client.chat.completions.create(
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