import atexit
import os
import tempfile
from typing import Optional

import gradio as gr
import ollama
import whisper
from TTS.api import TTS


STORE_NAME = "TechShop"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://172.16.0.13:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
TTS_MODEL_NAME = os.getenv("TTS_MODEL", "tts_models/es/css10/vits")
GRADIO_HOST = os.getenv("GRADIO_HOST", "0.0.0.0")
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))

SYSTEM_PROMPT = f"""
Eres un agente de ventas de {STORE_NAME}, una tienda de electrónica.
Tu personalidad es amable, útil, profesional y orientada a cerrar ventas sin ser agresivo.
Responde siempre en español claro y natural.
Habla como asesor comercial experto, destacando beneficios, usos recomendados y relación calidad-precio.
Si el cliente duda entre productos, compara opciones de forma breve y honesta.
No inventes productos ni precios fuera del catálogo.

Catálogo disponible:
- Laptop Pro X: 1200 euros
- Smartphone Y: 800 euros
- Auriculares Z: 150 euros
- Tablet W: 400 euros

Objetivo:
- Entender la necesidad del cliente.
- Recomendar el producto más adecuado.
- Responder dudas sobre precio, ventajas y escenarios de uso.
- Invitar sutilmente a la compra al final cuando tenga sentido.
""".strip()

_whisper_model = None
_tts_model = None
_generated_audio_files: set[str] = set()
_ollama_client = ollama.Client(host=OLLAMA_HOST)


def cleanup_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    _generated_audio_files.discard(path)


def cleanup_generated_files() -> None:
    for path in list(_generated_audio_files):
        cleanup_file(path)


atexit.register(cleanup_generated_files)


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    return _whisper_model


def get_tts_model():
    global _tts_model
    if _tts_model is None:
        _tts_model = TTS(model_name=TTS_MODEL_NAME, progress_bar=False, gpu=False)
    return _tts_model


def transcribe_audio(audio_path: str) -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise FileNotFoundError("No se encontró el archivo de audio proporcionado.")

    model = get_whisper_model()
    result = model.transcribe(audio_path, language="es")
    text = (result or {}).get("text", "").strip()
    if not text:
        raise ValueError("No se pudo transcribir contenido útil del audio.")
    return text


def ask_ollama(user_message: str) -> str:
    try:
        response = _ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
    except Exception as exc:
        raise RuntimeError(
            "No fue posible conectar con Ollama. Verifica que el servicio esté accesible en "
            f"`{OLLAMA_HOST}` y que el modelo `{OLLAMA_MODEL}` exista."
        ) from exc

    content = response.get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama devolvió una respuesta vacía.")
    return content


def synthesize_speech(text: str) -> str:
    tts = get_tts_model()
    tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    try:
        tts.tts_to_file(text=text, file_path=tmp_path)
    except Exception:
        cleanup_file(tmp_path)
        raise

    _generated_audio_files.add(tmp_path)
    return tmp_path


def process_request(
    text_input: str,
    audio_input: Optional[str],
    previous_audio_path: Optional[str],
):
    # El audio tiene prioridad porque suele representar la intención más reciente del usuario.
    cleanup_file(previous_audio_path)

    try:
        if audio_input:
            user_query = transcribe_audio(audio_input)
        else:
            user_query = (text_input or "").strip()

        if not user_query:
            raise ValueError("Escribe una consulta o graba un audio antes de enviar.")

        reply_text = ask_ollama(user_query)
        reply_audio_path = synthesize_speech(reply_text)

        return reply_text, reply_audio_path, reply_audio_path
    except FileNotFoundError as exc:
        return f"Error de archivo: {exc}", None, None
    except ValueError as exc:
        return f"Entrada no válida: {exc}", None, None
    except RuntimeError as exc:
        return f"Error del servicio: {exc}", None, None
    except Exception as exc:
        return f"Error inesperado: {exc}", None, None


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="TechShop Sales Agent") as demo:
        gr.Markdown(
            """
            # TechShop Sales Agent
            Consulta por texto o voz y recibe una respuesta comercial en texto y audio.

            Pasos previos:
            1. Verifica que Ollama esté disponible en la URL configurada
            2. Verifica que el modelo configurado exista en esa instancia
            3. Inicia esta app con `python app.py` o usando Docker

            Configuración actual:
            - OLLAMA_HOST: `{OLLAMA_HOST}`
            - OLLAMA_MODEL: `{OLLAMA_MODEL}`
            """
        )

        previous_audio_state = gr.State(value=None)

        with gr.Row():
            text_input = gr.Textbox(
                label="Escribe tu consulta",
                placeholder="Ejemplo: ¿Qué laptop me recomiendas para trabajo y estudio?",
                lines=4,
            )
            audio_input = gr.Audio(
                sources=["microphone"],
                type="filepath",
                label="O graba tu consulta por voz",
            )

        submit_button = gr.Button("Enviar", variant="primary")

        output_text = gr.Textbox(
            label="Respuesta del agente",
            lines=8,
            interactive=False,
        )
        output_audio = gr.Audio(
            label="Respuesta en audio",
            type="filepath",
            autoplay=True,
          