import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp_server.tools import SalesToolsService
from sales_agent.audio import audio_service
from sales_agent.conversation_service import conversation_service
from sales_agent.ollama_service import ollama_service


logger = logging.getLogger("techshop.chat")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatApplicationService:
    def __init__(self) -> None:
        self._sales_tools = SalesToolsService()

    def _extract_registration_data(self, message: str) -> Optional[dict[str, str]]:
        text = (message or "").strip()
        if not text:
            return None

        email_match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        phone_match = re.search(r"(\+?\d[\d\s-]{7,}\d)", text)
        if not email_match or not phone_match:
            return None

        email = email_match.group(1).strip().lower()
        telefono = re.sub(r"[^\d+]", "", phone_match.group(1))

        name_patterns = [
            r"mi nombre es\s+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+?)(?:,|\.|correo|email|telefono|teléfono|$)",
            r"me llamo\s+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+?)(?:,|\.|correo|email|telefono|teléfono|$)",
            r"estos son mis datos\s+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+?)(?:,|\.|correo|email|telefono|teléfono|$)",
        ]

        nombre = ""
        for pattern in name_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                nombre = match.group(1).strip(" ,.")
                break

        if not nombre:
            stripped = text.replace(email_match.group(1), " ").replace(phone_match.group(1), " ")
            stripped = re.sub(
                r"\b(mi nombre es|me llamo|estos son mis datos|correo es|correo|email es|email|telefono es|telefono|teléfono es|teléfono)\b",
                " ",
                stripped,
                flags=re.IGNORECASE,
            )
            stripped = re.sub(r"[\s,;:]+", " ", stripped).strip(" ,.")
            nombre = stripped

        nombre = re.sub(r"\s{2,}", " ", nombre).strip()
        if len(nombre) < 3:
            return None

        return {"nombre": nombre, "email": email, "telefono": telefono}

    def _ensure_client_registration(
        self,
        message: str,
        session_id: str,
        cliente_id: Optional[int],
    ) -> tuple[Optional[int], Optional[str]]:
        if cliente_id:
            return cliente_id, None

        registration_data = self._extract_registration_data(message)
        if not registration_data:
            return None, None

        logger.info("Intentando registrar cliente desde mensaje para session_id=%s", session_id)
        result = self._sales_tools.crear_cliente(
            registration_data["nombre"],
            registration_data["email"],
            registration_data["telefono"],
        )
        cliente = result.get("cliente") or {}
        resolved_cliente_id = cliente.get("id")
        if not resolved_cliente_id:
            return None, None

        system_note = (
            f"Cliente identificado para esta sesión: nombre={cliente.get('nombre')}, "
            f"email={cliente.get('email')}, telefono={cliente.get('telefono')}, "
            f"cliente_id={resolved_cliente_id}. "
            "Si el usuario estaba intentando comprar, continúa el flujo comercial sin volver a pedir estos datos."
        )
        return int(resolved_cliente_id), system_note

    def process_text_message(
        self,
        message: str,
        model_name: str,
        session_id: Optional[str] = None,
        cliente_id: Optional[int] = None,
    ) -> dict:
        normalized_message = conversation_service.validate_message(message)
        normalized_model = (model_name or "").strip()
        normalized_session = conversation_service.ensure_session_id(session_id)

        if not normalized_model:
            raise ValueError("`model` no puede estar vacío.")

        resolved_cliente_id, registration_note = self._ensure_client_registration(
            normalized_message,
            normalized_session,
            cliente_id,
        )
        effective_cliente_id = resolved_cliente_id or cliente_id

        user_row = conversation_service.save_message(
            normalized_session, effective_cliente_id, "user", normalized_message
        )
        context_messages = conversation_service.build_context(normalized_session)
        prior_messages = context_messages[:-1] if context_messages else []
        if registration_note:
            prior_messages.append({"role": "system", "content": registration_note})
        reply_text = ollama_service.chat(
            normalized_message,
            normalized_model,
            prior_messages=prior_messages or None,
        )
        assistant_row = conversation_service.save_message(
            normalized_session, effective_cliente_id, "assistant", reply_text
        )
        audio_path = audio_service.synthesize_speech(reply_text)
        audio_id = audio_service.register_audio_file(audio_path)

        return {
            "session_id": normalized_session,
            "cliente_id": effective_cliente_id,
            "model": normalized_model,
            "user_message": {
                "role": "user",
                "content": normalized_message,
                "created_at": (
                    user_row.get("fecha").isoformat()
                    if user_row.get("fecha")
                    else utc_now_iso()
                ),
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_text,
                "audio_id": audio_id,
                "audio_url": f"/api/audio/{audio_id}",
                "created_at": (
                    assistant_row.get("fecha").isoformat()
                    if assistant_row.get("fecha")
                    else utc_now_iso()
                ),
            },
        }

    def process_audio_message(
        self,
        file_bytes: bytes,
        filename: str,
        model_name: str,
        session_id: Optional[str] = None,
        cliente_id: Optional[int] = None,
    ) -> dict:
        suffix = Path(filename or "audio.webm").suffix or ".webm"
        temp_input_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                temp_input_path = tmp_file.name

            transcription = audio_service.transcribe_audio(temp_input_path)
            result = self.process_text_message(
                transcription,
                model_name,
                session_id=session_id,
                cliente_id=cliente_id,
            )
            result["transcription"] = transcription
            return result
        finally:
            if temp_input_path:
                audio_service.cleanup_file(temp_input_path)


chat_service = ChatApplicationService()
