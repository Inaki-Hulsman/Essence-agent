import streamlit as st
import requests
import json
import base64
from io import BytesIO
from PIL import Image

API_URL = "http://localhost:8000"

CHAT_PATH = API_URL + "/chat"
FORM_PATH = API_URL + "/get_form"

st.set_page_config(layout="wide")

# Estado local
if "messages" not in st.session_state:
    st.session_state.messages = []

if "state" not in st.session_state:
    st.session_state.state = {}

if "images" not in st.session_state:
    st.session_state.images = {}

USER_ID = "demo-user"

def render_field(key, field, path, images=None):
    if images is None:
        images = {}
    
    full_path = ".".join(path + [key])

    # Campo simple estructurado
    if isinstance(field, dict) and "value" in field:
        value = field["value"]
        status = field.get("status", "empty")

        # 🎨 color según origen
        color = {
            "empty": "⚪",
            "agent": "🟣",
            "user": "🟢",
            "default": "🔵"
        }.get(status, "⚪")

        # st.markdown(f"{color} **{key}**")

        # Tipo texto
        if isinstance(value, str):
            new_value = st.text_area(
                f"{color} **{key.replace('_', ' ')}**",
                value=value,
                key=full_path
            )

        # Tipo lista
        elif isinstance(value, list):
            new_value = st.text_area(
                f"{color} **{key}**",
                value="\n".join(value),
                key=full_path
            )
            new_value = [v.strip() for v in new_value.split("\n") if v.strip()]

        else:
            new_value = value

        # Detectar cambio
        if new_value != value:
            field["value"] = new_value
            field["status"] = "user"

        # Mostrar imágenes de referencias si existen
        if "references" in field and field["references"]:
            st.markdown("**📷 Imágenes de referencia:**")
            cols = st.columns(len(field["references"]))
            for col, img_ref in zip(cols, field["references"]):
                if img_ref in images:
                    try:
                        # Decodificar base64
                        img_data = base64.b64decode(images[img_ref])
                        img = Image.open(BytesIO(img_data))
                        with col:
                            img_name = img_ref.split("/")[-1]
                            cropped_name = img_name if len(img_name) <= 15 else img_name[:12] + "..."
                            st.image(img, caption=cropped_name, width=100)
                    except Exception as e:
                        st.error(f"Error loading image {img_ref}: {e}")

        return

    # Nodo intermedio
    elif isinstance(field, dict):
        # Manejar meta si existe
        if "meta" in field:
            enabled = field["meta"].get("enabled", False)
            new_enabled = st.checkbox(
                f"Enable {key.replace('_', ' ').capitalize()}",
                value=enabled,
                key=f"{full_path}_enabled"
            )
            if new_enabled != enabled:
                field["meta"]["enabled"] = new_enabled
            enabled = new_enabled  # usar el nuevo valor
        else:
            enabled = True  # si no hay meta, asumir enabled

        if enabled:
            with st.expander(key.replace('_', ' ').capitalize(), expanded=False):
                for subkey, subfield in field.items():
                    if subkey == "meta": continue
                    else:
                        render_field(subkey, subfield, path + [key], images)

def load_form(new=False):
    response = requests.get(FORM_PATH, params={"new": new})

    if response.status_code == 200:
        result = response.json()
        
        # Extraer formulario e imágenes
        form = result.get("form", {})
        images = result.get("images", {})
        
        # Guardar imágenes en session state
        st.session_state.images = images
        
        return form

    else:
        st.error("Error en el backend")

    

def apply_updates(form, updates):
    for update in updates:
        keys = update["path"].split(".")
        node = form

        for k in keys[:-1]:
            node = node[k]

        field = node[keys[-1]]

        field["value"] = update['changes']["value"]['to']
        field["status"] = "agent"
        field["confidence"] = update.get("confidence", 0.7)    


def get_selected_sections(form):
    selected = []

    for key, value in form.items():
        if isinstance(value, dict):
            if "meta" in value and value["meta"].get("enabled", False):
                selected.append(key)

    return selected
# Layout
col1, col2 = st.columns([1, 1])

# =========================
# 💬 COLUMNA IZQUIERDA (CHAT)
# =========================
with col1:
    st.title("🎬 Film Assistant")

    # Mostrar chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input usuario
    user_input = st.chat_input("Describe tu película...")

    uploaded_image = st.file_uploader(
        "Sube una imagen de referencia",
        type=["png", "jpg", "jpeg"],
        key="image_uploader"
    )

    if uploaded_image:
        st.image(uploaded_image, caption="Imagen de referencia cargada", use_container_width=True)

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        # Preparar request
        files = {}
        data = {
            "user_id": USER_ID,
            "message": user_input,
            "selected_sections": get_selected_sections(st.session_state.form)  # función para extraer qué secciones del formulario están habilitadas
        }

        if uploaded_image:
            files["image"] = (uploaded_image.name, uploaded_image, uploaded_image.type)

        # Llamada backend
        with st.spinner("Pensando..."):
            response = requests.post(CHAT_PATH, data=data, files=files)

        if response.status_code == 200:
            result = response.json()

            reply = result["reply"]
            st.session_state.state = result["state"]

            st.session_state.messages.append({"role": "assistant", "content": reply})

            with st.chat_message("assistant"):
                st.markdown(reply)

            apply_updates(st.session_state.form, result.get("updates", []))

            # 🔥 NUEVO: recargar formulario desde backend
            updated_form = load_form()
            if updated_form:
                st.session_state.form = updated_form

            # 🔁 Forzar refresco de la UI
            st.rerun()

        else:
            st.error("Error en el backend")

# =========================
# 🧾 COLUMNA DERECHA (FORM STATE)
# =========================
with col2:

    #TODO: hacer que el puto formulario se actualice en tiempo real con los cambios del backend

    st.title("🧾 Formulario de Producción")

    # st.button("🔄 Recargar formulario", on_click=lambda: st.session_state.update(form=load_form()))
    st.button("🗑️ Vacíar formulario", on_click=lambda: st.session_state.update(form=load_form(new=True)))

    # if "form" not in st.session_state:
    print("Cargando formulario desde backend...")
    st.session_state.form = load_form()
    print("Formulario cargado:", st.session_state.form["produccion"]["vision_estrategica"]["publico_objetivo"]["value"]) # type: ignore

    render_field("root", st.session_state.form, [], st.session_state.images)
