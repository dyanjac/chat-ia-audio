import atexit
import logging
import os
import tempfile
from typing import Optional

import whisper
from TTS.api import TTS

from sales_agent.config import settings


logger = logging.getLogger("techshop.audio")


class AudioService:
    def __init__(self) -> None:
        self._whisper_model = None
        self._tts_model = None
        self._generated_audio_files: set[str] = set()
        atexit.register(self.cleanup_generated_files)

    def cleanup_file(self, path: Optional[str]) -> None:
        if not path:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            logger.warning("No se pudo eliminar el archivo temporal: %s", path)
        self._generated_audio_files.discard(path)

    def cleanup_generated_files(self) -> None:
        for path in list(self._generated_audio_files):
            self.cleanup_file(path)

    def get_whisper_model(self):
        if self._whisper_model is None:
            self._whisper_model = whisper.load_model(settings.whisper_model)
        return self._whisper_model

    def get_tts_model(self):
        if self._tts_model is None:
            self._tts_model = TTS(model_name=settings.tts_model, progress_bar=False, gpu=False)
        return self._tts_model

    def transcribe_audio(self, audio_path: str) -> str:
        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError("No se encontró el archivo de audio proporcionado.")

        model = self.get_whisper_model()
        result = model.transcribe(audio_path, language="es")
        text = (result or {}).get("text", "").strip()
        if not text:
            raise ValueError("No se pudo transcribir contenido útil del audio.")
        return text

    def synthesize_speech(self, text: str) -> str:
        tts = self.get_tts_model()
        tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        try:
            tts.tts_to_file(text=text, file_path=tmp_path)
        except Exception:
            self.cleanup_file(tmp_path)
            raise

        self._generated_audio_files.add(tmp_path)
        return tmp_path


audio_service = AudioService()
