import json
import asyncio
import base64
from app.realtime.llm import stream_llm_response
from app.tools.tools import TOOLS


class VllmAgentRuntime:
    """
    Runtime para manejar la conversación y síntesis de audio con VLLM.
    Encapsula la lógica del pipeline LLM + TTS.
    """

    def __init__(self, client_ws, tts_service):
        """
        Args:
            client_ws: WebSocket del cliente
            tts_service: Servicio de TTS para síntesis de audio
        """
        self.client_ws = client_ws
        self.tts_service = tts_service
        self.conversation: list = []
        self.cancel_event = asyncio.Event()

    def add_user_message(self, text: str):
        """Añade un mensaje del usuario a la conversación."""
        self.conversation.append({"role": "user", "content": text})

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
            async for pcm_chunk in self.tts_service.synthesize_stream(llm_gen()):
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
