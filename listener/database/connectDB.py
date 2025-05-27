import asyncpg
import asyncio
from typing import Optional, Tuple, List, Any
from listener.database.config import DB_CONFIG
import logging

logger = logging.getLogger(__name__)

class PostgreSQLConnector:
    _instance = None
    _connection = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Устанавливает единственное асинхронное подключение"""
        async with self._lock:
            if self._connection is None or self._connection.is_closed():
                try:
                    self._connection = await asyncpg.connect(
                        database=DB_CONFIG["dbname"],
                        user=DB_CONFIG["user"],
                        password=DB_CONFIG["password"],
                        host=DB_CONFIG["host"],
                        port=DB_CONFIG["port"],
                        timeout=10
                    )
                    logger.info("Установлено единственное подключение к PostgreSQL")
                except Exception as e:
                    logger.error(f"Ошибка подключения: {e}")
                    raise

    async def disconnect(self) -> None:
        """Закрывает соединение"""
        async with self._lock:
            if self._connection and not self._connection.is_closed():
                await self._connection.close()
                self._connection = None
                logger.info("Подключение к PostgreSQL закрыто")

    async def execute_query(self, query: str, params: Optional[tuple] = None) -> Tuple[bool, Optional[List[Any]]]:
        """
        Выполняет SQL-запрос и возвращает кортеж:
        - первый элемент: булево значение (успех/ошибка)
        - второй элемент: результат для SELECT или None для других запросов
        """

        try:
            if self._connection is None or self._connection.is_closed():
                await self.connect()

            if query.strip().lower().startswith("select"):
                result = await self._connection.fetch(query, *(params or ()))
                return (True, result)
            else:
                await self._connection.execute(query, *(params or ()))
                return (True, None)
        except Exception as e:
            print(query)
            logger.error(f"Ошибка при выполнении запроса: {e}")
            return (False, None)

    async def __aenter__(self):
        """Асинхронный контекстный менеджер"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Не закрываем соединение при выходе из контекста для Singleton"""
        pass

    @classmethod
    async def close_global_connection(cls):
        """Явное закрытие глобального соединения"""
        if cls._instance and cls._connection and not cls._connection.is_closed():
            await cls._instance.disconnect()