from langfuse import Langfuse
from langfuse.openai import openai as langfuse_openai # type: ignore
from app.config import OPENAI_API_KEY, GEMMA_BASE_URL, GEMMA_API_KEY
import os

from openai import OpenAI

# openai_client = OpenAI(
#     base_url=GEMMA_BASE_URL,
#     api_key=GEMMA_API_KEY,
# )

openai_client = langfuse_openai
openai_client.api_key = OPENAI_API_KEY


LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


langfuse = Langfuse(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    host=LANGFUSE_HOST,
)
