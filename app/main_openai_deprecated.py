import asyncio
import websockets
import json
import os
from fastapi import FastAPI, WebSocket, UploadFile, File
from app.config import IMAGES_FOLDER, OPENAI_API_KEY, OPENAI_WS_URL
from app.services.form_manager import FormManager
from app.realtime.llm import extract_section_info
from app.services.logger import logger
from typing import List 


from app.services.utils import encode_file, load_image

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:3000",  # tu frontend
    "http://127.0.0.1:3000",
    "http://192.168.1.13:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # o ["*"] para permitir todo (solo dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# -----------------------
# 🧰 TOOLS
# -----------------------

form_manager: FormManager = FormManager()  # Singleton FormManager


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


@app.post("/upload_image")
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
    

@app.post("/delete_loaded_image")
async def delete_loaded_image():
    try:
        # current_image = form_manager.get_current_image()
        # if current_image:
        #     image_path = f"{IMAGES_FOLDER}/{current_image['name']}"
        #     if os.path.exists(image_path):
        #         os.remove(image_path)
        print("Borrando imagen cargada actualmente en form_manager")
        global form_manager
        form_manager.clear_current_image()
        #     return {"status": "ok"}
        # else:
        #     return {"error": "No image to delete"}
    except Exception as e:
        return {"error": str(e)}

async def get_form_agent(new: bool = False) -> str:
    global form_manager
    if not form_manager:
        form_manager =FormManager()
    fm = form_manager
    if new:
        form = fm.load_empty_form()
    else:
        form = fm.get_form()
    return json.dumps(form, ensure_ascii=False)



async def extract_and_update(message: str, selected_sections: List[str], use_loaded_image: bool = False) -> str:
    
    global form_manager
    if not form_manager:
        form_manager =FormManager()
    fm = form_manager
    reduced_form = fm.get_very_reduced_form(selected_sections)
    print(f"Formulario reducido para secciones seleccionadas: {reduced_form}")
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

    print( f"Verificando si hay imagen cargada. Imagen actual: {form_manager.get_current_image()['name']}" )

    return form_manager.exists_current_image()


TOOLS = {
    "get_form": get_form_agent,
    # "update_form": update_form,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}

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
                    "description": "Si es True, devuelve un formulario vacío, si es False devuelve el actual"
                }
            },
        }
    },
    {
        "type": "function",
        "name": "extract_and_update",
        "description": "Extrae información del mensaje del usuario para secciones seleccionadas y actualiza el formulario",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Mensaje del usuario"},
                "selected_sections": {"type": "array", "items": {"type": "string"}, "description": "Lista de secciones seleccionadas, siempre son una ruta completa de las claves del formulario, por ejemplo: ['produccion.vision_estrategica.posicionamiento', 'direccion.nota_de_direccion.vision_autoral']"},
                "use_loaded_image": {"type": "boolean", "description": "Indica si se debe utilizar la imagen cargada por el usuario. El backend ya tiene acceso a la imagen real, esta referencia es para que la función de extracción pueda relacionar la imagen con el campo correspondiente del formulario"}
            },
            "required": [ "message", "selected_sections"]
        }
    },{
        "type": "function",
        "name": "is_uploaded_image",
        "description": "Verifica si hay una imagen subida por el usuario, para añadirla como parametro de extracción de información en secciones del formulario",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# -----------------------
# ⚙️ AGENT RUNTIME
# -----------------------

class AgentRuntime:
    def __init__(self, openai_ws):
        self.openai_ws = openai_ws
        # Buffers de tool calls en curso: { call_id: { name, arguments } }
        self.pending_calls: dict[str, dict] = {}

    async def send_session_config(self):
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700,
                },
                "instructions": "Eres un asistente que ayuda a rellenar formularios. Usa las tools disponibles para obtener y actualizar el formulario basado en la conversación con el usuario. Responde siempre en el idioma del usuario.",
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto",
            }
        }))

    async def run_tool(self, name: str, args: dict) -> str:
        if name not in TOOLS:
            return f"Error: la tool '{name}' no existe"
        try:
            result = await TOOLS[name](**args)
            return str(result)
        except Exception as e:
            logger.error(f"Error ejecutando {name}: {e}")
            return f"Error ejecutando {name}: {e}"

    def on_function_call_started(self, call_id: str, name: str):
        """Llamado cuando OpenAI anuncia una nueva function call (output_item.added)."""
        self.pending_calls[call_id] = {"name": name, "arguments": ""}
        print(f"🛠  Tool iniciada: {name} [{call_id}]")

    def on_arguments_delta(self, call_id: str, delta: str):
        """Acumula el JSON de argumentos que llega en streaming."""
        if call_id in self.pending_calls:
            self.pending_calls[call_id]["arguments"] += delta

    async def on_arguments_done(self, call_id: str):
        """
        Llamado cuando response.function_call_arguments.done llega.
        En este punto los argumentos están completos → ejecutar la tool.
        """
        if call_id not in self.pending_calls:
            print(f"⚠️  call_id desconocido: {call_id}")
            return

        tool = self.pending_calls.pop(call_id)
        name = tool["name"]
        raw_args = tool["arguments"]

        print(f"🛠  Ejecutando: {name}({raw_args})")

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {}

        result = await self.run_tool(name, args)
        print(f"✅  Resultado: {result}")

        # 1️⃣  Añadir el resultado a la conversación
        await self.openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            }
        }))

        # 2️⃣  Pedir a OpenAI que genere la siguiente respuesta con ese resultado
        await self.openai_ws.send(json.dumps({
            "type": "response.create"
        }))


# -----------------------
# 🌐 WEBSOCKET ENDPOINT
# -----------------------

@app.websocket("/ws-openai")
async def websocket_agent(client_ws: WebSocket):
    await client_ws.accept()
    print("🟢 Client connected")

    try:
        async with websockets.connect(
            OPENAI_WS_URL,  # type: ignore
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:

            print("🟢 Connected to OpenAI")
            agent = AgentRuntime(openai_ws)
            await agent.send_session_config()

            # -----------------------
            # CLIENT → OPENAI
            # -----------------------
            async def client_to_openai():
                try:
                    while True:
                        msg = await client_ws.receive_text()
                        await openai_ws.send(msg)
                except Exception as e:
                    print("❌ client_to_openai:", e)

            # -----------------------
            # OPENAI → AGENT → CLIENT
            # -----------------------
            async def openai_to_client():
                try:
                    while True:
                        msg = await openai_ws.recv()
                        if not msg:
                            continue
                        try:
                            data = json.loads(msg)
                        except json.JSONDecodeError:
                            print("⚠️  Mensaje no-JSON:", msg)
                            continue

                        evt_type = data.get("type", "")

                        # ── Tool call: anuncio inicial (nombre + call_id) ──────
                        if evt_type == "response.output_item.added":
                            item = data.get("item", {})
                            if item.get("type") == "function_call":
                                agent.on_function_call_started(
                                    item["call_id"],
                                    item["name"]
                                )
                            # No reenviar al cliente (es tráfico interno)
                            continue

                        # ── Tool call: delta de argumentos ────────────────────
                        elif evt_type == "response.function_call_arguments.delta":
                            agent.on_arguments_delta(
                                data["call_id"],
                                data.get("delta", "")
                            )
                            continue

                        # ── Tool call: argumentos completos → ejecutar ────────
                        elif evt_type == "response.function_call_arguments.done":
                            await agent.on_arguments_done(data["call_id"])
                            continue

                        # ── Todo lo demás va al cliente (audio, transcripts…) ──
                        await client_ws.send_text(msg) # type: ignore

                except Exception as e:
                    print("❌ openai_to_client:", e)

            await asyncio.gather(
                client_to_openai(),
                openai_to_client()
            )

    except Exception as e:
        print("🔥 OPENAI CONNECTION ERROR:", e)

    finally:
        print("🔴 Connection closed")
        await client_ws.close()