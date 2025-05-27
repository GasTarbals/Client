from telethon import TelegramClient
from telethon.tl.types import Message as TelethonMessage
from typing import Optional
import asyncio
import logging
from dataclasses import dataclass

from listener.messager import MediaDownloader
from listener.parser import MessageConverter
from schema import Message

logger = logging.getLogger(__name__)


@dataclass
class LoaderStats:
    processed_count: int
    failed_count: int


class MessageLoader:
    """Упрощенный класс для загрузки и обработки сообщений Telegram."""

    def __init__(
            self,
            client: TelegramClient,
            downloader: 'MediaDownloader',
            converter: 'MessageConverter'
    ):
        self.client = client
        self.downloader = downloader
        self.converter = converter
        self._processed_queue = asyncio.Queue()
        self._processed_count = 0
        self._failed_count = 0
        self._is_running = False

    async def process_message(self, message: TelethonMessage) -> None:
        """Основной метод обработки сообщения."""
        if not isinstance(message, TelethonMessage):
            logger.warning(f"Invalid message type: {type(message)}")
            self._failed_count += 1
            return

        try:
            logger.info(f"Processing message ID: {message.id}")

            # Конвертация сообщения
            converted = await self.converter.convert(
                message,
                download_func=self.downloader.download
            )

            if not converted:
                logger.warning(f"Failed to convert message {message.id}")
                self._failed_count += 1
                return

            await self._processed_queue.put(converted)
            self._processed_count += 1
            logger.info(f"Message {message.id} processed successfully")

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {str(e)}")
            self._failed_count += 1

    async def get_processed_message(self) -> Optional['Message']:
        """Получение обработанного сообщения."""
        try:
            message = await asyncio.wait_for(self._processed_queue.get(), timeout=1.0)
            logger.debug(f"Retrieved processed message ID: {message.message_id}")
            return message
        except asyncio.TimeoutError:
            return None

    def get_stats(self) -> LoaderStats:
        """Получение статистики обработки."""
        return LoaderStats(
            processed_count=self._processed_count,
            failed_count=self._failed_count
        )

    async def stop(self):
        """Остановка обработчика."""
        self._is_running = False
        logger.info("Message loader stopped")