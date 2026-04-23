from app.config import IMAGES_FOLDER
import json
import os
from fastapi import UploadFile, File
from app.realtime.llm import extract_section_info
from app.services.logger import logger
from typing import List 
from app.services.utils import encode_file, load_image

from app.services.form_manager import FormManager

form_manager: FormManager = FormManager()  # Singleton FormManager


def get_form(new: bool = False):
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


async def upload_image(file: UploadFile = File(...)):

    try:
        os.makedirs(IMAGES_FOLDER, exist_ok=True)

        file.file.seek(0)
        image_path = f"{IMAGES_FOLDER}/{file.filename}"

        if file.filename and file.content_type:
            global form_manager
            form_manager.set_current_image(file.filename, file.content_type)

        with open(image_path, "wb") as f:
            f.write(file.file.read())

        return {
            "status": "ok",
            "filename": file.filename
        }

    except Exception as e:
        return {"error": str(e)}
    

async def delete_loaded_image():
    try:
        global form_manager
        form_manager.clear_current_image()
        return {"status": "ok"}
    
    except Exception as e:
        return {"error": str(e)}

async def get_form_agent(new: bool = False) -> str:
    global form_manager

    fm = form_manager
    if new:
        form = fm.load_empty_form()
    else:
        form = fm.get_form()
    return json.dumps(form, ensure_ascii=False)



async def extract_and_update(message: str, selected_sections: List[str], use_loaded_image: bool = False) -> str:
    
    global form_manager

    fm = form_manager
    reduced_form = fm.get_very_reduced_form(selected_sections)
    reduced_form_class = fm.get_form_as_class(reduced_form)

    if use_loaded_image:
        image_name = fm.get_current_image().get("name", "")
        image = load_image(f"{IMAGES_FOLDER}/{image_name}")
        extraction = extract_section_info([message],
                                        reduced_form,
                                        reduced_form_class,
                                        image=image,
                                        image_type=fm.get_current_image()['type'] if image else None
                                        ).model_dump()
        fm.update_form(extraction)
        form_manager.add_image_reference(image_name)

    else:
        extraction = extract_section_info([message],reduced_form,reduced_form_class).model_dump()
        fm.update_form(extraction)

    fm.save_form_to_json()
    return json.dumps(extraction, ensure_ascii=False)


async def is_uploaded_image() -> bool:
    global form_manager
    return form_manager.exists_current_image()


TOOLS = {
    "get_form": get_form_agent,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}