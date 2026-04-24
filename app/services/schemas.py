
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
# 📋 SYSTEM PROMPTS
# -----------------------

INITIAL_INPUT = "Saluda al usuario y preséntate brevemente."

SYSTEM_PROMPT = """Eres un asistente DE VOZ que ayuda a rellenar formularios.

Tienes acceso a las siguientes herramientas:
- get_form: Obtiene el formulario actual o uno nuevo vacío
- extract_and_update: Extrae información del usuario y actualiza secciones del formulario, puede usar la información de la imagen subida para analizarla y añadirla a secciones del formulario.
- is_uploaded_image: Verifica si hay una imagen subida

Cuando el usuario proporcione información o pida algo relacionado con el formulario, usa las herramientas apropiadas.
Cuando solo sea una conversación general o pregunta, responde directamente sin herramientas.
No utilices asteriscos para resaltar texto, no utilices markdown, negritas ni cursivas.
Manten la conversación centrada en ayudar al usuario a completar el formulario, preguntándole por secciones aún sin completar"""


ROUTER_PROMPT = """Analiza el mensaje y el contexto. Decide si necesitas una herramienta.

Herramientas disponibles: {tool_names}

Responde con JSON indicando si necesitas tool y cuál. Si no necesitas ninguna, tool_name = "none"."""

EXECUTOR_PROMPT = """Basándote en el mensaje del usuario y el historial, genera los argumentos exactos para llamar a: {tool_name}

Descripción: {tool_description}
Parámetros requeridos: {required_params}

Genera SOLO los argumentos en JSON, sin texto adicional."""


# -----------------------
# 📚 TOOL DEFINITIONS
# -----------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_form",
        "description": "Obtiene el formulario actual o uno nuevo vacío",
        "parameters": {
            "type": "object",
            "properties": {
                "new": {
                    "type": "boolean",
                    "description": "Si es True, devuelve un formulario vacío. Si es False, devuelve el actual"
                }
            },
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "extract_and_update",
        "description": "Extrae información del usuario y actualiza secciones del formulario, puede usar la información de la imagen subida para analizarla y añadirla a secciones del formulario.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensaje del usuario con la información a extraer"
                },
                "selected_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rutas completas de secciones del formulario, ej: ['produccion.vision_estrategica.posicionamiento']"
                },
                "use_loaded_image": {
                    "type": "boolean",
                    "description": "el valor debe ser True si el usuario pide que se añada informacion de la imagen cargada, False si no se hace alusión a la imagen"
                }
            },
            "required": ["message", "selected_sections", "use_loaded_image"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "is_uploaded_image",
        "description": "Verifica si hay una imagen subida por el usuario",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]