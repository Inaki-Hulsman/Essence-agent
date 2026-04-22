import asyncio
from typing import Dict, Any

from app.realtime.llm import stream_llm_response


# -----------------------
# 🧰 TOOLS MOCK
# -----------------------

async def get_form(new: bool = False) -> str:
    print(f"\n  🔧 get_form(new={new})")
    return '{"nombre": "", "edad": ""}' if new else '{"nombre": "Juan", "edad": 30}'


async def extract_and_update(
    message: str,
    selected_sections: list,
    use_loaded_image: bool = False
) -> str:
    print(f"\n  🔧 extract_and_update(message='{message}', sections={selected_sections}, image={use_loaded_image})")
    return f"Extraído de '{message}' en secciones {selected_sections}"


async def is_uploaded_image() -> bool:
    print("\n  🔧 is_uploaded_image()")
    return False


TOOLS: Dict[str, Any] = {
    "get_form": get_form,
    "extract_and_update": extract_and_update,
    "is_uploaded_image": is_uploaded_image,
}


# -----------------------
# 🧠 TEST LOOP
# -----------------------

async def chat():
    # conversation se mantiene aquí y stream_llm_response la muta directamente,
    # añadiendo los mensajes de assistant y tool results en cada turno.
    conversation = []

    print("\n🧠 Test LLM (Gemma + vLLM)\n")
    print("Escribe 'exit' para salir\n")

    while True:
        user_input = input("👤 Tú: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("👋 Hasta luego")
            break

        conversation.append({
            "role": "user",
            "content": user_input
        })

        print("🤖 Asistente: ", end="", flush=True)

        async for chunk in stream_llm_response(conversation, TOOLS):
            print(chunk, end="", flush=True)

        print("\n")


# -----------------------
# 🚀 RUN
# -----------------------

if __name__ == "__main__":
    asyncio.run(chat())