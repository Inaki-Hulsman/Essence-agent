
from typing import Dict, Any


# -----------------------
# 🧰 TOOL SCHEMA BUILDER
# -----------------------

def build_router_schema(tool_names: list[str]) -> Dict[str, Any]:
    """
    Schema mínimo para la decisión binaria: ¿necesito tool o no?
    Separar el router del executor reduce alucinaciones en Gemma.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "routing_decision",
            "schema": {
                "type": "object",
                "properties": {
                    "needs_tool": {"type": "boolean"},
                    "tool_name": {
                        "type": "string",
                        "enum": tool_names + ["none"]
                    },
                    "reason": {"type": "string"}
                },
                "required": ["needs_tool", "tool_name"],
                "additionalProperties": False
            }
        }
    }


def build_tool_schema(tool_name: str, tools: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schema específico por tool — mucho más preciso que un schema genérico.
    Gemma sigue mejor instrucciones cuando el schema es concreto.
    """
    # Buscar el schema de parámetros en TOOL_SCHEMAS
    tool_def = next((t for t in TOOL_SCHEMAS if t["name"] == tool_name), None)
    if not tool_def:
        # Fallback genérico
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "tool_call",
                "schema": {
                    "type": "object",
                    "properties": {
                        "arguments": {"type": "object", "additionalProperties": True}
                    },
                    "required": ["arguments"],
                    "additionalProperties": False
                }
            }
        }

    params_schema = tool_def.get("parameters", {"type": "object", "properties": {}})

    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{tool_name}_call",
            "schema": params_schema
        }
    }


# -----------------------
# 📚 TOOL DEFINITIONS
# -----------------------

def get_tools_and_descriptions():

    return "\n".join([f"- {tool['name']}: {tool['description']}" for tool in TOOL_SCHEMAS])

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_form",
        "description": "Retrieves the current form state",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },{
        "type": "function",
        "name": "new_form",
        "description": "Creates a new empty form, overwriting the existing one",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "extract_and_update",
        "description": "Extracts information from the user and updates the form fields; you can use information from the uploaded image to analyze it and add it to the form fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "User message containing the information to be extracted. Always provide enough context to fill in the field with the relevant information"
                },
                "selected_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Complete form field paths must always be in the format ‘Section.Subsection.field’, e.g.: ['produccion.vision_estrategica.posicionamiento']"
                },
                "use_loaded_image": {
                    "type": "boolean",
                    "description": "The value should be True if the user requests that information about the uploaded image be added, and False if the image is not mentioned."
                }
            },
            "required": ["message", "selected_sections", "use_loaded_image"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "is_uploaded_image",
        "description": "Checks if an image has been uploaded",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]