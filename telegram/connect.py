from typing import Optional, Any, Dict
import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import RPCError
from telegram import TelegramFunctions

logger = logging.getLogger(__name__)


class TelegramService:
    """Singleton класс для работы с Telegram API с явным возвратом статуса операций."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramService, cls).__new__(cls)
            cls._instance._init_flag = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.client: Optional[TelegramClient] = None
        self._is_running = False
        self._lock = asyncio.Lock()
        self._connection_params: Dict[str, Any] = {}
        self._initialized = True
        self.functions: Optional[TelegramFunctions] = None
        logger.debug("TelegramService initialized")

    async def initialize(
            self,
            session: str,
            api_id: int,
            api_hash: str,
            phone: Optional[str] = None,
            **kwargs
    ) -> bool:
        """
        Инициализация клиента.

        Returns:
            bool: True если инициализация успешна, False при ошибке
        """
        async with self._lock:
            if self.client is not None:
                logger.warning("Client already initialized")
                return True

            try:
                if not isinstance(api_id, int):
                    raise TypeError("API ID must be integer")
                if not isinstance(api_hash, str):
                    raise TypeError("API hash must be string")
                if not isinstance(session, (str, StringSession)):
                    raise TypeError("Session must be string or StringSession")

                self.client = TelegramClient(
                    session=session,
                    api_id=api_id,
                    api_hash=api_hash,
                    **kwargs
                )
                self._connection_params = {
                    'session': session,
                    'api_id': api_id,
                    'api_hash': api_hash,
                    'phone': phone,
                    **kwargs
                }
                self.functions = TelegramFunctions(self.client)
                logger.info("Client initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Initialization failed: {e}")
                await self._cleanup()
                return False

    async def start(self, phone: Optional[str] = None) -> bool:
        """
        Запуск клиента.

        Returns:
            bool: True если подключение успешно, False при ошибке
        """
        async with self._lock:
            if self._is_running:
                return True

            if self.client is None:
                logger.error("Client not initialized")
                return False

            try:
                if self.client.is_connected():
                    self._is_running = True
                    return True

                auth_phone = phone or self._connection_params.get('phone')
                await self.client.connect()

                if not await self.client.is_user_authorized():
                    if not auth_phone:
                        logger.error("Authorization required but no phone provided")
                        return False

                    sent_code = await self.client.send_code_request(auth_phone)
                    logger.info(f"Code request sent (type: {sent_code.type})")

                    # В реальном приложении замените на получение кода из API
                    code = input("Enter Telegram code: ")

                    await self.client.sign_in(auth_phone, code)

                self._is_running = True
                logger.info("Client started successfully")
                return True

            except Exception as e:
                logger.error(f"Start failed: {e}")
                await self._cleanup()
                return False

    async def stop(self) -> bool:
        """
        Остановка клиента.

        Returns:
            bool: True если отключение успешно, False при ошибке
        """
        async with self._lock:
            if not self._is_running:
                return True

            try:
                if self.client and self.client.is_connected():
                    await self.client.disconnect()

                self._is_running = False
                logger.info("Client stopped successfully")
                return True

            except Exception as e:
                logger.error(f"Stop failed: {e}")
                await self._cleanup()
                return False

    async def restart(self) -> bool:
        """Перезапуск клиента."""
        async with self._lock:
            stopped = await self.stop()  # Получаем результат stop()
            if not stopped:
                return False
            return await self.start()  # Возвращаем результат start()

    async def _cleanup(self) -> bool:
        """Аварийная очистка ресурсов."""
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            self._is_running = False
            return True
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return False
        finally:
            logger.info("Cleanup completed")

    async def ensure_connection(self) -> bool:
        """Гарантирует активное соединение с Telegram."""
        if self.is_connected():
            return True
        return await self.start()  # Правильное использование await

    @property
    def is_running(self) -> bool:
        """Текущий статус работы сервиса."""
        return self._is_running

    def is_connected(self) -> bool:
        """Проверка активного соединения."""
        return self.client is not None and self.client.is_connected()

    def is_authorized(self) -> bool:
        """Проверка авторизации пользователя."""
        return self.client is not None and self.client.is_user_authorized()