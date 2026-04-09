import atexit
import json
import logging
import os
import tempfile
from typing import Any, Optional

import gradio as gr
import ollama
import whisper
from TTS.api import TTS

from mcp_server.tools import SalesToolsService


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("techshop.app")

STORE_NAME = "TechShop"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://172.16.0.13:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
TTS_MODEL_NAME = os.getenv("TTS_MODEL", "tts_models/es/css10/vits")
GRADIO_HOST = os.getenv("GRADIO_HOST", "0.0.0.0")
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
MAX_TOOL_ROUNDS = int(os.getenv("OLLAMA_MAX_TOOL_ROUNDS", "4"))

SYSTEM_PROMPT = f"""
Eres un agente de ventas de {STORE_NAME}, una tienda de electrónica.
Tu personalidad es amable, útil, profesional y orientada a cerrar ventas sin ser agresivo.
Responde siempre en español claro y natural.
Habla como asesor comercial experto, destacando beneficios, usos recomendados y relación calidad-precio.
Si el cliente duda entre productos, compara opciones de forma breve y honesta.
No inventes productos ni precios fuera del catálogo.

Cuando el usuario pida datos concretos de clientes, pedidos o inventario, usa las herramientas disponibles.
No inventes IDs, stock, pedidos ni historiales.
Si una herramienta no devuelve resultados, dilo con claridad y ofrece siguiente paso.

Catálogo base:
- Laptop Pro X: 1200 euros
- Smartphone Y: 800 euros
- Auriculares Z: 150 euros
- Tablet W: 400 euros
""".strip()

OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_cliente",
            "description": "Busca clientes por nombre y devuelve coincidencias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "description": "Nombre completo o parcial del cliente.",
                    }
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_cliente",
            "description": "Crea un cliente nuevo cuando no exista en la base de datos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "email": {"type": "string"},
                    "telefono": {"type": "string"},
                },
                "required": ["nombre", "email", "telefono"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_productos",
            "description": "Lista productos activos con precio y stock disponible.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_pedido",
            "description": "Crea un pedido para un cliente existente con productos e inventario válido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nombre": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "producto_id": {"type": "integer"},
                                "cantidad": {"type": "integer"},
                            },
                            "required": ["producto_id", "cantidad"],
                        },
                    },
                },
                "required": ["cliente_nombre", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_pedidos_cliente",
            "description": "Devuelve el historial de pedidos de un cliente.",
            "parameters": {
                "type": "object",
                "properties": {"nombre": {"type": "string"}},
                "required": ["nombre"],
            },
        },
    },
]

_whisper_model = None
_tts_model = None
_generated_audio_files: set[str] = set()
_ollama_client = ollama.Client(host=OLLAMA_HOST)
_sales_tools = SalesToolsService()


def cleanup_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.warning("No se pudo eliminar el archivo temporal: %s", path)
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


def normalize_arguments(raw_arguments: Any) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        raw_arguments = raw_arguments.strip()
        if not raw_arguments:
            return {}
        return json.loads(raw_arguments)
    raise ValueError("Formato de argumentos de herramienta no soportado.")


def list_ollama_models() -> list[str]:
    try:
        response = _ollama_client.list()
        models = response.get("models", [])
        names = [model.get("model", "").strip() for model in models if model.get("model")]
        return sorted(set(name for name in names if name))
    except Exception:
        logger.warning("No se pudo obtener la lista de modelos de Ollama.", exc_info=True)
        return []


def refresh_model_choices(current_value: Optional[str]):
    models = list_ollama_models()
    selected = (current_value or OLLAMA_MODEL).strip() or OLLAMA_MODEL
    if selected not in models:
        models = [selected, *models] if selected else models
    info_text = (
        "Modelos cargados desde Ollama."
        if models
        else "No se pudo cargar la lista desde Ollama. Puedes escribir el modelo manualmente."
    )
    return gr.Dropdown(choices=models, value=selected, allow_custom_value=True), info_text


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "buscar_cliente": lambda args: _sales_tools.buscar_cliente(args["nombre"]),
        "crear_cliente": lambda args: _sales_tools.crear_cliente(
            args["nombre"], args["email"], args["telefono"]
        ),
        "listar_productos": lambda args: _sales_tools.listar_productos(),
        "crear_pedido": lambda args: _sales_tools.crear_pedido(
            args["cliente_nombre"], args["items"]
        ),
        "obtener_pedidos_cliente": lambda args: _sales_tools.obtener_pedidos_cliente(
            args["nombre"]
        ),
    }
    if tool_name not in handlers:
        raise ValueError(f"Herramienta no soportada: {tool_name}")
    return handlers[tool_name](arguments)


def ask_ollama(user_message: str, model_name: str) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = _ollama_client.chat(
                model=model_name,
                messages=messages,
                tools=OLLAMA_TOOLS,
            )
            message = response.get("message", {})
            tool_calls = message.get("tool_calls") or []
            messages.append(message)

            if not tool_calls:
                content = (message.get("content") or "").strip()
                if not content:
                    raise RuntimeError("Ollama devolvió una respuesta vacía.")
                return content

            for tool_call in tool_calls:
                function_block = tool_call.get("function", {})
                tool_name = function_block.get("name", "")
                arguments = normalize_arguments(function_block.get("arguments"))
                logger.info("Ejecutando herramienta %s con args=%s", tool_name, arguments)

                try:
                    tool_result = execute_tool(tool_name, arguments)
                except Exception as exc:
                    logger.exception("Error ejecutando herramienta %s", tool_name)
                    tool_result = {"ok": False, "error": str(exc)}

                messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        raise RuntimeError("El modelo excedió el máximo de rondas de herramientas.")
    except Exception as exc:
        raise RuntimeError(
            "No fue posible conectar con Ollama o completar la conversación con herramientas. "
            f"Verifica que el servicio esté accesible en `{OLLAMA_HOST}` y que el modelo "
            f"`{model_name}` exista."
        ) from exc


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
    selected_model: str,
    previous_audio_path: Optional[str],
):
    cleanup_file(previous_audio_path)

    try:
        if audio_input:
            user_query = transcribe_audio(audio_input)
        else:
            user_query = (text_input or "").strip()

        if not user_query:
            raise ValueError("Escribe una consulta o graba un audio antes de enviar.")

        model_name = (selected_model or OLLAMA_MODEL).strip()
        if not model_name:
            raise ValueError("Selecciona o escribe un modelo de Ollama.")

        reply_text = ask_ollama(user_query, model_name)
        reply_audio_path = synthesize_speech(reply_text)

        return reply_text, reply_audio_path, reply_audio_path
    except FileNotFoundError as exc:
        return f"Error de archivo: {exc}", None, None
    except ValueError as exc:
        return f"Entrada no válida: {exc}", None, None
    except RuntimeError as exc:
        return f"Error del servicio: {exc}", None, None
    except Exception as exc:
        logger.exception("Fallo inesperado en process_request")
        return f"Error inesperado: {exc}", None, None


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="TechShop Sales Agent") as demo:
        available_models = list_ollama_models()
        default_model = OLLAMA_MODEL if OLLAMA_MODEL else (available_models[0] if available_models else "")
        if default_model and default_model not in available_models:
            available_models = [default_model, *available_models]

        gr.Markdown(
            f"""
            # TechShop Sales Agent
            Consulta por texto o voz y recibe una respuesta comercial en texto y audio.

            La app puede consultar datos de clientes, productos y pedidos a través de herramientas controladas.

            Configuración actual:
            - OLLAMA_HOST: `{OLLAMA_HOST}`
            - Modelo por defecto: `{OLLAMA_MODEL}`
            """
        )

        previous_audio_state = gr.State(value=None)
        model_status = gr.Markdown(
            "Modelos cargados desde Ollama."
            if available_models
            else "No se pudo cargar la lista desde Ollama. Puedes escribir el modelo manualmente."
        )

        with gr.Row():
            model_selector = gr.Dropdown(
                choices=available_models,
                value=default_model,
                label="Modelo Ollama",
                allow_custom_value=True,
                interactive=True,
            )
            refresh_models_button = gr.Button("Actualizar modelos")

        with gr.Row():
            text_input = gr.Textbox(
                label="Escribe tu consulta",
                placeholder="Ejemplo: crea un pedido para Ana con 2 auriculares y 1 tablet",
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
            lines=10,
            interactive=False,
        )
        output_audio = gr.Audio(
            label="Respuesta en audio",
            type="filepath",
            autoplay=True,
            interactive=False,
        )

        submit_button.click(
            fn=process_request,
            inputs=[text_input, audio_input, model_selector, previous_audio_state],
            outputs=[output_text, output_audio, previous_audio_state],
        )
        refresh_models_button.click(
            fn=refresh_model_choices,
            inputs=[model_selector],
            outputs=[model_selector, model_status],
        )

    return demo


if __name__ == "__main__":
    app = build_interface()
    app.launch(server_name=GRADIO_HOST, server_port=GRADIO_PORT)
