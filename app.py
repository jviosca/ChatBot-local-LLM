import streamlit as st
from aux_functions import (
    init_session_state,
    deepseek_response,
    deepseek_response_streaming,
    login_user,
    create_folder,
    get_user_folders,
    send_message,
    load_conversations,
    update_conversations
)

# Inicializar variables de sesión
init_session_state()

# Cargar conversaciones desde JSON comprimido
load_conversations() 

# Si se ha marcado `should_rerun`, hacer `st.rerun()` fuera de los callbacks
if "should_rerun" in st.session_state and st.session_state.should_rerun:
    st.session_state.should_rerun = False  # 🔹 Restablecemos el estado
    st.rerun()  # 🔹 Ahora el rerun se ejecuta en un lugar válido

# Asegurar que las claves esenciales existen en session_state
if "username" not in st.session_state:
    st.session_state.username = None
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "current_folder" not in st.session_state:
    st.session_state.current_folder = "General"
if "current_conversation" not in st.session_state:
    st.session_state.current_conversation = "Conversación 1"
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

    # Crear estructura si el usuario aún no tiene conversaciones
    if st.session_state.username not in st.session_state.conversations:
        st.session_state.conversations[st.session_state.username] = {}

    user_conversations = st.session_state.conversations[st.session_state.username]

    # Asegurar que siempre exista la carpeta "General"
    if "General" not in user_conversations:
        user_conversations["General"] = {}

    # 🔥 **CORRECCIÓN: Convertimos listas en diccionarios**
    for folder in list(user_conversations.keys()):
        if isinstance(user_conversations[folder], list):
            user_conversations[folder] = {"Conversación 1": user_conversations[folder]}
        if "Conversación 1" not in user_conversations[folder]:  # Siempre debe haber al menos 1 conversación
            user_conversations[folder]["Conversación 1"] = []

    # Obtener carpetas del usuario
    user_folders = list(user_conversations.keys())
    
    # Construir lista de opciones con carpetas arriba y opciones abajo
    folder_options = user_folders + ["    ⬇⬇ Gestionar ⬇⬇", "Nueva Carpeta", "Renombrar Carpeta"]

    # Selección de carpeta (por defecto, la última usada o "General") 
    selected_folder = st.sidebar.selectbox(
        "Selecciona una carpeta",
        folder_options,
        index=folder_options.index(st.session_state.current_folder) if st.session_state.current_folder in user_folders else 0
    )

    # Crear una nueva carpeta
    if selected_folder == "Nueva Carpeta":
        new_folder = st.sidebar.text_input("Nombre de la nueva carpeta")
        if st.sidebar.button("Crear carpeta") and new_folder.strip():
            if new_folder not in user_conversations:
                user_conversations[new_folder] = {"Conversación 1": []}
                st.session_state.current_folder = new_folder
                st.session_state.current_conversation = "Conversación 1"
                st.sidebar.success(f"Carpeta '{new_folder}' creada")
                update_conversations()  # Guardar los cambios
                st.rerun()
            else:
                st.sidebar.error("La carpeta ya existe")

    # Renombrar una carpeta existente
    elif selected_folder == "Renombrar Carpeta":
        folder_to_rename = st.sidebar.selectbox("Selecciona carpeta a renombrar", user_folders)
        new_folder_name = st.sidebar.text_input(f"Nuevo nombre para '{folder_to_rename}'")

        if st.sidebar.button("Guardar nuevo nombre"):
            if new_folder_name.strip() and new_folder_name != folder_to_rename:
                if new_folder_name not in user_conversations:
                    # Mover contenido de la carpeta antigua a la nueva
                    user_conversations[new_folder_name] = user_conversations.pop(folder_to_rename)

                    # Si la carpeta renombrada era "General", crear una nueva carpeta "General" vacía
                    if folder_to_rename == "General":
                        user_conversations["General"] = {"Conversación 1": []}  # Mantener estructura de inicio
                        st.session_state.general_renamed = True  # Guardar aviso en session_state

                    # Actualizar la carpeta actual en la sesión
                    st.session_state.current_folder = new_folder_name
                    st.sidebar.success(f"Carpeta renombrada a '{new_folder_name}'")

                    update_conversations()  # Guarda los cambios
                    st.rerun()
                else:
                    st.sidebar.error("Ese nombre ya existe, elige otro")
            else:
                st.sidebar.error("Debes ingresar un nombre válido")
                
    # Si el usuario selecciona una carpeta válida, actualizar la carpeta actual
    elif selected_folder != "    ⬇⬇ Gestionar ⬇⬇":
        st.session_state.current_folder = selected_folder


    # Mostrar aviso después del rerun si se renombró "General"
    if "general_renamed" in st.session_state and st.session_state.general_renamed:
        st.sidebar.warning("La carpeta 'General' ha sido renombrada, pero se ha creado una nueva vacía.")
        st.session_state.general_renamed = False  # Resetear el mensaje


    # Obtener la lista de conversaciones en la carpeta actual
    current_folder_conversations = user_conversations[st.session_state.current_folder]
    conversation_list = list(current_folder_conversations.keys())

    # Construir la lista de opciones con conversaciones arriba y opciones de gestión abajo
    conversation_options = conversation_list + ["    ⬇⬇ Gestionar ⬇⬇", "Nueva Conversación", "Renombrar Conversación"]

    # Selección de conversación o acción especial
    selected_conversation = st.sidebar.selectbox(
        "Selecciona una conversación",
        conversation_options,
        index=conversation_options.index(st.session_state.current_conversation) if st.session_state.current_conversation in conversation_list else 0
    )

    # Manejar la opción seleccionada
    if selected_conversation == "Nueva Conversación":
        new_conversation_name = st.sidebar.text_input("Nombre de la nueva conversación")
        if st.sidebar.button("Crear Conversación") and new_conversation_name.strip():
            if new_conversation_name not in current_folder_conversations:
                current_folder_conversations[new_conversation_name] = []
                st.session_state.current_conversation = new_conversation_name
                st.sidebar.success(f"Conversación '{new_conversation_name}' creada")
                update_conversations()  # Guarda los cambios
                st.rerun()
            else:
                st.sidebar.error("Ese nombre ya existe, elige otro")

    elif selected_conversation == "Renombrar Conversación":
        conversation_to_rename = st.sidebar.selectbox("Selecciona conversación a renombrar", conversation_list, key="rename_convo_select")
        new_conversation_name = st.sidebar.text_input(f"Nuevo nombre para '{conversation_to_rename}'")

        if st.sidebar.button("Renombrar Conversación"):
            if new_conversation_name.strip() and new_conversation_name != conversation_to_rename:
                if new_conversation_name not in current_folder_conversations:
                    # Mover el contenido de la conversación antigua a la nueva
                    current_folder_conversations[new_conversation_name] = current_folder_conversations.pop(conversation_to_rename)

                    # Actualizar la conversación actual en la sesión
                    st.session_state.current_conversation = new_conversation_name
                    st.sidebar.success(f"Conversación renombrada a '{new_conversation_name}'")

                    update_conversations()  # Guarda los cambios
                    st.rerun()
                else:
                    st.sidebar.error("Ese nombre ya existe, elige otro")
            else:
                st.sidebar.error("Debes ingresar un nombre válido")

    # Si el usuario selecciona una conversación válida, actualizar la conversación actual
    elif selected_conversation != "    ⬇⬇ Gestionar ⬇⬇":
        st.session_state.current_conversation = selected_conversation


    # Botón de cerrar sesión
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.current_folder = "General"
        st.session_state.current_conversation = "Conversación 1"
        st.rerun()

# Título principal de la aplicación
st.title("Chatbot con DeepSeek")

if st.session_state.logged_in:
    st.subheader(f"📁 Carpeta: {st.session_state.current_folder} | 💬 {st.session_state.current_conversation}")

    # Obtener mensajes de la conversación seleccionada
    conversation = st.session_state.conversations[st.session_state.username][st.session_state.current_folder].get(
        st.session_state.current_conversation, []
    )

    # Mostrar historial de conversación
    if conversation:
        for entry in conversation:
            st.markdown(f"**Tú:** {entry['user']}")
            st.markdown(f"**Chatbot:** {entry['bot']}")
            st.markdown("---")
    else:
        st.info("No hay mensajes en esta conversación aún.")

    # Entrada de mensaje del usuario con `on_change`
    st.text_input("Envía un mensaje", key="user_input", on_change=send_message)
else:
    st.warning("Por favor, inicia sesión para continuar.")
