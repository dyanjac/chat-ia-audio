import logging
from typing import Any, Optional

from mcp_server.db import DatabasePool


logger = logging.getLogger("techshop.conversation_repository")


class ConversationRepository:
    def save_message(
        self,
        session_id: str,
        cliente_id: Optional[int],
        rol: str,
        mensaje: str,
    ) -> dict[str, Any]:
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversaciones (cliente_id, session_id, rol, mensaje)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (cliente_id, session_id, rol, mensaje),
                )
                conversation_id = cursor.lastrowid
                connection.commit()
                cursor.execute(
                    """
                    SELECT id, cliente_id, session_id, rol, mensaje, fecha
                    FROM conversaciones
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (conversation_id,),
                )
                row = cursor.fetchone()
        return row or {}

    def get_recent_messages(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, cliente_id, session_id, rol, mensaje, fecha
                    FROM conversaciones
                    WHERE session_id = %s
                      AND mensaje IS NOT NULL
                      AND TRIM(mensaje) <> ''
                    ORDER BY fecha DESC, id DESC
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                rows = cursor.fetchall()
        rows.reverse()
        return rows

    def count_messages(self, session_id: str) -> int:
        with DatabasePool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM conversaciones
                    WHERE session_id = %s
                      AND mensaje IS NOT NULL
                      AND TRIM(mensaje) <> ''
                    """,
                    (session_id,),
                )
                result = cursor.fetchone()
        return int(result[0] if result else 0)

    def get_older_messages(self, session_id: str, offset: int) -> list[dict[str, Any]]:
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, cliente_id, session_id, rol, mensaje, fecha
                    FROM conversaciones
                    WHERE session_id = %s
                      AND mensaje IS NOT NULL
                      AND TRIM(mensaje) <> ''
                    ORDER BY fecha ASC, id ASC
                    LIMIT %s
                    """,
                    (session_id, offset),
                )
                rows = cursor.fetchall()
        return rows


conversation_repository = ConversationRepository()
