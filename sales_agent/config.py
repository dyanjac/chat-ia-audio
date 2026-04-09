import os
from dataclasses import dataclass


def parse_csv_env(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    store_name: str = "TechShop"
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://172.16.0.13:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    tts_model: str = os.getenv("TTS_MODEL", "tts_models/es/css10/vits")
    gradio_host: str = os.getenv("GRADIO_HOST", "0.0.0.0")
    gradio_port: int = int(os.getenv("GRADIO_PORT", "7860"))
    max_tool_rounds: int = int(os.getenv("OLLAMA_MAX_TOOL_ROUNDS", "4"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    cors_allowed_origins: tuple[str, ...] = parse_csv_env(
        os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"


settings = Settings()
