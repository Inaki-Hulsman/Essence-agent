import numpy as np
from faster_whisper import WhisperModel
from typing import Optional

# -----------------------
# ⚙️ MODEL INIT
# -----------------------

# Ajusta según tu GPU:
# - "small" → buena latencia
# - "medium" → equilibrio
# - "large-v3" → máxima calidad (más lento)

model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16"
)


# -----------------------
# 🎤 AUDIO BUFFER STATE
# -----------------------

class AudioBuffer:
    def __init__(self):
        self.buffer = []

    def add_chunk(self, chunk: bytes):
        self.buffer.append(chunk)

    def reset(self):
        self.buffer = []

    def get_audio(self) -> np.ndarray:
        """
        Convierte bytes PCM16 → numpy array float32
        """
        audio_bytes = b"".join(self.buffer)

        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0  # normalización

        return audio


# -----------------------
# 🎤 TRANSCRIPCIÓN
# -----------------------

async def transcribe_audio(audio: np.ndarray) -> Optional[str]:
    """
    Transcribe un chunk de audio.
    faster-whisper es síncrono → lo corremos en thread
    """

    if len(audio) < 16000:  # ~1s mínimo
        return None

    segments, info = model.transcribe(
        audio,
        language="es",  # ajusta si quieres auto-detect
        beam_size=5
    )

    text = ""

    for segment in segments:
        text += segment.text

    return text.strip() if text.strip() else None


# -----------------------
# 🔁 STREAMING SIMULADO
# -----------------------

audio_buffer = AudioBuffer()


async def transcribe_audio_chunk(audio_chunk: bytes) -> Optional[str]:
    """
    Función que usarás desde WebSocket.

    Acumula audio y transcribe cuando hay suficiente contexto.
    """

    audio_buffer.add_chunk(audio_chunk)

    audio = audio_buffer.get_audio()

    # threshold simple (puedes reemplazar por VAD después)
    if len(audio) < 24000:  # ~1.5s
        return None

    text = await transcribe_audio(audio)

    if text:
        audio_buffer.reset()

    return text