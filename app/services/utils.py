import base64
from typing import BinaryIO
import os

def encode_file(file : str | bytes) -> str:
    if isinstance(file, str):
        with open(file, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return base64.b64encode(file).decode("utf-8")

def load_image(image_path: str) -> bytes | None:
    if not (os.path.exists(image_path)):
        return None
    with open(image_path, "rb") as f:
            return f.read()