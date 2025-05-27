from telethon import TelegramClient, events
from telethon.tl.types import Message as TelethonMessage
import asyncio
import logging
from typing import List, Optional

from listener.messager import MediaDownloader
from listener.parser import MessageConverter
from schema import Message
from listener.database.connectDB import PostgreSQLConnector
from listener.database.baseDB import TelegramMessageHandler
from listener.messager.message_loder import MessageLoader

logger = logging.getLogger(__name__)


class TelegramMonitor:
    """Упрощенный мониторинг Telegram каналов с записью в БД."""

    def __init__(self, client: TelegramClient):
        self.client = client
        self._is_running = False

        # Инициализация компонентов
        self.message_loader = MessageLoader(
            client=client,
            downloader=MediaDownloader(client),
            converter=MessageConverter()
        )

        # Фоновые задачи
        self._tasks: List[asyncio.Task] = []

    async def start_monitor(self):
        """Запускает мониторинг сообщений."""
        if self._is_running:
            logger.warning("Мониторинг уже запущен")
            return

        if not self.client.is_connected():
            raise ConnectionError("Клиент Telegram не подключен")

        try:
            self.client.add_event_handler(self._handle_new_message, events.NewMessage)
            self._is_running = True

            # Запуск задачи записи в БД
            self._tasks = [
                asyncio.create_task(self._database_writer_task(), name="db_writer")
            ]

            logger.info("Мониторинг успешно запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга: {e}")
            await self.stop_monitor()
            raise

    async def stop_monitor(self):
        """Останавливает мониторинг."""
        if not self._is_running:
            return

        self._is_running = False

        # Остановка задач
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Мониторинг остановлен")

    async def _handle_new_message(self, event: events.NewMessage.Event):
        """Обрабатывает новое сообщение."""
        try:
            logger.info(f"Получено новое сообщение ID: {event.message.id}")
            await self.message_loader.process_message(event.message)
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")

    async def _database_writer_task(self):
        """Записывает обработанные сообщения в БД."""
        logger.info("Задача записи в БД запущена")

        while self._is_running:
            try:
                message = await self.message_loader.get_processed_message()

                if message is None:
                    await asyncio.sleep(1)
                    continue

                # Запись в БД
                async with PostgreSQLConnector() as connector:
                    handler = TelegramMessageHandler(connector)
                    success = await handler.save_message(message)

                    if success:
                        logger.info(f"Сообщение ID={message.message_id} успешно записано в БД, тип  {message.message_type}")
                    else:
                        logger.warning(f"Не удалось записать сообщение ID={message.message_id}")

            except Exception as e:
                logger.error(f"Ошибка записи в БД: {e}")
                await asyncio.sleep(5)

    def get_status(self) -> dict:
        """Возвращает статус мониторинга."""
        return {
            "is_running": self._is_running,
            "is_connected": self.client.is_connected()
        }
    def is_running(self) -> bool:
        return self._is_running

    async def __aenter__(self):
        await self.start_monitor()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_monitor()