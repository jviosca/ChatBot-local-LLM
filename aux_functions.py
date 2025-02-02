import streamlit as st
import requests
import json
import sys
import re
import time

def init_session_state():
    """
    Inicializa las variables de sesión necesarias.
    """
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "conversations" not in st.session_state:
        # Estructura: { usuario: { carpeta: [ {"user": ..., "bot": ...}, ... ] } }
        st.session_state.conversations = {}
    if "current_folder" not in st.session_state:
        st.session_state.current_folder = "General"

def process_token(token, in_think):
    """
    Procesa un token, eliminando (no mostrando) el contenido que se encuentre entre
    las etiquetas <think> y </think>. Si está dentro de <think>, activa el estado de "pensando...".
    
    Retorna una tupla: (texto_a_mostrar, nuevo_estado_in_think).
    """
    text_to_display = ""
    # Si ya estamos dentro de un bloque <think>, buscamos el cierre
    if in_think:
        if "</think>" in token:
            parts = token.split("</think>", 1)
            in_think = False
            text_to_display = parts[1]  # Muestra lo que venga después del cierre
        else:
            text_to_display = ""  # No mostrar nada mientras esté en <think>
    else:
        if "<think>" in token:
            parts = token.split("<think>", 1)
            text_to_display = parts[0]  # Muestra lo anterior a la etiqueta
            # Verificar si el cierre está en el mismo token
            if "</think>" in parts[1]:
                inner_parts = parts[1].split("</think>", 1)
                text_to_display += inner_parts[1]
            else:
                in_think = True  # Se inicia un bloque <think>
                text_to_display = ""  # No mostrar contenido dentro de <think>
        else:
            text_to_display = token
    return text_to_display, in_think

def deepseek_response_streaming(user_message):
    """
    Función que simula la respuesta del LLM integrando una llamada a la API de Ollama.
    Durante el streaming, se oculta el contenido entre <think> y </think>, y se muestra 
    "⏳ Pensando..." una sola vez mientras el modelo está procesando.
    
    Nota: Asegúrate de que Ollama está ejecutándose en "http://localhost:11434".
    """
    # Mensaje del sistema
    system_message = "Eres un asistente útil. Tus respuestas deben ser en español."
    
    # Construir el prompt combinando el system message y el mensaje del usuario
    prompt = f"System: {system_message}\nUser: {user_message}\nAssistant:"

    # Construir el payload para la API de Ollama
    payload = {
        "model": "deepseek-r1:1.5b",
        "prompt": prompt,
        "stream": True
    }

    url = "http://localhost:11434/api/generate"
    
    full_response = ""   # Acumula la respuesta completa (con todo el contenido)
    display_text = ""    # Acumula solo el texto a mostrar (filtrado)
    in_think = False     # Bandera para saber si estamos dentro de un bloque <think>
    think_shown = False  # Se asegura de que "⏳ Pensando..." solo se muestre una vez
    
    thinking_placeholder = st.empty()  # Placeholder para "pensando..."
    response_placeholder = st.empty()  # Placeholder para la respuesta final

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("response")
                        if token:
                            full_response += token
                            
                            # Procesa el token para filtrar lo que esté entre <think> y </think>
                            processed, new_in_think = process_token(token, in_think)
                            
                            # Si entramos en un bloque <think>, mostramos "⏳ Pensando..." solo una vez
                            if not think_shown and not in_think and new_in_think:
                                thinking_placeholder.text("⏳ Pensando...")
                                think_shown = True  # Evita que se muestre más de una vez
                            
                            # Si ya terminamos el bloque <think>, eliminamos el mensaje de "pensando..."
                            if in_think and not new_in_think:
                                thinking_placeholder.text("")  # Borrar "pensando..."
                            
                            in_think = new_in_think  # Actualizar estado

                            # Acumular solo el texto procesado
                            display_text += processed
                            # Actualizar el placeholder con el texto filtrado
                            response_placeholder.text(display_text)
                            
                            time.sleep(0.05)  # Pequeño delay para mejorar la experiencia de streaming
                    except json.JSONDecodeError:
                        response_placeholder.text("No se pudo decodificar la línea: " + line)
    except requests.exceptions.RequestException as e:
        response_placeholder.text("Error en la solicitud: " + str(e))
    response_placeholder.text("")
    return display_text


def send_message(stream=False):
    """
    Envía el mensaje del usuario al chatbot y almacena la respuesta en el historial de la conversación.
    """
    user_input = st.session_state.user_input.strip()
    if user_input:
        if stream:
            bot_response = deepseek_response_streaming(user_input)
        else:
            bot_response = deepseek_response(user_input)

        # Obtener el usuario, carpeta y conversación actual
        username = st.session_state.username
        folder = st.session_state.current_folder
        conversation = st.session_state.current_conversation

        # Guardar el mensaje en la conversación seleccionada
        st.session_state.conversations[username][folder][conversation].append({
            "user": user_input,
            "bot": bot_response
        })

        # 🔹 Guardar historial comprimido y actualizar la interfaz
        update_conversations()

        # Limpiar la entrada
        st.session_state.user_input = ""


def deepseek_response(user_message):
    """
    Llama a la API de DeepSeek sin streaming, enviando todo el historial de la conversación.
    """
    username = st.session_state.username
    folder = st.session_state.current_folder
    conversation = st.session_state.current_conversation

    # Recuperar el historial de mensajes de la conversación actual
    conversation_history = st.session_state.conversations[username][folder][conversation]

    # Construcción de la lista de mensajes en formato esperado por la API
    messages = [{"role": "system", "content": "Eres un asistente útil. Tus respuestas deben ser en español."}]
    for msg in conversation_history:
        messages.append({"role": "user", "content": msg["user"]})
        messages.append({"role": "assistant", "content": msg["bot"]})

    # Agregar el nuevo mensaje del usuario
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": "deepseek-r1:1.5b",
        "messages": messages,
        "stream": False  # Desactiva el streaming para recibir la respuesta completa
    }

    url = "http://localhost:11434/api/chat"

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extraer la respuesta del asistente
        bot_response = data.get("message", {}).get("content", "").strip()

        # Filtrar contenido no deseado (como <think>...</think>)
        bot_response = re.sub(r'<think>.*?</think>', '', bot_response, flags=re.DOTALL).strip()

        return bot_response

    except requests.exceptions.RequestException as e:
        return f"Error en la solicitud: {str(e)}"



def login_user(username):
    """
    Registra el usuario en el estado de sesión y crea la estructura de conversaciones.
    """
    st.session_state.logged_in = True
    st.session_state.username = username
    if username not in st.session_state.conversations:
        st.session_state.conversations[username] = {"General": []}
    st.session_state.current_folder = "General"

def create_folder(username, folder_name):
    """
    Crea una nueva carpeta para el usuario si no existe.
    Retorna True si se crea la carpeta, o False en caso contrario.
    """
    if folder_name not in st.session_state.conversations[username]:
        st.session_state.conversations[username][folder_name] = []
        st.session_state.current_folder = folder_name
        return True
    return False

def get_user_folders(username):
    """
    Retorna la lista de carpetas existentes para el usuario.
    """
    return list(st.session_state.conversations[username].keys())


def save_conversations():
    """
    Guarda las conversaciones en formato JSON comprimido en session_state.
    """
    st.session_state.conversations_json = json.dumps(
        st.session_state.conversations, separators=(',', ':')  # Sin espacios innecesarios
    )

def load_conversations():
    """
    Carga las conversaciones desde JSON comprimido.
    """
    if "conversations_json" in st.session_state and st.session_state.conversations_json:
        try:
            st.session_state.conversations = json.loads(st.session_state.conversations_json)
        except json.JSONDecodeError:
            st.session_state.conversations = {}  # En caso de error, inicializa vacío

def update_conversations():
    """
    Marca el estado para una actualización en la siguiente iteración del script.
    """
    save_conversations()
    st.session_state.should_rerun = True  # 🔹 Indicamos que se debe hacer un `rerun`


