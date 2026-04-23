import asyncio
import websockets
import json
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from app.config import OPENAI_API_KEY, OPENAI_WS_URL

from fastapi.middleware.cors import CORSMiddleware

# Servicios de STT y TTS (clientes de los microservicios)
from app.realtime.openai_agent import OpenaiAgentRuntime
from app.realtime.vllm_agent import VllmAgentRuntime
from app.realtime.stt_service import STTService
from app.realtime.tts_service import TTSService

from app.tools.tools import get_form, upload_image, delete_loaded_image


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
    return get_form(new)


@app.post("/upload_image")
async def upload_image_endpoint(file: UploadFile = File(...)):
    return await upload_image(file)
    

@app.post("/delete_loaded_image")
async def delete_loaded_image_endpoint():
    return await delete_loaded_image()


@app.on_event("startup")
async def startup():
    global _stt, _tts
    _stt = STTService()
    _stt.start()
    _tts = TTSService()


# -----------------------
# 🌐 WEBSOCKET VLLM ENDPOINT
# -----------------------

@app.websocket("/ws-vllm")
async def websocket_vllm_agent(client_ws: WebSocket):
    await client_ws.accept()
    print("🟢 Client connected")

    stt = STTService()
    stt.start()
    text_queue: asyncio.Queue[str] = asyncio.Queue()

    # Instanciar el agent runtime
    agent = VllmAgentRuntime(client_ws, _tts)

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
        await client_ws.close()
        

# -----------------------
# 🌐 WEBSOCKET OPENAI ENDPOINT
# -----------------------

@app.websocket("/ws-openai")
async def websocket_openai_agent(client_ws: WebSocket):
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
            agent = OpenaiAgentRuntime(openai_ws)
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
                                agent.on_function_call_started(item["call_id"],item["name"])
                            # No reenviar al cliente (es tráfico interno)
                            continue

                        # ── Tool call: delta de argumentos ────────────────────
                        elif evt_type == "response.function_call_arguments.delta":
                            agent.on_arguments_delta(data["call_id"],data.get("delta", ""))
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