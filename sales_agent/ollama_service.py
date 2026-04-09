import json
import logging
from typing import Any, Optional

import ollama

from sales_agent.config import settings
from sales_agent.prompts import SYSTEM_PROMPT
from sales_agent.tools_registry import OLLAMA_TOOLS, ToolExecutor


logger = logging.getLogger("techshop.ollama")


class OllamaChatService:
    def __init__(self, tool_executor: ToolExecutor | None = None) -> None:
        self._client = ollama.Client(host=settings.ollama_host)
        self._tool_executor = tool_executor or ToolExecutor()

    def normalize_arguments(self, raw_arguments: Any) -> dict[str, Any]:
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

    def list_models(self) -> list[str]:
        try:
            response = self._client.list()
            models = response.get("models", [])
            names = [model.get("model", "").strip() for model in models if model.get("model")]
            return sorted(set(name for name in names if name))
        except Exception:
            logger.warning("No se pudo obtener la lista de modelos de Ollama.", exc_info=True)
            return []

    def chat(
        self,
        user_message: str,
        model_name: str,
        prior_messages: Optional[list[dict[str, str]]] = None,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if prior_messages:
            messages.extend(prior_messages)
        messages.append({"role": "user", "content": user_message})

        try:
            for _ in range(settings.max_tool_rounds):
                response = self._client.chat(
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
                    arguments = self.normalize_arguments(function_block.get("arguments"))
                    logger.info("Ejecutando herramienta %s con args=%s", tool_name, arguments)

                    try:
                        tool_result = self._tool_executor.execute(tool_name, arguments)
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
                f"Verifica que el servicio esté accesible en `{settings.ollama_host}` y que el modelo "
                f"`{model_name}` exista."
            ) from exc

    def refresh_model_choices(self, current_value: Optional[str]):
        models = self.list_models()
        selected = (current_value or settings.ollama_model).strip() or settings.ollama_model
        if selected not in models:
            models = [selected, *models] if selected else models
        info_text = (
            "Modelos cargados desde Ollama."
            if models
            else "No se pudo cargar la lista desde Ollama. Puedes escribir el modelo manualmente."
        )
        return models, selected, info_text


ollama_service = OllamaChatService()
