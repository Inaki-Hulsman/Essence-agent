import json
import asyncio
import base64
from app.form.functions import get_form
from app.services.tts_service import TTSService
from app.agents.tools import TOOLS

from typing import List, Dict, Any, AsyncGenerator

from app.agents.schemas import EXECUTOR_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT, TOOL_SCHEMAS, build_router_schema, build_tool_schema
from app.config import GEMMA_CHAT_MODEL, VLLM_BASE_URL, DEFAULT_VOICE

from openai import AsyncOpenAI


async_vllm_client = AsyncOpenAI(
    base_url=VLLM_BASE_URL,
    api_key="not-needed"
)


# ⚠️ vLLM debe estar levantado en modo OpenAI-compatible con:
# python -m vllm.entrypoints.openai.api_server \
#   --model google/gemma-3-27b-it \
#   --enable-auto-tool-choice \
#   --tool-call-parser pythonic   ← Gemma usa formato pythonic

MAX_TOOL_ITERATIONS = 4  # Evita loops infinitos


class VllmAgentRuntime:
    """
    Runtime para manejar la conversación y síntesis de audio con VLLM.
    Encapsula la lógica del pipeline LLM + TTS.
    """

    def __init__(self, client_ws, tts_service : TTSService):
        """
        Args:
            client_ws: WebSocket del cliente
            tts_service: Servicio de TTS para síntesis de audio
        """
        self.client_ws = client_ws
        self.tts_service = tts_service
        self.conversation: list = []
        self.cancel_event = asyncio.Event()
        self.voice = DEFAULT_VOICE

    def add_user_message(self, text: str):
        """Añade un mensaje del usuario a la conversación."""
        self.conversation.append({"role": "user", "content": text})

    def set_voice(self, voice : str):
        print("voz:" + voice)
        """Cambia la voz del agente"""
        self.voice = voice

    async def generate_response(self):
        """
        Genera una respuesta LLM + síntesis de audio.
        Retorna el texto completo de la respuesta.
        """
        if not self.conversation:
            return ""

        full_response = ""

        async def llm_gen():
            """Generador que obtiene chunks del LLM."""
            nonlocal full_response
            async for chunk in stream_llm_response(self.conversation, TOOLS):
                # Parar si llega interrupción
                if self.cancel_event.is_set():
                    return

                full_response += chunk

                # Enviar delta de texto al cliente
                await self.client_ws.send_text(json.dumps({
                    "type": "response.text.delta",
                    "text": chunk
                }))
                yield chunk

        # Síntesis de audio con check de cancelación en cada chunk
        try:
            async for pcm_chunk in self.tts_service.synthesize_stream(llm_gen(), voice= self.voice):
                if self.cancel_event.is_set():
                    break

                # Enviar delta de audio al cliente
                await self.client_ws.send_text(json.dumps({
                    "type": "response.audio.delta",
                    "data": base64.b64encode(pcm_chunk).decode()
                }))

            if not self.cancel_event.is_set():
                # Solo notificar "done" si no fue interrumpido
                await self.client_ws.send_text(json.dumps({
                    "type": "response.text.done",
                    "text": full_response
                }))
                await self.client_ws.send_text(json.dumps({
                    "type": "response.audio.done"
                }))

                # Añadir la respuesta a la conversación
                self.conversation.append({"role": "assistant", "content": full_response})
            else:
                # Truncar el historial — no añadir respuesta incompleta
                print("⚡ Respuesta interrumpida, descartando")

        except Exception as e:
            print(f"❌ Error en generate_response: {e}")
            return "Lo siento, ha habido un error procesando la solicitud. Disculpe las molestias."

        return full_response

    def interrupt(self):
        """Señaliza la interrupción del pipeline actual."""
        self.cancel_event.set()

    def reset_interrupt(self):
        """Reinicia la señal de interrupción para la siguiente respuesta."""
        self.cancel_event.clear()

    def clear_conversation(self):
        """Limpia el historial de conversación."""
        self.conversation = []


# -----------------------
# 🧠 GENERACIÓN
# -----------------------

async def generate_text_stream(messages: list) -> AsyncGenerator[str, None]:
    """Streaming normal de texto."""
    stream = await async_vllm_client.chat.completions.create(
        model=GEMMA_CHAT_MODEL,
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

    response = await async_vllm_client.chat.completions.create(
        model=GEMMA_CHAT_MODEL,
        messages=router_messages,
        temperature=0,
        max_tokens=100,  # La decisión es corta
        response_format=schema,  # type: ignore
    )
    
    print(response.usage)

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

    response = await async_vllm_client.chat.completions.create(
        model=GEMMA_CHAT_MODEL,
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

def get_form_state():
    form = get_form()
    return json.dumps(form, ensure_ascii=False)


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

    messages = [{"role": "system", "content": SYSTEM_PROMPT + get_form_state()}] + conversation
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
            "role": "system",
            "content": format_tool_result(tool_name, result)
        })

        # También actualizar conversation para persistencia externa
        conversation.append({
            "role": "assistant",
            "content": json.dumps({"tool": tool_name, "arguments": args}, ensure_ascii=False)
        })
        conversation.append({
            "role": "system",
            "content": format_tool_result(tool_name, result)
        })

        # 🔁 Continúa el loop → el modelo decide si necesita otra tool o responder

    # Seguridad: si se agotaron las iteraciones, responder con lo que hay
    async for chunk in generate_text_stream(messages):
        yield chunk