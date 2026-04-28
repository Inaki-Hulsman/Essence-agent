"""
STT Service — cliente del microservicio Whisper remoto.
Misma API pública que antes: push_audio() + events() + start/stop/clear.
"""

import asyncio
import base64
import json
from typing import AsyncGenerator

from app.config import WHISPER_WS_URL

import websockets

# -----------------------
# 🎙️ STT SERVICE (cliente remoto)
# -----------------------

class STTService:
    """
    Thin client que:
    - Recibe chunks PCM16 localmente (push_audio)
    - Los reenvía por WebSocket al microservicio Whisper
    - Emite los eventos de transcripción que devuelve el servicio
    """

    def __init__(self):
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._running = False
        self._ws_task: asyncio.Task | None = None

    # -----------------------
    # 🔌 API PÚBLICA (sin cambios para el caller)
    # -----------------------

    def push_audio(self, pcm16_bytes: bytes):
        """Encola un chunk de audio para enviarlo al servicio remoto."""
        self._audio_queue.put_nowait(pcm16_bytes)

    async def events(self) -> AsyncGenerator[dict, None]:
        """Generador de eventos {type, text} que llegan del servicio."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue

    def start(self):
        self._running = True
        # Lanzar la tarea de conexión WS en background
        self._ws_task = asyncio.create_task(self._ws_loop())

    def stop(self):
        self._running = False
        self._audio_queue.put_nowait(None)  # señal de cierre

    def clear(self):
        """Vaciar cola de audio pendiente (p.ej. al interrumpir)."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    # -----------------------
    # 🔧 INTERNO: loop WS
    # -----------------------

    async def _ws_loop(self):
        """
        Mantiene la conexión con el microservicio Whisper.
        Reconecta automáticamente si se cae.
        """
        while self._running:
            try:
                async with websockets.connect(WHISPER_WS_URL) as ws: # type: ignore
                    print(f"🎙️  STT conectado a {WHISPER_WS_URL}")
                    await asyncio.gather(
                        self._send_loop(ws),
                        self._recv_loop(ws),
                    )
            except Exception as e:
                if self._running:
                    print(f"⚠️  STT reconectando en 2s ({e})")
                    await asyncio.sleep(2)

    async def _send_loop(self, ws):
        """Lee audio de la cola y lo envía al servidor en base64."""
        while self._running:
            chunk = await self._audio_queue.get()
            if chunk is None:
                # Señal de cierre — avisar al servidor
                await ws.send(json.dumps({"type": "session.stop"}))
                break
            msg = json.dumps({
                "type": "audio",
                "data": base64.b64encode(chunk).decode()
            })
            await ws.send(msg)

    async def _recv_loop(self, ws):
        """Recibe eventos del servidor y los pone en la cola de eventos."""
        async for raw in ws:
            try:
                event = json.loads(raw)
                await self._queue.put(event)
            except Exception:
                pass