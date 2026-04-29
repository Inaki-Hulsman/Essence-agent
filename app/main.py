import asyncio
from fastapi.websockets import WebSocketState
import websockets
import json
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from app.config import OPENAI_API_KEY, OPENAI_WS_URL, DEFAULT_LANGUAGE

from fastapi.middleware.cors import CORSMiddleware

# Servicios de STT y TTS (clientes de los microservicios)
from app.agents.openai_agent import OpenaiAgentRuntime
from app.agents.vllm_agent import VllmAgentRuntime
from app.services.stt_service import STTService
from app.services.tts_service import TTSService

from app.agents.prompts import get_text_prompt
from app.form.functions import get_form, get_form_text, get_images, update_field, upload_image, delete_loaded_image, remove_image_reference, upload_section_image

from app.agents.llm import llm_models



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

# Singletons de STT y TTS — se cargan una vez al arrancar
_stt: STTService | None = None
_tts: TTSService | None = None


@app.get("/get_form")
async def get_form_endpoint(new: bool = False):
    form = get_form(new)
    images = await get_images()

    return {
        "form": form,
        "images": images
    }


@app.patch("/update_field")
async def update_field_endpoint(body: dict):
    return await update_field(body["path"], body["value"])

@app.post("/upload_image")
async def upload_image_endpoint(file: UploadFile = File(...)):
    return await upload_image(file)
    
@app.post("/delete_loaded_image")
async def delete_loaded_image_endpoint():
    return await delete_loaded_image()

@app.post("/upload_section_image")
async def upload_section_image_endpoint(file: UploadFile = File(...), field_path: str = ""):
    return await upload_section_image(file, field_path)

@app.delete("/remove_image_reference")
async def remove_image_reference_endpoint(body: dict):
    return await remove_image_reference(body["field_path"], body["image_name"])

@app.on_event("startup")
async def startup():
    print("🚀 Starting up: initializing STT and TTS services...")
    global _stt, _tts
    _stt = STTService()
    _stt.start()
    _tts = TTSService()


# -----------------------
# 🌐 WEBSOCKET VLLM ENDPOINT
# -----------------------

@app.websocket("/ws-vllm")
async def websocket_vllm_agent(client_ws: WebSocket):
    voice = client_ws.query_params.get("voice", "ef_dora")

    await client_ws.accept()
    print("🟢 Client connected")
    llm_models.set_vllm_model()

    stt = STTService()
    stt.start()
    text_queue: asyncio.Queue[str] = asyncio.Queue()

    # Input inicial
    await text_queue.put(get_text_prompt(name = "initial_input",language = DEFAULT_LANGUAGE))

    # Instanciar el agent runtime
    agent = VllmAgentRuntime(client_ws, _tts) # type: ignore
    agent.set_voice(voice)


    async def receive_audio():
        import base64
        try:
            while True:
                raw = await client_ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "audio":
                    pcm = base64.b64decode(msg.get("audio", ""))
                    stt.push_audio(pcm)
                elif msg.get("type") == "text_input":
                    # Mensaje de texto del usuario — saltar STT, ir directo al pipeline
                    text = msg.get("text", "").strip()
                    if text:
                        agent.reset_interrupt()
                        await client_ws.send_text(json.dumps({
                            "type": "transcript.final",
                            "text": text
                        }))
                        await text_queue.put(text)
                elif msg.get("type") == "config":
                    voice = msg.get("voice", "ef_dora")
                    agent.set_voice(voice)
                elif msg.get("type") == "session.stop":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            stt.stop()
            await text_queue.put(None) # type: ignore

    async def process_stt_events():
        try:
            async for event in stt.events():
                if event["type"] == "transcript.partial":
                    await client_ws.send_text(json.dumps({
                        "type": "transcript.partial",
                        "text": event["text"]
                    }))

                elif event["type"] == "speech.started":
                    # ✅ Interrumpir: cancelar pipeline actual y avisar al frontend
                    agent.interrupt()
                    await client_ws.send_text(json.dumps({
                        "type": "input_audio_buffer.speech_started"
                    }))

                elif event["type"] == "transcript.final":
                    text = event["text"]
                    print(f"🎤 Final: {text}")
                    agent.reset_interrupt()  # ✅ reset para la nueva respuesta
                    await client_ws.send_text(json.dumps({
                        "type": "transcript.final",
                        "text": text
                    }))
                    await text_queue.put(text)

        except Exception as e:
            print(f"❌ process_stt_events: {e}")

    async def llm_tts_pipeline():
        try:
            while True:
                user_text = await text_queue.get()
                if user_text is None:
                    break

                agent.add_user_message(user_text)
                print(f"🤖 Generating response for: {user_text}")
                await agent.generate_response()

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
        try:
            if client_ws.application_state == WebSocketState.CONNECTED:
                await client_ws.close()
        except RuntimeError:
            pass
        
        

# -----------------------
# 🌐 WEBSOCKET OPENAI ENDPOINT
# -----------------------

@app.websocket("/ws-openai")
async def websocket_openai_agent(client_ws: WebSocket):
    await client_ws.accept()
    print("🟢 Client connected")
    llm_models.set_openai_model()

    try:
        async with websockets.connect(
            OPENAI_WS_URL,  # type: ignore
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:

            print("🟢 Connected to OpenAI")
            agent = OpenaiAgentRuntime(openai_ws)
            await agent.send_session_config()

            # ✅ Mensaje de bienvenida: inyectar en la conversación y pedir respuesta, AÑADE EL CONTEXTO DEL FORMULARIO
            await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": f"Este es el estado actual del formulario: {get_form_text()}.\n" + get_text_prompt(name = "initial_input",language = DEFAULT_LANGUAGE)}]
                }
            }))
            await openai_ws.send(json.dumps({"type": "response.create"}))

            # -----------------------
            # CLIENT → OPENAI
            # -----------------------
            async def client_to_openai():
                try:
                    while True:
                        raw = await client_ws.receive_text()
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            await openai_ws.send(raw)
                            continue

                        if msg.get("type") == "text_input":
                            text = msg.get("text", "").strip()
                            if text:
                                # Mostrar en el chat del cliente
                                await client_ws.send_text(json.dumps({
                                    "type": "transcript.final",
                                    "text": text
                                }))
                                await agent.send_text_message(text)
                        else:
                            await openai_ws.send(raw)
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
                            print("⚠️ Mensaje no-JSON:", msg)
                            continue

                        evt_type = data.get("type", "")

                        # ── Tool call: anuncio inicial (nombre + call_id) ──────
                        if evt_type == "response.output_item.added":
                            item = data.get("item", {})
                            if item.get("type") == "function_call":
                                agent.on_function_call_started(item["call_id"], item["name"])
                            continue

                        # ── Tool call: delta de argumentos ────────────────────
                        elif evt_type == "response.function_call_arguments.delta":
                            agent.on_arguments_delta(data["call_id"], data.get("delta", ""))
                            continue

                        # ── Tool call: argumentos completos → ejecutar ────────
                        elif evt_type == "response.function_call_arguments.done":
                            await agent.on_arguments_done(data["call_id"])
                            continue

                        # ── Todo lo demás va al cliente (audio, transcripts…) ──
                        await client_ws.send_text(msg)  # type: ignore

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
        try:
            if client_ws.application_state == WebSocketState.CONNECTED:
                await client_ws.close()
        except RuntimeError:
            pass