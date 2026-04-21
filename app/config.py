import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_WS_URL = os.getenv("OPENAI_WS_URL")
CHAT_MODEL = "gpt-4o"

GEMMA_API_KEY = os.getenv("GEMMA_API_KEY")
GEMMA_BASE_URL = os.getenv("GEMMA_BASE_URL")
# CHAT_MODEL = "google/gemma-4-26B-A4B-it"

IMAGES_FOLDER = "app/images"