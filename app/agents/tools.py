from app.form.functions import get_form, form_manager, IMAGES_FOLDER
from app.agents.llm import correct_fields, extract_info
from app.services.utils import load_image
import json
from typing import List

from langfuse import observe

# AGENT TOOLS

FIELD_PARSING_RETRIES = 2

@observe(name="get-form", as_type="tool")
async def get_form_agent():
    print("Loading form")
    form = get_form(False)
    return json.dumps(form, ensure_ascii=False)

@observe(name="new-form", as_type="tool")
async def new_form():
    print("Creating new form")
    form = get_form(True)
    # return json.dumps(form, ensure_ascii=False)
    return "Ok"

@observe(name="extract-and-update", as_type="tool")
async def extract_and_update(message: str, selected_fields: List[str], use_loaded_image: bool = False) -> str:
    
    print("Calling extract_and_update, use_image =", use_loaded_image)
    print("Selected sections:", selected_fields)
    global form_manager

    fm = form_manager

    reduced_form = None
    for i in range(FIELD_PARSING_RETRIES):
        result, reduced_form = fm.get_very_reduced_form(selected_fields)
        if not result:
            print(f"Campos inválidos: {selected_fields}, reintentando...")
            selected_fields = correct_fields(selected_fields, fm.get_fields_path(fm.get_form()),message)

    if reduced_form is None: 
        print("No se han podido extraer campos válidos... usando todo el formulario")
        reduced_form = fm.get_clean_form(fm.get_form())


    reduced_form_class = fm.get_form_as_class(reduced_form)

    if use_loaded_image:
        image_name = fm.get_current_image().get("name", "")
        image = load_image(f"{IMAGES_FOLDER}/{image_name}")
        extraction = extract_info([message],
                                        reduced_form,
                                        reduced_form_class,
                                        image=image,
                                        image_type=fm.get_current_image()['type'] if image else None
                                        ).model_dump()
        fm.update_form(extraction)
        form_manager.add_image_reference(image_name)

    else:
        extraction = extract_info([message],reduced_form,reduced_form_class).model_dump()
        fm.update_form(extraction)

    fm.save_form_to_json()
    return json.dumps(extraction, ensure_ascii=False)


async def is_uploaded_image() -> bool:
    global form_manager
    is_image = form_manager.exists_current_image()
    print("Called is_image, result: ", is_image)
    return is_image





TOOLS = {
    "get_form" : get_form_agent,
    "new_form": new_form,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}