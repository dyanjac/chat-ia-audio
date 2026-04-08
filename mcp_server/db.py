import logging
import os
import time
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling


logger = logging.getLogger("techshop.db")


class DatabaseConfigError(RuntimeError):
    pass


class DatabasePool:
    _pool: pooling.MySQLConnectionPool | None = None

    @classmethod
    def get_pool(cls) -> pooling.MySQLConnectionPool:
        if cls._pool is None:
            cls._pool = cls._create_pool_with_retry()
        return cls._pool

    @classmethod
    def _create_pool_with_retry(cls) -> pooling.MySQLConnectionPool:
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")
        db_port = int(os.getenv("DB_PORT", "3306"))
        pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        retries = int(os.getenv("DB_CONNECT_RETRIES", "5"))
        retry_delay = float(os.getenv("DB_CONNECT_RETRY_DELAY", "2"))

        if not all([db_host, db_user, db_password, db_name]):
            raise DatabaseConfigError(
                "Faltan variables DB_HOST, DB_USER, DB_PASSWORD o DB_NAME."
            )

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                logger.info("Inicializando pool MySQL intento %s/%s", attempt, retries)
                return pooling.MySQLConnectionPool(
                    pool_name="techshop_pool",
                    pool_size=pool_size,
                    host=db_host,
                    user=db_user,
                    password=db_password,
                    database=db_name,
                    port=db_port,
                    charset="utf8mb4",
                    use_unicode=True,
                    autocommit=False,
                )
            except mysql.connector.Error as exc:
                last_error = exc
                logger.warning("No se pudo crear el pool MySQL: %s", exc)
                time.sleep(retry_delay)

        raise RuntimeError(
            "No fue posible conectarse a MySQL tras varios intentos."
        ) from last_error

    @classmethod
    @contextmanager
    def connection(cls):
        connection = cls.get_pool().get_connection()
        try:
            yield connection
        finally:
            connection.close()
