"""
TTS Service — cliente del microservicio Kokoro remoto.
Misma API pública que antes: synthesize_stream() + synthesize_full().
"""

import asyncio
from typing import AsyncGenerator
from app.config import KOKORO_HTTP_URL, DEFAULT_VOICE, DEFAULT_SPEED

import httpx

# Tamaño mínimo de chunk PCM16 para reenviar al cliente (~50ms a 24kHz)
MIN_CHUNK_BYTES = 24000 * 2 * 50 // 1000   # 2400 bytes


# -----------------------
# 🔊 TTS SERVICE (cliente remoto)
# -----------------------

class TTSService:
    """
    Thin client que:
    - Recibe un generador de texto del LLM
    - Acumula texto hasta tener frases completas
    - Hace POST /synthesize al microservicio Kokoro con cada frase
    - Devuelve chunks PCM16 en streaming conforme llegan
    """

    def __init__(self):
        # Cliente HTTP reutilizable con timeout generoso para síntesis larga
        self._client = httpx.AsyncClient(
            base_url=KOKORO_HTTP_URL, # type: ignore
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
        )

    # -----------------------
    # 🔌 API PÚBLICA (sin cambios para el caller)
    # -----------------------

    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
    ) -> AsyncGenerator[bytes, None]:
        """
        Recibe chunks de texto del LLM y emite PCM16 en cuanto hay frases.
        La latencia es ≈ tiempo de síntesis de la primera frase.
        """
        import re
        buffer = ""

        async for chunk in text_stream:
            buffer += chunk
            sentences, buffer = self._split_sentences(buffer)

            for sentence in sentences:
                if sentence.strip():
                    async for pcm in self._synthesize_sentence(sentence, voice, speed):
                        yield pcm

        # Resto del buffer
        if buffer.strip():
            async for pcm in self._synthesize_sentence(buffer.strip(), voice, speed):
                yield pcm

    async def synthesize_full(self, text: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED) -> bytes:
        """Síntesis completa, devuelve todos los bytes PCM16."""
        result = b""
        async for chunk in self._synthesize_sentence(text, voice, speed):
            result += chunk
        return result

    # -----------------------
    # 🔧 INTERNO
    # -----------------------

    async def _synthesize_sentence(
        self,
        text: str,
        voice: str,
        speed: float,
    ) -> AsyncGenerator[bytes, None]:
        """POST al microservicio y devuelve chunks PCM16 en streaming."""
        try:
            async with self._client.stream(
                "POST",
                "/synthesize",
                json={"text": text, "voice": voice, "speed": speed},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=MIN_CHUNK_BYTES):
                    if chunk:
                        yield chunk
        except httpx.ConnectError:
            print(f"❌ TTS: no se puede conectar a {KOKORO_HTTP_URL}")
        except Exception as e:
            print(f"⚠️  TTS error síntesis '{text[:40]}': {e}")

    @staticmethod
    def _split_sentences(text: str) -> tuple[list[str], str]:
        import re
        parts = re.split(r'(?<=[.!?…])\s+|(?<=\n)', text)
        if len(parts) <= 1:
            return [], text
        return parts[:-1], parts[-1]

    async def close(self):
        await self._client.aclose()