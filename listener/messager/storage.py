from collections import deque
from typing import Deque, List, Optional, Callable, AsyncIterator, AsyncGenerator, Union
import asyncio
from telethon.tl.types import Message as TelethonMessage, PeerChannel
import logging
from telethon import TelegramClient, events
class MessageStorage:
    """Потокобезопасное хранилище для сообщений Telethon.

    Args:
        max_size: Максимальное количество хранимых сообщений (по умолчанию 1000)
    """

    def __init__(self, client:TelegramClient, max_size: int = 1000):
        self._queue: Deque[TelethonMessage] = deque(maxlen=max_size)
        self._new_message_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._waiters = 0
        self.client = client

    async def add_message(self, message: TelethonMessage) -> None:
        """Добавляет новое сообщение в хранилище.

        Args:
            message: Объект сообщения Telethon
        """
        if not isinstance(message, TelethonMessage):
            raise TypeError(f"Expected TelethonMessage, got {type(message)}")

        async with self._lock:
            self._queue.append(message)
            if self._waiters > 0:
                self._new_message_event.set()

    async def get_messages(self, count: int = 1) -> List[TelethonMessage]:
        """Возвращает последние N сообщений.

        Args:
            count: Количество сообщений для возврата
        Returns:
            Список последних сообщений (от старых к новым)
        """
        async with self._lock:
            return list(self._queue)[-count:]

    async def get_messages_filtered(
            self,
            filter_func: Callable[[TelethonMessage], bool],
            count: int = 1
    ) -> List[TelethonMessage]:
        """Возвращает отфильтрованные сообщения.

        Args:
            filter_func: Функция для фильтрации сообщений
            count: Максимальное количество сообщений для возврата
        Returns:
            Список сообщений, удовлетворяющих фильтру
        """
        async with self._lock:
            filtered = [msg for msg in self._queue if filter_func(msg)]
            return filtered[-count:]

    async def _process_media_group(self, first_msg: TelethonMessage, group_timeout: float) -> List[TelethonMessage]:
        """Обработка медиа-группы"""
        group_id = first_msg.grouped_id
        group = [first_msg]
        print(f"📦 Обнаружена медиа-группа (ID: {group_id})")

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < group_timeout:
            try:
                remaining_time = group_timeout - (asyncio.get_event_loop().time() - start_time)
                await asyncio.wait_for(self._new_message_event.wait(), max(0.1, remaining_time))
            except asyncio.TimeoutError:
                break

            async with self._lock:
                for msg in list(self._queue):
                    if hasattr(msg, 'grouped_id') and msg.grouped_id == group_id:

                        group.append(msg)
                        self._queue.remove(msg)
                        print(f"   Добавлен элемент {msg.id} в группу")

                if not self._queue:
                    self._new_message_event.clear()

        print(f"📦 Группа собрана ({len(group)} элементов)")
        return group

    async def wait_for_message(
            self,
            timeout: Optional[float] = None,
            group_timeout: float = 1.0
    ) -> Optional[Union[TelethonMessage, List[TelethonMessage]]]:
        async with self._lock:
            self._waiters += 1

        try:
            # Ожидаем новое сообщение
            try:
                await asyncio.wait_for(self._new_message_event.wait(), timeout)
            except asyncio.TimeoutError:
                return None

            async with self._lock:
                if not self._queue:
                    self._new_message_event.clear()
                    return None

                first_msg = self._queue[-1]
                print(f"📨 Получено сообщение ID {first_msg.id}")

                # Удаляем сообщение из очереди перед обработкой
                self._queue.remove(first_msg)

                # Определяем тип сообщения и обрабатываем
                if hasattr(first_msg, 'grouped_id') and first_msg.grouped_id:
                    return await self._process_media_group(first_msg, group_timeout)
                else:
                    return first_msg

        finally:
            async with self._lock:
                self._waiters -= 1
                if self._waiters == 0:
                    self._new_message_event.clear()


    async def clear(self) -> None:
        """Очищает хранилище сообщений."""
        async with self._lock:
            self._queue.clear()
            self._new_message_event.clear()

    async def size(self) -> int:
        """Возвращает текущее количество сообщений в хранилище."""
        async with self._lock:
            return len(self._queue)

    async def messages_stream(self) -> AsyncGenerator[TelethonMessage, None]:
        """Асинхронно генерирует сообщения по мере их поступления.

        Yields:
            Объекты сообщений Telethon по мере их получения
        """
        while True:
            msg = await self.wait_for_message()
            if msg is not None:
                yield msg

    async def get_all_messages(self) -> List[TelethonMessage]:
        """Возвращает все сообщения в хранилище.

        Returns:
            Список всех сообщений (от старых к новым)
        """
        async with self._lock:
            return list(self._queue)