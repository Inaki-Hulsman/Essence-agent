"""
Whisper Microservice
====================
Recibe audio PCM16 por WebSocket en chunks y devuelve eventos de transcripción.

Protocolo (JSON):
  Cliente → servidor:  { "type": "audio",         "data": "<base64 PCM16>" }
                       { "type": "session.stop" }
  Servidor → cliente:  { "type": "transcript.partial", "text": "..." }
                       { "type": "transcript.final",   "text": "..." }
"""

import asyncio
import base64
import json
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from faster_whisper import WhisperModel

# -----------------------
# ⚙️ CONFIG (override con env vars en docker-compose)
# -----------------------
import os

WHISPER_MODEL_SIZE   = os.getenv("WHISPER_MODEL_SIZE",   "medium")
WHISPER_DEVICE       = os.getenv("WHISPER_DEVICE",       "cuda")   # "cpu" si no hay GPU
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16") # "int8" para CPU

SAMPLE_RATE             = 24000
BYTES_PER_SAMPLE        = 2
VAD_SILENCE_THRESHOLD_MS = int(os.getenv("VAD_SILENCE_THRESHOLD_MS",  "700"))
VAD_MIN_SPEECH_MS        = int(os.getenv("VAD_MIN_SPEECH_MS","200"))
VAD_ENERGY_THRESHOLD     = int(os.getenv("VAD_ENERGY_THRESHOLD",  "300"))

# -----------------------
# 🚀 APP
# -----------------------
app = FastAPI(title="Whisper STT Service")

print(f"🎙️  Cargando Whisper ({WHISPER_MODEL_SIZE} / {WHISPER_DEVICE})...")
model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
print("✅  Whisper listo")


# -----------------------
# 🔊 VAD helpers
# -----------------------

def rms(chunk: bytes) -> float:
    if len(chunk) < 2:
        return 0.0
    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2)))


def pcm16_to_float32(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio_bytes: bytes) -> str:
    if len(audio_bytes) < SAMPLE_RATE * BYTES_PER_SAMPLE * 0.3:
        return ""
    audio = pcm16_to_float32(audio_bytes)
    segments, _ = model.transcribe(
        audio,
        language=None,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    return " ".join(s.text.strip() for s in segments).strip()


# -----------------------
# 🌐 WebSocket endpoint
# -----------------------

@app.websocket("/ws")
async def stt_ws(ws: WebSocket):
    await ws.accept()

    audio_buffer  = b""
    silence_ms    = 0.0
    speech_ms     = 0.0
    speaking      = False
    partial_bytes = 0   # bytes acumulados desde el último partial

    async def emit(event: dict):
        await ws.send_text(json.dumps(event))

    async def do_transcribe(buf: bytes, final: bool):
        text = await asyncio.get_event_loop().run_in_executor(None, transcribe, buf)
        if text:
            evt_type = "transcript.final" if final else "transcript.partial"
            await emit({"type": evt_type, "text": text})

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "session.stop":
                # Transcribir lo que quede en buffer
                if audio_buffer:
                    await do_transcribe(audio_buffer, final=True)
                break

            if msg.get("type") != "audio":
                continue

            chunk = base64.b64decode(msg.get("data", ""))
            audio_buffer += chunk

            chunk_ms  = (len(chunk) / BYTES_PER_SAMPLE / SAMPLE_RATE) * 1000
            energy    = rms(chunk)

            if energy > VAD_ENERGY_THRESHOLD:
                speech_ms  += chunk_ms
                silence_ms  = 0

                if not speaking and speech_ms >= VAD_MIN_SPEECH_MS:
                    speaking = True
                    # ✅ Avisar inmediatamente de que hay voz
                    asyncio.create_task(emit({"type": "speech.started"}))

                # Partial cada ~1s de habla nueva
                partial_bytes += len(chunk)
                if speaking and partial_bytes >= SAMPLE_RATE * BYTES_PER_SAMPLE:
                    partial_bytes = 0
                    asyncio.create_task(do_transcribe(audio_buffer, final=False))

            else:
                if speaking:
                    silence_ms += chunk_ms
                    if silence_ms >= VAD_SILENCE_THRESHOLD_MS:
                        # Fin de turno
                        buf_to_transcribe = audio_buffer
                        audio_buffer  = b""
                        silence_ms    = 0.0
                        speech_ms     = 0.0
                        speaking      = False
                        partial_bytes = 0
                        asyncio.create_task(do_transcribe(buf_to_transcribe, final=True))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ STT WS error: {e}")
    finally:
        await ws.close()


@app.get("/health")
async def health():
    return {"status": "ok", "model": WHISPER_MODEL_SIZE}