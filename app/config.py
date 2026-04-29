import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_WS_URL = os.getenv("OPENAI_WS_URL")
OPENAI_CHAT_MODEL = "gpt-4o"
OPENAI_TIMEOUT = 60

VLLM_API_KEY = os.getenv("VLLM_API_KEY")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")
GEMMA_CHAT_MODEL = "google/gemma-4-26B-A4B-it"
GEMMA_TIMEOUT = 15

WHISPER_WS_URL = os.getenv("WHISPER_WS_URL")
KOKORO_HTTP_URL = os.getenv("KOKORO_HTTP_URL")

DEFAULT_VOICE   = "em_santa"
DEFAULT_SPEED   = 1.35

IMAGES_FOLDER = "app/images"


LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


RETRY_WITH_OTHER_MODEL = True

DEFAULT_LANGUAGE = "spanish"