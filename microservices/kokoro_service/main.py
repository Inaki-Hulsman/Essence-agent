"""
Kokoro TTS Microservice
=======================
Recibe texto y devuelve audio PCM16 en streaming HTTP (chunked transfer).

Endpoints:
  POST /synthesize          body: { "text": "...", "voice": "ef_dora", "speed": 1.0 }
  GET  /synthesize?text=... query param (cómodo para tests)
  GET  /health

La respuesta es un stream de bytes PCM16 raw a 24kHz mono.
El cliente acumula los chunks y los reproduce conforme llegan.
"""

import asyncio
import os
import re
import numpy as np
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from kokoro_onnx import Kokoro

# -----------------------
# ⚙️ CONFIG
# -----------------------

KOKORO_MODEL_PATH = os.getenv("KOKORO_MODEL_PATH", "/models/kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.getenv("KOKORO_VOICES_PATH", "/models/voices-v1.0.bin")
DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "ef_dora")
DEFAULT_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
DEFAULT_LANG  = os.getenv("KOKORO_LANG",  "es")
OUTPUT_SAMPLE_RATE = 24000

# -----------------------
# 🚀 APP
# -----------------------

app = FastAPI(title="Kokoro TTS Service")

print("🔊  Cargando Kokoro TTS...")
kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
print("✅  Kokoro listo")


# -----------------------
# 🔧 Helpers
# -----------------------

def split_sentences(text: str) -> list[str]:
    """Divide en frases por puntuación para empezar a emitir audio antes."""
    parts = re.split(r'(?<=[.!?…])\s+|(?<=\n)', text)
    return [p.strip() for p in parts if p.strip()]


def to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


def resample(samples: np.ndarray, orig: int, target: int) -> np.ndarray:
    if orig == target:
        return samples
    n = int(len(samples) * target / orig)
    return np.interp(
        np.linspace(0, len(samples) - 1, n),
        np.arange(len(samples)),
        samples
    ).astype(np.float32)


def synthesize_sentence(text: str, voice: str, speed: float) -> bytes | None:
    try:
        samples, sr = kokoro.create(text, voice=voice, speed=speed, lang=DEFAULT_LANG)
        samples = resample(samples, sr, OUTPUT_SAMPLE_RATE)
        return to_pcm16(samples)
    except Exception as e:
        print(f"⚠️  TTS error '{text[:40]}': {e}")
        return None


# -----------------------
# 📋 Schema
# -----------------------

class SynthesizeRequest(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE
    speed: float = DEFAULT_SPEED


# -----------------------
# 🌐 Endpoints
# -----------------------

@app.post("/synthesize")
async def synthesize_stream(req: SynthesizeRequest):
    """
    Streaming PCM16 raw.
    Las frases se sintetizan y emiten en orden — latencia ≈ primera frase.
    """
    sentences = split_sentences(req.text)

    async def generate():
        for sentence in sentences:
            pcm = await asyncio.get_event_loop().run_in_executor(
                None, synthesize_sentence, sentence, req.voice, req.speed
            )
            if pcm:
                yield pcm

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={"X-Sample-Rate": str(OUTPUT_SAMPLE_RATE)},
    )


@app.get("/synthesize")
async def synthesize_get(text: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED):
    """Alias GET para tests rápidos desde el navegador."""
    return await synthesize_stream(SynthesizeRequest(text=text, voice=voice, speed=speed))


@app.get("/health")
async def health():
    return {"status": "ok", "voice": DEFAULT_VOICE, "sample_rate": OUTPUT_SAMPLE_RATE}