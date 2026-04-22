import numpy as np
from faster_whisper import WhisperModel
from typing import Optional, AsyncGenerator

# -----------------------
# ⚙️ MODEL
# -----------------------

model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16"
)


# -----------------------
# 🎤 STREAM STATE
# -----------------------

class StreamingASR:
    """
    Simula whisper-streaming real:
    - mantiene buffer continuo
    - transcribe parcialmente cada N ms
    - evita reset total entre chunks
    """

    def __init__(self):
        self.audio_buffer = np.array([], dtype=np.float32)
        self.sample_rate = 16000

        # control de estabilidad
        self.chunk_size = 16000 * 2  # 2s
        self.overlap = 16000 * 0.5    # 500ms overlap

    def add_audio(self, audio: np.ndarray):
        self.audio_buffer = np.concatenate([self.audio_buffer, audio])

    def trim_buffer(self):
        if len(self.audio_buffer) > self.chunk_size * 4:
            # evita crecimiento infinito
            self.audio_buffer = self.audio_buffer[-self.chunk_size * 2:]


# -----------------------
# 🧠 TRANSCRIBER STREAM
# -----------------------

async def stream_transcribe(audio_stream: AsyncGenerator[np.ndarray, None]):
    """
    Generador tipo streaming real:
    devuelve texto incremental conforme llega audio
    """

    state = StreamingASR()
    last_text = ""

    async for audio_chunk in audio_stream:

        state.add_audio(audio_chunk)
        state.trim_buffer()

        if len(state.audio_buffer) < state.chunk_size:
            continue

        # -----------------------
        # 🔥 INFERENCIA INCREMENTAL
        # -----------------------

        segments, _ = model.transcribe(
            state.audio_buffer,
            language="es",
            beam_size=3,
            vad_filter=True
        )

        full_text = "".join([s.text for s in segments]).strip()

        # -----------------------
        # 🧠 DELTA DETECTION
        # -----------------------

        if full_text and full_text != last_text:

            # extraemos solo delta nuevo
            delta = full_text.replace(last_text, "").strip()

            if delta:
                yield delta

            last_text = full_text