import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sales_agent.audio import audio_service
from sales_agent.ollama_service import ollama_service


logger = logging.getLogger("techshop.chat")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatApplicationService:
    def process_text_message(self, message: str, model_name: str) -> dict:
        normalized_message = (message or "").strip()
        normalized_model = (model_name or "").strip()

        if not normalized_message:
            raise ValueError("`message` no puede estar vacío.")
        if not normalized_model:
            raise ValueError("`model` no puede estar vacío.")

        reply_text = ollama_service.chat(normalized_message, normalized_model)
        audio_path = audio_service.synthesize_speech(reply_text)
        audio_id = audio_service.register_audio_file(audio_path)

        return {
            "model": normalized_model,
            "user_message": {
                "role": "user",
                "content": normalized_message,
                "created_at": utc_now_iso(),
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_text,
                "audio_id": audio_id,
                "audio_url": f"/api/audio/{audio_id}",
                "created_at": utc_now_iso(),
            },
        }

    def process_audio_message(self, file_bytes: bytes, filename: str, model_name: str) -> dict:
        suffix = Path(filename or "audio.webm").suffix or ".webm"
        temp_input_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                temp_input_path = tmp_file.name

            transcription = audio_service.transcribe_audio(temp_input_path)
            result = self.process_text_message(transcription, model_name)
            result["transcription"] = transcription
            return result
        finally:
            if temp_input_path:
                audio_service.cleanup_file(temp_input_path)


chat_service = ChatApplicationService()
