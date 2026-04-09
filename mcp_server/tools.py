import logging
import os
import re
import time
from decimal import Decimal
from typing import Any

from mcp_server.db import DatabasePool


logger = logging.getLogger("techshop.tools")


class SalesToolsService:
    def __init__(self) -> None:
        self._product_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}
        self._product_cache_ttl = int(os.getenv("PRODUCT_CACHE_TTL", "30"))

    def _normalize_decimal(self, value: Decimal | float | int) -> float:
        return float(value)

    def _validate_name(self, value: str, field: str) -> str:
        normalized = (value or "").strip()
        if len(normalized) < 2:
            raise ValueError(f"`{field}` debe tener al menos 2 caracteres.")
        return normalized

    def _validate_email(self, value: str) -> str:
        normalized = (value or "").strip().lower()
        email_match = re.search(
            r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})",
            normalized,
            flags=re.IGNORECASE,
        )
        if email_match:
            normalized = email_match.group(1).lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError("`email` debe tener un formato válido.")
        return normalized

    def _validate_phone(self, value: str) -> str:
        normalized = re.sub(r"[^\d+]", "", (value or "").strip())
        if len(normalized) < 6:
            raise ValueError("`telefono` debe tener al menos 6 caracteres.")
        return normalized

    def _coerce_positive_int(self, value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"`{field}` debe ser un entero positivo.")
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, float):
            parsed = int(value)
        else:
            text = str(value or "").strip()
            match = re.search(r"\d+", text)
            parsed = int(match.group(0)) if match else 0
        if parsed <= 0:
            raise ValueError(f"`{field}` debe ser un entero positivo.")
        return parsed

    def _validate_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(items, list) or not items:
            raise ValueError("`items` debe ser una lista no vacía.")

        validated_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Cada item debe ser un objeto.")
            cantidad = self._coerce_positive_int(item.get("cantidad", 0), "cantidad")
            producto_id_raw = item.get("producto_id")
            producto_nombre = (item.get("producto_nombre") or item.get("nombre") or "").strip()

            if producto_id_raw not in (None, "", 0, "0"):
                producto_id = self._coerce_positive_int(producto_id_raw, "producto_id")
                validated_items.append({"producto_id": producto_id, "cantidad": cantidad})
                continue

            if producto_nombre:
                validated_items.append(
                    {"producto_nombre": producto_nombre, "cantidad": cantidad}
                )
                continue

            raise ValueError(
                "Cada item debe incluir `producto_id` válido o `producto_nombre`."
            )
        return validated_items

    def buscar_cliente(self, nombre: str) -> dict[str, Any]:
        nombre = self._validate_name(nombre, "nombre")
        sql = """
            SELECT id, nombre, email, telefono, fecha_creacion
            FROM clientes
            WHERE nombre LIKE %s
            ORDER BY nombre ASC
            LIMIT 10
        """
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(sql, (f"%{nombre}%",))
                rows = cursor.fetchall()

        return {"ok": True, "count": len(rows), "clientes": rows}

    def crear_cliente(self, nombre: str, email: str, telefono: str) -> dict[str, Any]:
        nombre = self._validate_name(nombre, "nombre")
        email = self._validate_email(email)
        telefono = self._validate_phone(telefono)

        with DatabasePool.connection() as connection:
            try:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute(
                        """
                        SELECT id, nombre, email, telefono, fecha_creacion
                        FROM clientes
                        WHERE email = %s
                        LIMIT 1
                        """,
                        (email,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        return {
                            "ok": True,
                            "created": False,
                            "message": "El cliente ya existía.",
                            "cliente": existing,
                        }

                    cursor.execute(
                        """
                        INSERT INTO clientes (nombre, email, telefono)
                        VALUES (%s, %s, %s)
                        """,
                        (nombre, email, telefono),
                    )
                    cliente_id = cursor.lastrowid
                    connection.commit()

                    cursor.execute(
                        """
                        SELECT id, nombre, email, telefono, fecha_creacion
                        FROM clientes
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (cliente_id,),
                    )
                    created = cursor.fetchone()

                return {
                    "ok": True,
                    "created": True,
                    "message": "Cliente creado correctamente.",
                    "cliente": created,
                }
            except Exception:
                connection.rollback()
                logger.exception("No se pudo crear el cliente")
                raise

    def listar_productos(self) -> dict[str, Any]:
        now = time.time()
        if self._product_cache["data"] and now < self._product_cache["expires_at"]:
            return {
                "ok": True,
                "cached": True,
                "count": len(self._product_cache["data"]),
                "productos": self._product_cache["data"],
            }

        sql = """
            SELECT id, nombre, descripcion, precio, stock
            FROM productos
            WHERE activo = TRUE
            ORDER BY nombre ASC
        """
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()

        products = [
            {**row, "precio": self._normalize_decimal(row["precio"])}
            for row in rows
        ]
        self._product_cache["data"] = products
        self._product_cache["expires_at"] = now + self._product_cache_ttl
        return {"ok": True, "cached": False, "count": len(products), "productos": products}

    def crear_pedido(self, cliente_nombre: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        cliente_nombre = self._validate_name(cliente_nombre, "cliente_nombre")
        items = self._validate_items(items)

        with DatabasePool.connection() as connection:
            try:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute(
                        """
                        SELECT id, nombre, email
                        FROM clientes
                        WHERE nombre LIKE %s
                        ORDER BY nombre ASC
                        LIMIT 2
                        """,
                        (f"%{cliente_nombre}%",),
                    )
                    clients = cursor.fetchall()
                    if not clients:
                        raise ValueError("No se encontró un cliente con ese nombre.")
                    if len(clients) > 1:
                        raise ValueError(
                            "El nombre del cliente es ambiguo. Usa un nombre más específico."
                        )

                    cliente = clients[0]
                    products: dict[int, dict[str, Any]] = {}
                    items_resolved: list[dict[str, Any]] = []

                    ids_to_load = [
                        item["producto_id"] for item in items if item.get("producto_id")
                    ]
                    if ids_to_load:
                        placeholders = ", ".join(["%s"] * len(ids_to_load))
                        cursor.execute(
                            f"""
                            SELECT id, nombre, precio, stock, activo
                            FROM productos
                            WHERE id IN ({placeholders})
                            """,
                            tuple(ids_to_load),
                        )
                        products.update({row["id"]: row for row in cursor.fetchall()})

                    for item in items:
                        if item.get("producto_id"):
                            items_resolved.append(item)
                            continue

                        producto_nombre = self._validate_name(
                            item.get("producto_nombre", ""),
                            "producto_nombre",
                        )
                        cursor.execute(
                            """
                            SELECT id, nombre, precio, stock, activo
                            FROM productos
                            WHERE nombre LIKE %s AND activo = TRUE
                            ORDER BY nombre ASC
                            LIMIT 2
                            """,
                            (f"%{producto_nombre}%",),
                        )
                        matched_products = cursor.fetchall()
                        if not matched_products:
                            raise ValueError(
                                f"No se encontró el producto `{producto_nombre}`."
                            )
                        if len(matched_products) > 1:
                            raise ValueError(
                                f"El producto `{producto_nombre}` es ambiguo."
                            )
                        matched_product = matched_products[0]
                        products[matched_product["id"]] = matched_product
                        items_resolved.append(
                            {
                                "producto_id": matched_product["id"],
                                "cantidad": item["cantidad"],
                            }
                        )

                    detalles = []
                    total = Decimal("0.00")
                    for item in items_resolved:
                        product = products.get(item["producto_id"])
                        if not product or not product["activo"]:
                            raise ValueError(
                                f"El producto {item['producto_id']} no existe o está inactivo."
                            )
                        if product["stock"] < item["cantidad"]:
                            raise ValueError(
                                f"Stock insuficiente para {product['nombre']}."
                            )

                        subtotal = product["precio"] * item["cantidad"]
                        total += subtotal
                        detalles.append(
                            {
                                "producto_id": product["id"],
                                "nombre": product["nombre"],
                                "cantidad": item["cantidad"],
                                "precio_unitario": product["precio"],
                                "subtotal": subtotal,
                            }
                        )

                    cursor.execute(
                        """
                        INSERT INTO pedidos (cliente_id, estado, total)
                        VALUES (%s, %s, %s)
                        """,
                        (cliente["id"], "pendiente", total),
                    )
                    pedido_id = cursor.lastrowid

                    for detalle in detalles:
                        cursor.execute(
                            """
                            INSERT INTO pedido_detalle
                                (pedido_id, producto_id, cantidad, precio_unitario, subtotal)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                pedido_id,
                                detalle["producto_id"],
                                detalle["cantidad"],
                                detalle["precio_unitario"],
                                detalle["subtotal"],
                            ),
                        )

                    connection.commit()

                return {
                    "ok": True,
                    "pedido": {
                        "id": pedido_id,
                        "cliente": cliente,
                        "estado": "pendiente",
                        "total": self._normalize_decimal(total),
                        "items": [
                            {
                                **detalle,
                                "precio_unitario": self._normalize_decimal(
                                    detalle["precio_unitario"]
                                ),
                                "subtotal": self._normalize_decimal(detalle["subtotal"]),
                            }
                            for detalle in detalles
                        ],
                    },
                }
            except Exception:
                connection.rollback()
                logger.exception("No se pudo crear el pedido")
                raise

    def obtener_pedidos_cliente(self, nombre: str) -> dict[str, Any]:
        nombre = self._validate_name(nombre, "nombre")
        with DatabasePool.connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, nombre, email
                    FROM clientes
                    WHERE nombre LIKE %s
                    ORDER BY nombre ASC
                    LIMIT 10
                    """,
                    (f"%{nombre}%",),
                )
                clients = cursor.fetchall()
                if not clients:
                    return {"ok": True, "count": 0, "pedidos": []}

                client_ids = tuple(client["id"] for client in clients)
                placeholders = ", ".join(["%s"] * len(client_ids))
                cursor.execute(
                    f"""
                    SELECT p.id, p.cliente_id, c.nombre AS cliente_nombre, p.fecha, p.estado, p.total
                    FROM pedidos p
                    INNER JOIN clientes c ON c.id = p.cliente_id
                    WHERE p.cliente_id IN ({placeholders})
                    ORDER BY p.fecha DESC
                    LIMIT 20
                    """,
                    client_ids,
                )
                orders = cursor.fetchall()

                if not orders:
                    return {"ok": True, "count": 0, "pedidos": []}

                order_ids = tuple(order["id"] for order in orders)
                placeholders = ", ".join(["%s"] * len(order_ids))
                cursor.execute(
                    f"""
                    SELECT d.pedido_id, d.producto_id, pr.nombre AS producto_nombre,
                           d.cantidad, d.precio_unitario, d.subtotal
                    FROM pedido_detalle d
                    INNER JOIN productos pr ON pr.id = d.producto_id
                    WHERE d.pedido_id IN ({placeholders})
                    ORDER BY d.id ASC
                    """,
                    order_ids,
                )
                details = cursor.fetchall()

        detail_map: dict[int, list[dict[str, Any]]] = {}
        for detail in details:
            detail_map.setdefault(detail["pedido_id"], []).append(
                {
                    **detail,
                    "precio_unitario": self._normalize_decimal(detail["precio_unitario"]),
                    "subtotal": self._normalize_decimal(detail["subtotal"]),
                }
            )

        result_orders = []
        for order in orders:
            result_orders.append(
                {
                    **order,
                    "total": self._normalize_decimal(order["total"]),
                    "items": detail_map.get(order["id"], []),
                }
            )

        return {"ok": True, "count": len(result_orders), "pedidos": result_orders}
