import streamlit as st
from aux_functions import (
    init_session_state,
    deepseek_response,
    deepseek_response_streaming,
    login_user,
    create_folder,
    get_user_folders,
    send_message
)

# Inicializar variables de sesión
init_session_state()

# Asegurar que las claves esenciales existen en session_state
if "username" not in st.session_state:
    st.session_state.username = None
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "current_folder" not in st.session_state:
    st.session_state.current_folder = "General"
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# Sidebar: Login y gestión de carpetas
if not st.session_state.logged_in:
    st.sidebar.title("Login")
    username = st.sidebar.text_input("Usuario")
    if st.sidebar.button("Ingresar"):
        if username:
            login_user(username)
            st.sidebar.success(f"Bienvenido, {username}")
            st.rerun()
        else:
            st.sidebar.error("Debes ingresar un usuario")
else:
    st.sidebar.title("Gestión de Carpetas")
    
    user_folders = get_user_folders(st.session_state.username)
    if "General" not in user_folders:
        user_folders.append("General")

    current_folder = st.sidebar.selectbox(
        "Selecciona carpeta",
        user_folders,
        index=user_folders.index(st.session_state.current_folder)
        if st.session_state.current_folder in user_folders else 0
    )
    st.session_state.current_folder = current_folder

    new_folder = st.sidebar.text_input("Nueva carpeta")
    if st.sidebar.button("Crear carpeta"):
        if new_folder.strip():
            if create_folder(st.session_state.username, new_folder):
                st.sidebar.success(f"Carpeta '{new_folder}' creada")
                st.rerun()
            else:
                st.sidebar.error("La carpeta ya existe")
        else:
            st.sidebar.error("Ingresa un nombre válido")
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.current_folder = "General"
        st.rerun()

# Título principal de la aplicación
st.title("Chatbot con DeepSeek-R1")

if st.session_state.logged_in:
    st.subheader(f"Conversación - Carpeta: {st.session_state.current_folder}")

    # Asegurar estructura de conversaciones del usuario
    if st.session_state.username not in st.session_state.conversations:
        st.session_state.conversations[st.session_state.username] = {"General": []}
    
    if st.session_state.current_folder not in st.session_state.conversations[st.session_state.username]:
        st.session_state.conversations[st.session_state.username][st.session_state.current_folder] = []

    # Mostrar historial de conversaciones
    conversation = st.session_state.conversations[st.session_state.username][st.session_state.current_folder]
    if conversation:
        for entry in conversation:
            st.markdown(f"**Tú:** {entry['user']}")
            st.markdown(f"**Chatbot:** {entry['bot']}")
            st.markdown("---")
    else:
        st.info("No hay mensajes en esta carpeta aún.")



    # Entrada de mensaje del usuario con `on_change`
    st.text_input("Envía un mensaje", key="user_input", on_change=send_message)

else:
    st.warning("Por favor, inicia sesión para continuar.")
