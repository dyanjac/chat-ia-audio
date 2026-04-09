import logging
from typing import Optional

import gradio as gr

from sales_agent.audio import audio_service
from sales_agent.config import settings
from sales_agent.ollama_service import ollama_service


logger = logging.getLogger("techshop.ui")


def process_request(
    text_input: str,
    audio_input: Optional[str],
    selected_model: str,
    previous_audio_path: Optional[str],
):
    audio_service.cleanup_file(previous_audio_path)

    try:
        if audio_input:
            user_query = audio_service.transcribe_audio(audio_input)
        else:
            user_query = (text_input or "").strip()

        if not user_query:
            raise ValueError("Escribe una consulta o graba un audio antes de enviar.")

        model_name = (selected_model or settings.ollama_model).strip()
        if not model_name:
            raise ValueError("Selecciona o escribe un modelo de Ollama.")

        reply_text = ollama_service.chat(user_query, model_name)
        reply_audio_path = audio_service.synthesize_speech(reply_text)
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


def refresh_model_choices(current_value: Optional[str]):
    models, selected, info_text = ollama_service.refresh_model_choices(current_value)
    return gr.Dropdown(choices=models, value=selected, allow_custom_value=True), info_text


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="TechShop Sales Agent") as demo:
        available_models = ollama_service.list_models()
        default_model = (
            settings.ollama_model
            if settings.ollama_model
            else (available_models[0] if available_models else "")
        )
        if default_model and default_model not in available_models:
            available_models = [default_model, *available_models]

        gr.Markdown(
            f"""
            # TechShop Sales Agent
            Consulta por texto o voz y recibe una respuesta comercial en texto y audio.

            La app puede consultar datos de clientes, productos y pedidos a través de herramientas controladas.

            Configuración actual:
            - OLLAMA_HOST: `{settings.ollama_host}`
            - Modelo por defecto: `{settings.ollama_model}`
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
