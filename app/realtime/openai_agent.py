from app.services.schemas import TOOL_SCHEMAS
from app.tools.tools import TOOLS
import json
from app.services.logger import logger


# -----------------------
# ⚙️ AGENT RUNTIME
# -----------------------

class OpenaiAgentRuntime:
    def __init__(self, openai_ws):
        self.openai_ws = openai_ws
        # Buffers de tool calls en curso: { call_id: { name, arguments } }
        self.pending_calls: dict[str, dict] = {}

    async def send_session_config(self):
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {   # ← añadir esto
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700,
                },
                "instructions": "Eres un asistente que ayuda a rellenar formularios. Usa las tools disponibles para obtener y actualizar el formulario basado en la conversación con el usuario. Responde siempre en el idioma del usuario.",
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto",
            }
        }))

    async def run_tool(self, name: str, args: dict) -> str:
        if name not in TOOLS:
            return f"Error: la tool '{name}' no existe"
        try:
            result = await TOOLS[name](**args)
            return str(result)
        except Exception as e:
            logger.error(f"Error ejecutando {name}: {e}")
            return f"Error ejecutando {name}: {e}"

    async def send_text_message(self, text: str):
        """Inyecta un mensaje de texto del usuario y solicita respuesta."""
        await self.openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}]
            }
        }))
        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    def on_function_call_started(self, call_id: str, name: str):
        """Llamado cuando OpenAI anuncia una nueva function call (output_item.added)."""
        self.pending_calls[call_id] = {"name": name, "arguments": ""}
        print(f"🛠  Tool iniciada: {name} [{call_id}]")

    def on_arguments_delta(self, call_id: str, delta: str):
        """Acumula el JSON de argumentos que llega en streaming."""
        if call_id in self.pending_calls:
            self.pending_calls[call_id]["arguments"] += delta

    async def on_arguments_done(self, call_id: str):
        """
        Llamado cuando response.function_call_arguments.done llega.
        En este punto los argumentos están completos → ejecutar la tool.
        """
        if call_id not in self.pending_calls:
            print(f"⚠️  call_id desconocido: {call_id}")
            return

        tool = self.pending_calls.pop(call_id)
        name = tool["name"]
        raw_args = tool["arguments"]

        print(f"🛠  Ejecutando: {name}({raw_args})")

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {}

        result = await self.run_tool(name, args)
        print(f"✅  Resultado: {result}")

        # 1️⃣  Añadir el resultado a la conversación
        await self.openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            }
        }))

        # 2️⃣  Pedir a OpenAI que genere la siguiente respuesta con ese resultado
        await self.openai_ws.send(json.dumps({
            "type": "response.create"
        }))