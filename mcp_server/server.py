import logging
import os

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import SalesToolsService


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("techshop.mcp")

mcp = FastMCP("techshop-sales")
service = SalesToolsService()


@mcp.tool()
def buscar_cliente(nombre: str) -> dict:
    """Busca clientes por nombre parcial o completo."""
    return service.buscar_cliente(nombre)


@mcp.tool()
def crear_cliente(nombre: str, email: str, telefono: str) -> dict:
    """Crea un cliente nuevo si todavía no existe por email."""
    return service.crear_cliente(nombre, email, telefono)


@mcp.tool()
def listar_productos() -> dict:
    """Lista productos activos con precio y stock."""
    return service.listar_productos()


@mcp.tool()
def crear_pedido(cliente_nombre: str, items: list[dict]) -> dict:
    """Crea un pedido para un cliente usando una lista de items."""
    return service.crear_pedido(cliente_nombre, items)


@mcp.tool()
def obtener_pedidos_cliente(nombre: str) -> dict:
    """Obtiene el historial de pedidos de un cliente."""
    return service.obtener_pedidos_cliente(nombre)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    logger.info("Iniciando MCP server con transporte %s", transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
