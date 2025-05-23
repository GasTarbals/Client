from typing import Optional, Any, Dict
import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import RPCError
from telegram import TelegramFunctions, TelegramComment, MTProtoSender
from telethon.tl.functions.account import UpdateStatusRequest

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
        self.comment: Optional[TelegramComment] = None
        self.mtproto: Optional[MTProtoSender] = None
        logger.debug("TelegramService initialized")

    async def initialize(
            self,
            session: str,
            api_id: int,
            api_hash: str,
            phone: Optional[str] = None,
            device_model: Optional[str] = None,
            system_version: Optional[str] = None,
            app_version: Optional[str] = None,
            lang_code: Optional[str] = None,
            system_lang_code: Optional[str] = None,
            time_zone: Optional[str] = None,
            **kwargs
    ) -> bool:
        """
        Инициализация клиента с полным набором параметров.

        Args:
            session: Сессия (строка или StringSession)
            api_id: API ID Telegram
            api_hash: API Hash Telegram
            phone: Номер телефона (опционально)
            device_model: Модель устройства (опционально)
            system_version: Версия ОС (опционально)
            app_version: Версия приложения (опционально)
            lang_code: Код языка (опционально)
            system_lang_code: Код языка системы (опционально)
            time_zone: Часовой пояс (опционально)
            **kwargs: Дополнительные параметры для TelegramClient

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

                # Собираем параметры для TelegramClient
                client_params = {
                    'session': session,
                    'api_id': api_id,
                    'api_hash': api_hash,
                    **kwargs
                }

                # Добавляем опциональные параметры, если они переданы
                if device_model is not None:
                    client_params['device_model'] = device_model
                if system_version is not None:
                    client_params['system_version'] = system_version
                if app_version is not None:
                    client_params['app_version'] = app_version
                if lang_code is not None:
                    client_params['lang_code'] = lang_code
                if system_lang_code is not None:
                    client_params['system_lang_code'] = system_lang_code

                self.client = TelegramClient(**client_params)
                # Сохраняем все параметры соединения
                self._connection_params = {
                    'session': session,
                    'api_id': api_id,
                    'api_hash': api_hash,
                    'phone': phone,
                    'device_model': device_model,
                    'system_version': system_version,
                    'app_version': app_version,
                    'lang_code': lang_code,
                    'system_lang_code': system_lang_code,
                    'time_zone': time_zone,
                    **kwargs
                }

                self.functions = TelegramFunctions(self.client)
                self.comment = TelegramComment(self.client)
                self.mtproto = MTProtoSender(self.client)
                logger.info("Client initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Initialization failed: {e}")
                await self._cleanup()
                return False

    async def start(self, phone: Optional[str] = None) -> bool:
        """
        Запуск клиента и установка статуса "онлайн".

        Returns:
            bool: True если подключение и установка статуса успешны, False при ошибке
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

                    code = input("Enter Telegram code: ")
                    await self.client.sign_in(auth_phone, code)

                # Устанавливаем статус "онлайн" после успешного подключения
                await self.client(UpdateStatusRequest(offline=False))
                logger.info("Status set to Online")

                self._is_running = True
                logger.info("Client started successfully with online status")
                return True

            except Exception as e:
                logger.error(f"Start failed: {e}")
                await self._cleanup()
                return False

    async def set_online(self) -> bool:
        """
        Принудительная установка статуса "онлайн".

        Returns:
            bool: True если статус успешно установлен, False при ошибке
        """
        if not self.is_connected():
            logger.error("Cannot set online status: client not connected")
            return False

        try:
            await self.client(UpdateStatusRequest(offline=False))
            logger.info("Online status set successfully")
            return True
        except RPCError as e:
            logger.error(f"Failed to set online status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while setting online status: {e}")
            return False

    async def set_offline(self) -> bool:
        """
        Установка статуса "оффлайн".

        Returns:
            bool: True если статус успешно установлен, False при ошибке
        """
        if not self.is_connected():
            logger.error("Cannot set offline status: client not connected")
            return False

        try:
            await self.client(UpdateStatusRequest(offline=True))
            logger.info("Offline status set successfully")
            return True
        except RPCError as e:
            logger.error(f"Failed to set offline status: {e}")
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