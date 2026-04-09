from typing import Any

from mcp_server.tools import SalesToolsService


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


class ToolExecutor:
    def __init__(self, sales_tools: SalesToolsService | None = None) -> None:
        self._sales_tools = sales_tools or SalesToolsService()

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "buscar_cliente": lambda args: self._sales_tools.buscar_cliente(args["nombre"]),
            "crear_cliente": lambda args: self._sales_tools.crear_cliente(
                args["nombre"], args["email"], args["telefono"]
            ),
            "listar_productos": lambda args: self._sales_tools.listar_productos(),
            "crear_pedido": lambda args: self._sales_tools.crear_pedido(
                args["cliente_nombre"], args["items"]
            ),
            "obtener_pedidos_cliente": lambda args: self._sales_tools.obtener_pedidos_cliente(
                args["nombre"]
            ),
        }
        if tool_name not in handlers:
            raise ValueError(f"Herramienta no soportada: {tool_name}")
        return handlers[tool_name](arguments)
