import logging
import uuid
from typing import Any, Optional

from sales_agent.conversation_repository import conversation_repository


logger = logging.getLogger("techshop.conversation_service")

ROLE_MAP = {
    "user": "user",
    "assistant": "assistant",
}


class ConversationService:
    def __init__(self, context_limit: int = 12, summary_threshold: int = 15) -> None:
        self._context_limit = context_limit
        self._summary_threshold = summary_threshold

    def ensure_session_id(self, session_id: Optional[str]) -> str:
        normalized = (session_id or "").strip()
        if normalized:
            return normalized
        return uuid.uuid4().hex

    def validate_message(self, message: str) -> str:
        normalized = (message or "").strip()
        if not normalized:
            raise ValueError("`message` no puede estar vacío.")
        return normalized

    def validate_session_id(self, session_id: str) -> str:
        normalized = (session_id or "").strip()
        if len(normalized) < 4:
            raise ValueError("`session_id` debe tener al menos 4 caracteres.")
        return normalized

    def save_message(
        self,
        session_id: str,
        cliente_id: Optional[int],
        rol: str,
        mensaje: str,
    ) -> dict[str, Any]:
        normalized_message = self.validate_message(mensaje)
        normalized_session = self.validate_session_id(session_id)
        if rol not in ROLE_MAP:
            raise ValueError("`rol` no es válido.")
        return conversation_repository.save_message(
            normalized_session,
            cliente_id,
            rol,
            normalized_message,
        )

    def build_context(self, session_id: str) -> list[dict[str, str]]:
        normalized_session = self.validate_session_id(session_id)
        total_messages = conversation_repository.count_messages(normalized_session)
        recent_rows = conversation_repository.get_recent_messages(
            normalized_session, self._context_limit
        )

        context_messages: list[dict[str, str]] = []
        if total_messages > self._summary_threshold:
            older_count = max(0, total_messages - len(recent_rows))
            older_rows = conversation_repository.get_older_messages(
                normalized_session, older_count
            )
            summary = self._summarize_rows(older_rows)
            if summary:
                context_messages.append({"role": "system", "content": summary})

        for row in recent_rows:
            role = ROLE_MAP.get((row.get("rol") or "").strip())
            content = (row.get("mensaje") or "").strip()
            if not role or not content:
                continue
            context_messages.append({"role": role, "content": content})

        return context_messages

    def _summarize_rows(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""

        segments = []
        for row in rows[-8:]:
            role = row.get("rol", "")
            content = (row.get("mensaje") or "").strip()
            if not content:
                continue
            label = "Cliente" if role == "user" else "Asistente"
            shortened = content[:220]
            segments.append(f"{label}: {shortened}")

        if not segments:
            return ""

        return (
            "Resumen de contexto previo de la conversación. "
            "Úsalo como memoria compacta y prioriza los mensajes recientes.\n"
            + "\n".join(segments)
        )


conversation_service = ConversationService()
