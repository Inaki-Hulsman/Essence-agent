import asyncio
import json
import os
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.config import IMAGES_FOLDER
from app.services.form_manager import FormManager
from app.services.llm import extract_section_info
from app.services.logger import logger
from app.services.utils import encode_file, load_image

from app.realtime.stt_service import STTService
from app.realtime.tts_service import TTSService
from app.realtime.llm import stream_llm_response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 🗂️  FORM REST ENDPOINTS  (sin cambios respecto al original)
# =============================================================================

form_manager: FormManager = FormManager()


@app.get("/get_form")
async def get_form(new: bool = False):

    form = form_manager.load_empty_form() if new else form_manager.get_form()
    images_refs = form_manager.get_all_image_references()
    images = {}
    for img_ref in images_refs:
        try:
            img_path = f"{IMAGES_FOLDER}/{img_ref}" if not img_ref.startswith(IMAGES_FOLDER) else img_ref
            images[img_ref] = encode_file(img_path)
        except Exception as e:
            logger.error(f"Error reading image {img_ref}: {e}")
    return {"form": form, "images": images}


@app.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):
    try:
        os.makedirs(IMAGES_FOLDER, exist_ok=True)
        file.file.seek(0)
        image_path = f"{IMAGES_FOLDER}/{file.filename}"
        if file.filename and file.content_type:
            form_manager.set_current_image(file.filename, file.content_type)
        with open(image_path, "wb") as f:
            f.write(file.file.read())
        return {"status": "ok", "filename": file.filename}
    except Exception as e:
        return {"error": str(e)}


@app.post("/delete_loaded_image")
async def delete_loaded_image():
    try:
        form_manager.clear_current_image()
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# 🧰  AGENT TOOLS  (misma lógica, desacoplada del transport)
# =============================================================================

async def get_form_agent(new: bool = False) -> str:
    form = form_manager.load_empty_form() if new else form_manager.get_form()
    return json.dumps(form, ensure_ascii=False)


async def extract_and_update(
    message: str,
    selected_sections: List[str],
    use_loaded_image: bool = False
) -> str:
    reduced_form = form_manager.get_very_reduced_form(selected_sections)
    reduced_form_class = form_manager.get_form_as_class(reduced_form)

    if use_loaded_image:
        image_name = form_manager.get_current_image().get("name", "")
        image = load_image(f"{IMAGES_FOLDER}/{image_name}")
        extraction = extract_section_info(
            [message], reduced_form, reduced_form_class,
            image=image,
            image_type=form_manager.get_current_image()["type"] if image else None,
        ).model_dump()
        form_manager.add_image_reference(image_name)
    else:
        extraction = extract_section_info(
            [message], reduced_form, reduced_form_class
        ).model_dump()

    form_manager.update_form(extraction)
    form_manager.save_form_to_json()
    return json.dumps(extraction, ensure_ascii=False)


async def is_uploaded_image() -> bool:
    return form_manager.exists_current_image()


TOOLS = {
    "get_form": get_form_agent,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}


# =============================================================================
# 🌐  WEBSOCKET — protocolo compatible con el frontend existente
#
# Mensajes que llegan del cliente (JSON con "type"):
#   { "type": "audio",        "data": "<base64 PCM16>" }   ← chunk de micro
#   { "type": "session.start" }                             ← opcional, init
#   { "type": "session.stop"  }                             ← opcional, cierre
#
# Mensajes que el servidor envía al cliente (JSON con "type"):
#   { "type": "transcript.partial", "text": "..." }         ← STT parcial
#   { "type": "transcript.final",   "text": "..." }         ← STT final
#   { "type": "response.text.delta","text": "..." }         ← LLM chunk
#   { "type": "response.text.done", "text": "..." }         ← LLM completo
#   { "type": "response.audio.delta","data": "<base64>" }   ← TTS chunk PCM16
#   { "type": "response.audio.done" }                       ← fin de audio
#   { "type": "tool.called",        "name": "...",
#     "result": "..." }                                     ← debug tool
# =============================================================================

# Singletons de STT y TTS — se cargan una vez al arrancar
_stt: STTService | None = None
_tts: TTSService | None = None


@app.on_event("startup")
async def startup():
    global _stt, _tts
    _stt = STTService()
    _stt.start()
    _tts = TTSService()


@app.websocket("/ws")
async def websocket_agent(client_ws: WebSocket):
    await client_ws.accept()
    print("🟢 Client connected")

    # Cada conexión tiene su propia conversación y buffer STT
    conversation: list = []
    stt = STTService()          # instancia por conexión para aislar buffers VAD
    stt.start()

    # Cola para pasar texto final del STT al pipeline LLM→TTS
    text_queue: asyncio.Queue[str] = asyncio.Queue()

    # -------------------------------------------------------------------------
    # 📥  TAREA 1: recibir audio del cliente, alimentar STT
    # -------------------------------------------------------------------------
    async def receive_audio():
        import base64
        try:
            while True:
                raw = await client_ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue


                msg_type = msg.get("type", "")
                

                if msg_type == "audio":
                    # PCM16 en base64
                    pcm = base64.b64decode(msg.get("audio", ""))
                    stt.push_audio(pcm)

                elif msg_type == "session.stop":
                    break

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"❌ receive_audio: {e}")
        finally:
            stt.stop()
            await text_queue.put(None)  # type: ignore - señal de cierre para el pipeline LLM→TTS

    # -------------------------------------------------------------------------
    # 📡  TAREA 2: escuchar eventos STT y reenviar al cliente / encolar texto
    # -------------------------------------------------------------------------
    async def process_stt_events():
        try:
            async for event in stt.events():
                if event["type"] == "transcript.partial":
                    await client_ws.send_text(json.dumps({
                        "type": "transcript.partial",
                        "text": event["text"]
                    }))

                elif event["type"] == "transcript.final":
                    text = event["text"]
                    print(f"🎤 Final transcript: {text}")

                    # Enviar al cliente para mostrar en UI
                    await client_ws.send_text(json.dumps({
                        "type": "transcript.final",
                        "text": text
                    }))

                    # Encolar para el pipeline LLM→TTS
                    await text_queue.put(text)

                else:
                    print(f"⚠️  Unknown STT event: {event}")

        except Exception as e:
            print(f"❌ process_stt_events: {e}")

    # -------------------------------------------------------------------------
    # 🧠  TAREA 3: LLM + TTS — procesar mensajes del usuario en orden
    # -------------------------------------------------------------------------
    async def llm_tts_pipeline():
        import base64

        async def _send_audio_chunk(pcm: bytes):
            """Enviar chunk de audio PCM16 al cliente en base64."""
            await client_ws.send_text(json.dumps({
                "type": "response.audio.delta",
                "data": base64.b64encode(pcm).decode()
            }))

        try:
            while True:
                print("⏳ Waiting for user text...")
                user_text = await text_queue.get()
                if user_text is None:
                    break  # señal de cierre

                # Añadir mensaje del usuario al historial
                conversation.append({"role": "user", "content": user_text})

                # ── LLM en streaming ──────────────────────────────────────
                full_response = ""

                async def llm_gen():
                    """Generador que también reenvía chunks de texto al cliente."""
                    nonlocal full_response
                    async for chunk in stream_llm_response(conversation, TOOLS):
                        full_response += chunk
                        # Reenviar texto al cliente (para subtítulos, debug…)
                        await client_ws.send_text(json.dumps({
                            "type": "response.text.delta",
                            "text": chunk
                        }))
                        yield chunk

                # ── TTS en streaming sobre el texto del LLM ───────────────
                async for pcm_chunk in _tts.synthesize_stream(llm_gen()):  # type: ignore
                    await _send_audio_chunk(pcm_chunk)

                # Notificar fin de respuesta
                await client_ws.send_text(json.dumps({
                    "type": "response.text.done",
                    "text": full_response
                }))
                await client_ws.send_text(json.dumps({
                    "type": "response.audio.done"
                }))

                print(f"🤖 Response done ({len(full_response)} chars)")

        except Exception as e:
            print(f"❌ llm_tts_pipeline: {e}")

    # -------------------------------------------------------------------------
    # 🚀  Lanzar las tres tareas en paralelo
    # -------------------------------------------------------------------------
    try:
        await asyncio.gather(
            receive_audio(),
            process_stt_events(),
            llm_tts_pipeline(),
        )
    except Exception as e:
        print(f"🔥 WS error: {e}")
    finally:
        stt.stop()
        print("🔴 Connection closed")
        await client_ws.close()