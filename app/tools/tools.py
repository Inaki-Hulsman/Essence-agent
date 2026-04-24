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

async def update_field(path: str, value: str):
    """
    path = "seccion.grupo.campo"  ej: "produccion.vision_estrategica.posicionamiento"
    """
    keys = path.split(".")
    form = form_manager.get_form()
    
    node = form
    for key in keys[:-1]:
        node = node[key]
    
    node[keys[-1]]["value"] = value
    node[keys[-1]]["status"] = "user"
    
    form_manager.update_form(form)
    form_manager.save_form_to_json()
    return {"ok": True, "path": path, "value": value}


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

    print(f"Called get_form with new: {new}")

    fm = form_manager
    if new:
        form = fm.load_empty_form()
    else:
        form = fm.get_form()
    return json.dumps(form, ensure_ascii=False)



async def extract_and_update(message: str, selected_sections: List[str], use_loaded_image: bool = False) -> str:
    
    print("Calling extract_and_update, use_image = ", use_loaded_image)
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
    is_image = form_manager.exists_current_image()
    print("Called is_image, result: ", is_image)
    return is_image


async def remove_image_reference(field_path: str, image_name: str):
    """
    Desasocia una imagen de un campo del formulario.
    field_path = "seccion.grupo.campo"
    Si ningún otro campo referencia la imagen, borra el archivo del disco.
    """
    global form_manager
    fm = form_manager
    form = fm.get_form()

    # 1. Quitar la referencia del campo
    keys = field_path.split(".")
    node = form
    try:
        for key in keys[:-1]:
            node = node[key]
        field = node[keys[-1]]
        refs = field.get("references", [])
        if image_name in refs:
            refs.remove(image_name)
        field["references"] = refs
    except (KeyError, TypeError) as e:
        return {"error": f"Campo no encontrado: {e}"}

    fm.update_form(form)
    fm.save_form_to_json()

    # 2. Comprobar si algún otro campo sigue referenciando la imagen
    all_refs = fm.get_all_image_references()
    if image_name not in all_refs:
        # Nadie más la usa → borrar archivo
        img_path = f"{IMAGES_FOLDER}/{image_name}"
        if os.path.exists(img_path):
            os.remove(img_path)
            logger.info(f"Imagen eliminada del disco: {img_path}")

    return {"ok": True, "deleted_from_disk": image_name not in all_refs}


async def upload_section_image(file: UploadFile, field_path: str):
    """
    Sube una imagen y la asocia directamente a un campo del formulario.
    field_path = "seccion.grupo.campo"  (o "seccion" para nivel sección)
    """
    global form_manager
    fm = form_manager

    try:
        os.makedirs(IMAGES_FOLDER, exist_ok=True)
        file.file.seek(0)
        image_path = f"{IMAGES_FOLDER}/{file.filename}"

        with open(image_path, "wb") as f:
            f.write(file.file.read())

        # Asociar al campo si se especificó ruta completa (3 niveles)
        keys = field_path.split(".")
        if len(keys) == 3:
            form = fm.get_form()
            node = form
            try:
                for key in keys[:-1]:
                    node = node[key]
                field = node[keys[-1]]
                refs = field.get("references", [])
                if file.filename not in refs:
                    refs.append(file.filename)
                field["references"] = refs
                fm.update_form(form)
                fm.save_form_to_json()
            except (KeyError, TypeError):
                pass  # path inválido, imagen subida igualmente

        # También registrar como imagen activa del form_manager
        if file.filename and file.content_type:
            fm.set_current_image(file.filename, file.content_type)

        return {"status": "ok", "filename": file.filename}

    except Exception as e:
        return {"error": str(e)}


TOOLS = {
    "get_form": get_form_agent,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}