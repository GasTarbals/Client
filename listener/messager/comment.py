from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Set, AsyncGenerator, Optional, Dict, List
import asyncio
import logging
from urllib.parse import urlparse
from telethon import TelegramClient
from telethon.tl.types import PeerChannel, Message as TelethonMessage
import os
class CommentTracker:
    """Трекер комментариев с расширенным функционалом кеширования."""

    def __init__(self, client: TelegramClient, **kwargs):
        """
        Args:
            client: Экземпляр TelegramClient
            kwargs:
                - channels_file: Путь к файлу с каналами
                - check_interval: Интервал проверки (по умолчанию 60 сек)
                - tracking_period: Период отслеживания (по умолчанию 24 часа)
                - request_delay: Задержка между запросами (по умолчанию 1 сек)
                - max_cached_comments: Максимальное количество кешированных комментариев (по умолчанию 1000)
        """
        self.client = client
        self.check_interval = kwargs.get('check_interval', 60)
        self.tracking_hours = kwargs.get('tracking_period', 24)
        self.request_delay = kwargs.get('request_delay', 1)
        self.max_cached = kwargs.get('max_cached_comments', 1000)
        self.channels_file = kwargs.get('channels_file')

        # Хранилища данных
        self._tracked_channels = set()
        self._tracked_messages = {}  # {channel_id: {msg_id: post_time}}
        self._processed_comments = {}  # {channel_id: {msg_id: {comment_ids}}}

        # Новые поля для кеширования
        self._new_comments_cache = defaultdict(list)  # {channel_id: {msg_id: [comments]}}
        self._cache_lock = asyncio.Lock()
        self._total_cached = 0
        self._is_active = False
        self._background_task = None

    # Сохраняем все существующие методы без изменений
    async def _resolve_channel(self, url_or_username: str) -> Optional[int]:
        """Преобразует URL/username канала в ID."""
        try:
            if url_or_username.startswith('https://'):
                parsed = urlparse(url_or_username)
                username = parsed.path.lstrip('/')
            else:
                username = url_or_username.lstrip('@')

            entity = await self.client.get_entity(username)
            return entity.id if hasattr(entity, 'id') else None
        except Exception as e:
            logging.warning(f"Не удалось получить канал {url_or_username}: {str(e)}")
            return None

    async def load_channels(self) -> Set[int]:
        """Загружает каналы из файла или возвращает пустое множество, если файла нет."""
        if self.channels_file and os.path.exists(self.channels_file):
            try:
                return await self._load_channels_from_file()
            except Exception as e:
                logging.warning(f"Ошибка загрузки каналов из файла {self.channels_file}: {str(e)}")

        logging.warning(f"Файл с каналами не найден: {self.channels_file}")
        return set()  # Возвращаем пустое множество вместо списка

    async def _load_channels_from_file(self) -> Set[int]:
        """Загружает каналы из файла."""
        channel_ids = set()

        with open(self.channels_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if channel_id := await self._resolve_channel(line):
                        channel_ids.add(channel_id)
                    await asyncio.sleep(self.request_delay)

        return channel_ids

    async def _load_channels_from_dialogs(self) -> Set[int]:
        """Загружает все каналы из диалогов."""
        return {
            dialog.id async for dialog in self.client.iter_dialogs()
            if dialog.is_channel
        }

    async def start_tracking(self):
        """Запускает фоновое отслеживание комментариев."""
        if self._is_active:
            return

        self._tracked_channels = await self.load_channels()
        logging.info(f"Начато отслеживание {len(self._tracked_channels)} каналов")

        self._is_active = True
        self._background_task = asyncio.create_task(self._tracking_loop())

    async def stop_tracking(self):
        """Останавливает отслеживание комментариев."""
        if not self._is_active:
            return

        self._is_active = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

    async def _tracking_loop(self):
        """Основной цикл отслеживания комментариев."""
        while self._is_active:
            try:
                await self._check_for_new_comments()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logging.error(f"Ошибка отслеживания: {str(e)}")
                await asyncio.sleep(10)

    async def _check_for_new_comments(self):
        """Проверяет новые комментарии и кеширует их."""
        expired_time = datetime.now(timezone.utc) - timedelta(hours=self.tracking_hours)

        for channel_id in list(self._tracked_messages.keys()):
            self._tracked_messages[channel_id] = {
                msg_id: time for msg_id, time in self._tracked_messages[channel_id].items()
                if time > expired_time
            }
            if not self._tracked_messages[channel_id]:
                del self._tracked_messages[channel_id]
                async with self._cache_lock:
                    self._new_comments_cache.pop(channel_id, None)

        await self._cache_new_comments()

    async def _cache_new_comments(self):
        """Кеширует новые комментарии."""
        async with self._cache_lock:
            for channel_id, messages in self._tracked_messages.items():
                for msg_id in messages.keys():
                    try:
                        async for comment in self._get_message_comments(channel_id, msg_id):
                            if self._total_cached >= self.max_cached:
                                logging.warning("Достигнут лимит кешированных комментариев")
                                return

                            if channel_id not in self._new_comments_cache:
                                self._new_comments_cache[channel_id] = {}
                            if msg_id not in self._new_comments_cache[channel_id]:
                                self._new_comments_cache[channel_id][msg_id] = []

                            self._new_comments_cache[channel_id][msg_id].append(comment)
                            self._total_cached += 1
                    except Exception as e:
                        logging.error(f"Ошибка при кешировании комментариев: {e}")

    async def track_message(self, message: TelethonMessage) -> bool:
        """Начинает отслеживать комментарии к сообщению."""
        if not isinstance(message.peer_id, PeerChannel):
            return False

        channel_id = message.peer_id.channel_id
        if channel_id not in self._tracked_channels:
            return False

        if channel_id not in self._tracked_messages:
            self._tracked_messages[channel_id] = {}

        self._tracked_messages[channel_id][message.id] = datetime.now(timezone.utc)
        return True


    async def _get_message_comments(self, channel_id: int, msg_id: int):
        """Возвращает комментарии к конкретному сообщению."""
        if channel_id not in self._processed_comments:
            self._processed_comments[channel_id] = {}
        if msg_id not in self._processed_comments[channel_id]:
            self._processed_comments[channel_id][msg_id] = set()

        last_id = max(self._processed_comments[channel_id][msg_id], default=0)

        async for comment in self.client.iter_messages(
                channel_id,
                reply_to=msg_id,
                min_id=last_id,
                limit=100
        ):
            if comment.id > last_id:
                comment.is_comment = True
                comment.original_msg_id = msg_id
                self._processed_comments[channel_id][msg_id].add(comment.id)
                yield comment

    # Новые методы для работы с кешем
    async def get_comments(self) -> AsyncGenerator[TelethonMessage, None]:
        """
        Возвращает и очищает кеш новых комментариев.
        Автоматически сортирует по времени публикации.
        """
        async with self._cache_lock:
            for channel_id in list(self._new_comments_cache.keys()):
                for msg_id in list(self._new_comments_cache[channel_id].keys()):
                    comments = self._new_comments_cache[channel_id][msg_id]
                    if comments:
                        # Сортируем комментарии по дате
                        sorted_comments = sorted(
                            comments,
                            key=lambda x: x.date.replace(tzinfo=timezone.utc)
                            if x.date.tzinfo is None else x.date
                        )

                        # Возвращаем и очищаем
                        for comment in sorted_comments:
                            yield comment
                            self._total_cached -= 1

                        self._new_comments_cache[channel_id][msg_id] = []

                # Удаляем пустые записи
                if not self._new_comments_cache[channel_id]:
                    del self._new_comments_cache[channel_id]

    def has_new_comments(self) -> bool:
        """Проверяет наличие новых комментариев в кеше."""
        return any(
            comments
            for channel in self._new_comments_cache.values()
            for comments in channel.values()
            if comments
        )

    def get_cached_count(self) -> int:
        """Возвращает количество кешированных комментариев."""
        return self._total_cached

    @property
    def tracked_channels_count(self) -> int:
        """Количество отслеживаемых каналов."""
        return len(self._tracked_channels)

    @property
    def tracked_messages_count(self) -> int:
        """Количество отслеживаемых сообщений."""
        return sum(len(msgs) for msgs in self._tracked_messages.values())