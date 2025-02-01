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


# Función de callback para manejar el envío del mensaje
def send_message():
    user_input = st.session_state.user_input.strip()
    if user_input:
        bot_response = deepseek_response(user_input)  # Procesar respuesta
        # Guardar la conversación en el historial
        st.session_state.conversations[st.session_state.username][st.session_state.current_folder].append({
            "user": user_input,
            "bot": bot_response
        })
        # Limpiar el campo de entrada antes de recargar
        st.session_state.user_input = ""
        #st.rerun()
    else:
        st.warning("Por favor ingresa un mensaje")


def deepseek_response(user_message):
    """
    Llama a la API de DeepSeek sin streaming, obteniendo la respuesta completa en una sola solicitud.
    
    Parámetros:
    - user_message (str): Mensaje del usuario que será enviado al modelo.

    Retorna:
    - str: Respuesta generada por el modelo después de limpiar cualquier contenido no deseado.
    """
    system_message = "Eres un asistente útil. Tus respuestas deben ser en español."
    prompt = f"System: {system_message}\nUser: {user_message}\nAssistant:"

    payload = {
        "model": "deepseek-r1:1.5b",  # Ajusta el modelo si es necesario
        "prompt": prompt,
        "stream": False  # Desactiva el streaming para recibir la respuesta completa
    }

    url = "http://localhost:11434/api/generate"

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extraer y limpiar la respuesta
        bot_response = data.get("response", "").strip()

        # Filtrar cualquier contenido entre <think>...</think>
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

