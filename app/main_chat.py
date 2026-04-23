
from app.services.form_manager import FormManager
from app.services.logger import logger
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, Form
from app.realtime.llm import call_llm, extract_section_info
from app.config import IMAGES_FOLDER
from app.services.utils import encode_file
import os

app = FastAPI()

form_manager = FormManager()


@app.get("/get_form")
async def get_form(new: bool = False):
    if new:
        form = form_manager.load_empty_form()
    else:
        form = form_manager.get_form()
    images_refs = form_manager.get_all_image_references()
    images = {}
    
    for img_ref in images_refs:
        try:
            img_path = f"{IMAGES_FOLDER}/{img_ref}" if not img_ref.startswith(IMAGES_FOLDER) else img_ref
            images[img_ref] = encode_file(img_path)
        except Exception as e:
            logger.error(f"Error reading image {img_ref}: {e}")
    
    return {
        "form": form,
        "images": images
    }

@app.post("/chat")
async def chat(
    user_id: str = Form(...),
    message: str = Form(...),
    selected_sections: List[str] = Form(...), # JSON string with list of selected sections
    image: UploadFile = None # type: ignore
):
    logger.info(f"Selected sections: {selected_sections}")
    recent_messages = [message]


    # Extraer info de secciones seleccionadas
    reduced_form = form_manager.get_reduced_form(selected_sections)
    logger.info(f"Formulario reducido para secciones seleccionadas: {reduced_form}")
    
    reduced_form_class = form_manager.get_form_as_class(reduced_form)
    extraction = extract_section_info(recent_messages,
                                      reduced_form,
                                      reduced_form_class,
                                      image=image.file if image else None,
                                      image_type=image.content_type if image else None
                                      ).model_dump()
   
    # Actualizar formulario con nueva info
    form_manager.update_form(extraction)

    if image:
        os.makedirs(IMAGES_FOLDER, exist_ok=True)
        image.file.seek(0)  # Reset file pointer to beginning
        image_location = f"{IMAGES_FOLDER}/{image.filename}"
        with open(image_location, "wb") as f:
            f.write(image.file.read())
        form_manager.add_image_reference(image.filename)
    form_manager.save_form_to_json()
    
    # Comparar con estado anterior para detectar cambios
    changes = form_manager.diff_fields(reduced_form, extraction)

    # Llamar al LLM con estado reducido y cambios
    llm_output = call_llm(form_manager.get_reduced_form(selected_sections), recent_messages, changes)

    return {
        "reply": llm_output,
        "state": form_manager.get_form(),
        "updates": changes
    }

