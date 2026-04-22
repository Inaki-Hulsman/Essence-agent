import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_WS_URL = os.getenv("OPENAI_WS_URL")
CHAT_MODEL = "gpt-4o"

VLLM_API_KEY = os.getenv("VLLM_API_KEY")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")
GEMMA_CHAT_MODEL = "google/gemma-4-26B-A4B-it"

WHISPER_WS_URL = os.getenv("WHISPER_WS_URL")
KOKORO_HTTP_URL = os.getenv("KOKORO_HTTP_URL")

DEFAULT_VOICE   = "ef_dora"
DEFAULT_SPEED   = 1.35

IMAGES_FOLDER = "app/images"