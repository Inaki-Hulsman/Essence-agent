from langfuse import observe
from pydantic import BaseModel
from app.config import CHAT_MODEL
from app.services.observability import openai_client as client
from app.services.observability import langfuse
from app.services.utils import encode_file


@observe(name="llm-call", as_type="span")
def call_llm(state: dict, recent_messages: list, changes: list = []) -> str:

    prompt = langfuse.get_prompt("Essence-main-chat")

    compiled_prompt = prompt.compile(
        #language=language,
        form=state,
        changes=changes,
        chat=recent_messages
    )

    # content ="Hola!"
    # compiled_prompt = [{"role": "user", "content": content}]

    # print("Compiled prompt for LLM call:", compiled_prompt)
   
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages= compiled_prompt ,# type: ignore
    )

    content = response.choices[0].message.content

    if content is None: return "I couldn't generate a response based on your query."
    return content


@observe(name="extract-section-info", as_type="span")
def extract_section_info(user_message: list, new_form : dict, form_class: type, image = None, image_type = None) -> BaseModel:

    print(f"Extracting info for section with message: {user_message} and form: {new_form}")
    # Build prompt
    prompt = langfuse.get_prompt("Extract_section_info")

    compiled_prompt : list= prompt.compile(
        form=new_form,
        chat=user_message
    ) # type: ignore

    print("Compiled prompt for extraction:", compiled_prompt)

    print(f"Image provided: {image is not None}, image type: {image_type}")

    if image and image_type:
        content_type = image_type
        base64_image = encode_file(image)

        compiled_prompt = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": compiled_prompt[0]["content"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ] + compiled_prompt
       
    response = client.chat.completions.parse(
        model=CHAT_MODEL,
        messages=compiled_prompt, # type: ignore
        response_format=form_class
    )

    parsed = response.choices[0].message.parsed

    if parsed is None:
        # fallback defensivo
        return form_class()

    return parsed


# def analyze_image(content_path : str = "C:\\Users\\inaki.hulsman\\Downloads\\scroll.jpg"):


#     content_type = "image/jpeg"
#     base64_image = encode_file(content_path)
#     response = client.chat.completions.create(
#         model=VISION_MODEL,
#         messages=[
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": "What’s in this image?"},
#                     {
#                         "type": "image_url",
#                         "image_url": {
#                             "url": f"data:{content_type};base64,{base64_image}"
#                         },
#                     },
#                 ],
#             }
#         ],
#         max_tokens=300,
#     )
#     return response.choices[0].message.content