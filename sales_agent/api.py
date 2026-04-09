from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from sales_agent.audio import audio_service
from sales_agent.chat_service import chat_service
from sales_agent.config import settings
from sales_agent.ollama_service import ollama_service


router = APIRouter(prefix="/api", tags=["api"])


class TextChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: Optional[str] = None


@router.get("/models")
def get_models() -> dict:
    models = ollama_service.list_models()
    default_model = settings.ollama_model
    return {"models": models, "default_model": default_model}


@router.post("/chat/text")
def post_chat_text(payload: TextChatRequest) -> dict:
    try:
        model_name = (payload.model or settings.ollama_model).strip()
        return chat_service.process_text_message(payload.message, model_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {exc}") from exc


@router.post("/chat/audio")
async def post_chat_audio(
    file: UploadFile = File(...),
    model: Optional[str] = Form(default=None),
) -> dict:
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("El archivo de audio está vacío.")
        model_name = (model or settings.ollama_model).strip()
        return chat_service.process_audio_message(
            file_bytes, file.filename or "audio.webm", model_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {exc}") from exc


@router.get("/audio/{audio_id}")
def get_audio(audio_id: str):
    try:
        path = audio_service.get_audio_file(audio_id)
        return FileResponse(path=path, media_type="audio/wav", filename=f"{audio_id}.wav")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
