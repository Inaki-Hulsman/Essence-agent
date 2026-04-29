
from typing import List

from langfuse import observe
from pydantic import BaseModel
from app.agents.prompts import get_chat_prompt
from app.services.utils import encode_file

# from langfuse.openai import openai as langfuse_openai # type: ignore
from app.config import OPENAI_API_KEY, VLLM_BASE_URL, GEMMA_CHAT_MODEL, OPENAI_CHAT_MODEL, RETRY_WITH_OTHER_MODEL, GEMMA_TIMEOUT, OPENAI_TIMEOUT
from openai import OpenAI

class LLM_model:
    client : OpenAI = OpenAI()
    model_name = ""
    timeout : int

    def __init__(self, url : str | None, api_key : str|None, model_name : str, timeout : int = 60):
        self.client = OpenAI(base_url=url,api_key=api_key)
        self.model_name = model_name
        self.timeout = timeout


class LLM_models:
    current_model : LLM_model
    vllm_model : LLM_model
    openai_model : LLM_model

    def __init__(self) -> None:
        self.vllm_model = LLM_model(VLLM_BASE_URL, "not-needed", GEMMA_CHAT_MODEL, GEMMA_TIMEOUT)
        self.openai_model = LLM_model(None, OPENAI_API_KEY, OPENAI_CHAT_MODEL, OPENAI_TIMEOUT)
        self.current_model = self.openai_model

    def set_vllm_model(self):
        print("cargado vllm")
        self.current_model = self.vllm_model

    def set_openai_model(self):
        print("cargado openai")
        self.current_model = self.openai_model

    def get_current_model(self):
        return self.current_model
    
llm_models = LLM_models()


# openai_client = langfuse_openai
# openai_client.api_key = OPENAI_API_KEY

# -----------------------
# 🧠 LLAMDAS BÁSICAS
# -----------------------



@observe(name="extract-info", as_type="generation")
def extract_info(user_message: list, new_form : dict, form_class: type, image = None, image_type = None) -> BaseModel:

    # Build prompt
    prompt : list = get_chat_prompt(name="Extract_section_info", role="system", form = new_form, chat = user_message)


    # print("Compiled prompt for extraction:", compiled_prompt)

    print(f"Image provided: {image is not None}, image type: {image_type}")

    if image and image_type:
        content_type = image_type
        base64_image = encode_file(image)

        prompt = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt[0]["content"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ] + prompt

    model = llm_models.get_current_model()

    for i in range(2):

        print(f"Using model: {model.model_name}")
        try:
            response = model.client.chat.completions.parse(
                model=model.model_name,
                messages=prompt,
                response_format=form_class,
                timeout=model.timeout
            )
            print(response.usage)

            parsed = response.choices[0].message.parsed # type: ignore

            if parsed is None:
                # fallback defensivo
                print("Parseo vacío")
                return form_class()

            return parsed
        
        except Exception as e:

            print(f"Error en la llamada al LLM en extract_info: {e}")

            # Si falla volver a probar con el otro modelo
            if RETRY_WITH_OTHER_MODEL:
                if model.model_name == GEMMA_CHAT_MODEL:
                    model = llm_models.openai_model
                else:
                    model = llm_models.vllm_model
            else:
                break

    return form_class()



@observe(name="correct-fields", as_type="generation")
def correct_fields(actual_fields : list, posible_fields : list , message : str) -> list:


    print("CORRECTING...")
    prompt : list =get_chat_prompt(name="correct_fields",
                            role="system",
                            actual_fields=actual_fields,
                            posible_fields=posible_fields,
                            message=message)

    model = llm_models.get_current_model()

    class Output(BaseModel):
        items: List[str]

    try:
        response = model.client.chat.completions.parse(
            model=model.model_name,
            messages=prompt,
            response_format=Output,
            timeout=model.timeout
        )
        print(response.usage)

        parsed = response.choices[0].message.parsed # type: ignore
        print(parsed)
        if parsed is None:
            # fallback defensivo
            return []

        return parsed.items
    
    except Exception as e:
        print(e)
        return [] 



