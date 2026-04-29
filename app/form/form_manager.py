import json
import os
from typing import Literal, Optional, List, Dict, Any

from app.config import IMAGES_FOLDER
from app.services.logger import logger

from pydantic import BaseModel, create_model



class Field_Text(BaseModel):
    value: str = ""
    status: Literal["empty", "agent", "user", "default", "image_ref"] = "empty"
    description: Optional[str] = None


FIELD_KEYS = set(Field_Text.model_fields.keys())

form_path = "app/data/form.json"
empty_form_path = "app/data/empty_form.json"





class FormManager:

    def __init__(self, form_path: str = form_path):
        self.form_path = form_path
        self.current_image_name : str = ""
        self.current_image_type : str = ""
        self.load_form_from_json()

    def get_form_as_class(self, dic: dict) -> type:
        FormModel = dict_to_custom_class("Form", dic)
        return FormModel # type: ignore
    
    def get_reduced_form(self, selected_sections: List[str]) -> dict:
        form = self.get_form()
        reduced_form = {section: form[section] for section in selected_sections if section in form}
        return self.get_clean_form(reduced_form)
    
    def get_very_reduced_form(self, selected_fields: List[str]):
        form = self.get_form()

        reduced = {}

        for section in selected_fields:

            if section not in self.get_fields_path(form):
                 return False, None
            keys = section.split(".")
            src = form
            dst = reduced

            for i, key in enumerate(keys):

                # Si es el último nivel, copiamos el valor
                if i == len(keys) - 1:
                    dst[key] = src[key]
                else:
                    # Creamos el nivel si no existe
                    if key not in dst or not isinstance(dst[key], dict):
                        dst[key] = {}

                    # Avanzamos en ambos diccionarios
                    dst = dst[key]
                    src = src[key]

        return True, self.get_clean_form(reduced) 
    
    def get_clean_form(self, form: dict) -> dict:

        cleaned = {}
        for k, v in form.items():
            if isinstance(v, dict):
                # Si parece un Field
                if set(v.keys()) >= set(FIELD_KEYS):
                    # Keep only value, status, description
                    cleaned[k] = {key: v[key] for key in FIELD_KEYS if key in v}
                else:
                    # Recurse
                    cleaned[k] = self.get_clean_form(v)
            else:
                cleaned[k] = v
        return cleaned
    
    def get_fields_path(self, form : dict):
        
        fields = []

        for k, v in form.items():
            if isinstance(v, dict):
                # Si parece un Field
                if set(v.keys()) >= set(FIELD_KEYS):
                    # Keep only value, status, description
                    fields.append(k)
                else:
                    # Recurse
                    sons = self.get_fields_path(v)
                    fields.extend([k + "." + s for s in sons])

        return fields


    def load_form_from_json(self, json_path: str = "") -> dict:

        if not json_path:
            json_path = self.form_path

        logger.info(f"Cargando formulario desde {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            self.form = json.load(f)
            # logger.info(f"Formulario cargado: {self.form}")

        return self.form
    
    def load_empty_form(self, json_path: str = "") -> dict:
        return self.load_form_from_json(empty_form_path)

    def save_form_to_json(self, json_path: str = ""):
        if not json_path:
            json_path = self.form_path
        with open(json_path, "w", encoding="utf-8") as f:
            # print("Guardando formulario en JSON")
            json.dump(self.form, f, indent=2, ensure_ascii=False)

    def get_form(self) -> dict:
        if not hasattr(self, "form"):
            return self.load_form_from_json()
        return self.form
    
    def set_form(self, new_form: dict):
        self.form = new_form

    def add_image_reference(self, image):
        self._add_image_ref_recursive(self.form, image)

    def _add_image_ref_recursive(self, form, image):
        for k, v in form.items():
            if isinstance(v, dict):
                if v.get("status") == "image_ref":
                    if "references" not in v:
                        v["references"] = []
                    v["references"].append(image)
                    v["status"] = "agent"
                else:
                    self._add_image_ref_recursive(v, image)
    
    def update_form(self, updates: dict):
        self._recursive_update(self.form, updates)

    def _recursive_update(self, target: dict, source: dict):
        for k, v in source.items():
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                if set(target[k].keys()) >= set(FIELD_KEYS):
                    # Update only value, status, description
                    for field in FIELD_KEYS:
                        if field in v:
                            target[k][field] = v[field]
                else:
                    # Recurse
                    self._recursive_update(target[k], v)
            else:
                target[k] = v

    def is_field(self, d: Any) -> bool:
        return isinstance(d, dict) and FIELD_KEYS.issubset(d.keys())


    def get_all_image_references(self, form: dict|None = None) -> List[str]:
        """Extrae recursivamente todas las referencias de imágenes del formulario."""
        if form is None:
            form = self.get_form()
        
        references = []
        self._extract_references_recursive(form, references)
        return references
    
    def _extract_references_recursive(self, d: dict, references: List[str]):
        """Busca recursivamente campos 'references' en el diccionario."""
        for k, v in d.items():
            if k == "references" and isinstance(v, list):
                references.extend(v)
            elif isinstance(v, dict):
                self._extract_references_recursive(v, references)

    def diff_fields(self, d1: Dict, d2: Dict, path: str = "") -> List[Dict]:
        """Compara dos diccionarios de formulario y devuelve una lista de cambios detectados en los campos.
        Cada cambio incluye la ruta al campo y las diferencias encontradas."""

        diffs = []

        all_keys = set(d1.keys()) | set(d2.keys())

        for key in all_keys:
            new_path = f"{path}.{key}" if path else key

            v1 = d1.get(key)
            v2 = d2.get(key)

            # Caso 1: ambos son Field → comparar
            if self.is_field(v1) and self.is_field(v2):
                changes = {}
                for k in FIELD_KEYS:
                    if v1.get(k) != v2.get(k): # type: ignore
                        changes[k] = {
                            "from": v1.get(k), # type: ignore
                            "to": v2.get(k) # type: ignore
                        }

                if changes:
                    diffs.append({
                        "path": new_path,
                        "changes": changes
                    })

            # Caso 2: dicts normales → recursión
            elif isinstance(v1, dict) and isinstance(v2, dict):
                diffs.extend(self.diff_fields(v1, v2, new_path))

            # Caso 3: uno es Field y otro no (edge case)
            elif self.is_field(v1) or self.is_field(v2):
                diffs.append({
                    "path": new_path,
                    "changes": {
                        "type": {
                            "from": type(v1).__name__,
                            "to": type(v2).__name__
                        }
                    }
                })

            # Otros casos → ignoramos (porque no son Field)

        return diffs

    def get_current_image(self) -> dict:
        return {"name": self.current_image_name, "type": self.current_image_type}
    
    def set_current_image(self, image_name: str, image_type: str):
        self.current_image_name = image_name
        self.current_image_type = image_type

    def exists_current_image(self):
        return os.path.isfile(f"{IMAGES_FOLDER}/{self.current_image_name}")
    
    def clear_current_image(self):
        self.current_image_name = ""
        self.current_image_type = ""


    def update_field(self, path: str, value: str):
        """
        path = "seccion.grupo.campo"  ej: "produccion.vision_estrategica.posicionamiento"
        """
        keys = path.split(".")
        form = self.get_form()
        
        node = form
        for key in keys[:-1]:
            node = node[key]
        
        node[keys[-1]]["value"] = value
        node[keys[-1]]["status"] = "user"
        
        self.update_form(form)
        self.save_form_to_json()
        return




def dict_to_custom_class(name: str, d: Dict[str, Any]) -> BaseModel:
    """
    Convierte un diccionario en un modelo Pydantic dinámico.
    """
    fields = {}
    for k, v in d.items():
        if isinstance(v, dict):
            # Si parece un Field
            if set(v.keys()) >= Field_Text.model_fields.keys():
                fields[k] = (Field_Text, Field_Text(**v))
            else:
                # Crear modelo anidado recursivamente
                nested_model = dict_to_custom_class(k.capitalize(), v)
                fields[k] = (nested_model, nested_model(**v)) # type: ignore
        elif isinstance(v, list):
            # Convertir listas a esquemas tipados, especialmente list[str]
            if len(v) > 0:
                item_type = type(v[0])
                fields[k] = (List[item_type], v)
            else:
                fields[k] = (List[str], v)
        else:
            # Para valores simples
            fields[k] = (type(v), v)
    
    # Crear modelo dinámico
    model = create_model(name, **fields)
    return model # type: ignore
