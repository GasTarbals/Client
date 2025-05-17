import asyncio

from telethon import TelegramClient
from typing import List, Optional, Union, Dict, Any
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import Channel, InputChannel, InputPeerChannel, Message
import logging
logger = logging.getLogger(__name__)
from telethon.errors import (
    ChatWriteForbiddenError,
    PeerIdInvalidError,
    MessageDeleteForbiddenError,
    MessageIdInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError
)


class TelegramFunctions:
    def __init__(self, client: TelegramClient):
        """
        Инициализация клиента
        :param session_name: Название сессии (без .session)
        :param api_id: Ваш API ID из my.telegram.org
        :param api_hash: Ваш API Hash из my.telegram.org
        """
        self.client = client


    async def get_all_channels(self) -> List[Dict[str, Any]]:
        """
        Получить список всех каналов/групп с их основными данными

        Returns:
            List[Dict]: Список словарей с информацией о каналах в формате:
            {
                "id": int,            # ID канала
                "title": str,         # Название канала
                "username": Optional[str],  # @username (если есть)
                "is_channel": bool    # Является ли каналом (а не чатом)
            }
        """
        try:
            dialogs = await self.client.get_dialogs()
            result = []

            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, Channel):
                    result.append({
                        "id": entity.id,
                        "title": getattr(entity, 'title', ''),
                        "username": getattr(entity, 'username', None),
                        "is_channel": getattr(entity, 'broadcast', False)
                    })

            logger.info(f"Retrieved {len(result)} channels")
            return result

        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            return []

    async def join_channel(self, channel_identifier: Union[str, int]) -> bool:
        """
        Присоединиться к каналу/группе
        :param channel_identifier: @username или ID канала
        :return: True если успешно
        """
        try:
            # Для username
            if isinstance(channel_identifier, str):
                entity = await self.client.get_entity(channel_identifier)
            # Для ID канала
            else:
                entity = InputChannel(channel_identifier, 0)

            await self.client(JoinChannelRequest(entity))
            return True
        except Exception as e:
            print(f"Ошибка входа в канал: {e}")
            return False

    async def leave_channel(self, channel_identifier: Union[str, int]) -> bool:
        """
        Покинуть канал/группу
        :param channel_identifier: @username или ID канала
        :return: True если успешно
        """
        try:
            if isinstance(channel_identifier, str):
                entity = await self.client.get_entity(channel_identifier)
            else:
                entity = InputChannel(channel_identifier, 0)

            await self.client(LeaveChannelRequest(entity))
            return True
        except Exception as e:
            print(f"Ошибка выхода из канала: {e}")
            return False

    async def get_last_message(self, channel: Union[str, int]) -> Optional[Message]:
        """
        Получить последнее сообщение в канале
        :param channel: @username или ID канала
        :return: Последнее сообщение или None при ошибке
        """
        try:
            messages = await self.client.get_messages(
                entity=channel,
                limit=1
            )
            return messages[0] if messages else None
        except Exception as e:
            print(f"Ошибка получения последнего сообщения: {e}")
            return None


    async def get_last_comment(self, channel: Union[str, int], message_id: int) -> Optional[Message]:
        """
        Получить последний комментарий к сообщению
        :param channel: @username или ID канала
        :param message_id: ID сообщения
        :return: Последний комментарий или None при ошибке
        """
        try:
            comments = await self.client.get_messages(
                entity=channel,
                reply_to=message_id,
                limit=1
            )
            return comments[0] if comments else None
        except Exception as e:
            print(f"Ошибка получения последнего комментария: {e}")
            return None

    async def get_messages(
            self,
            channel: Union[str, int],
            limit: int = 100,
            message_id: Optional[int] = None,
            offset_id: Optional[int] = None,
            reverse: bool = False
    ) -> List[Message]:
        """
        Получить список сообщений из канала/чата с возможностью фильтрации

        :param channel: @username или ID канала/чата
        :param limit: Максимальное количество сообщений (по умолчанию 100)
        :param message_id: Получить конкретное сообщение по ID (опционально)
        :param offset_id: ID сообщения, с которого начинать выборку (для пагинации)
        :param reverse: Если True, возвращает сообщения в обратном порядке (от старых к новым)
        :return: Список объектов Message

        Примеры использования:
        1. Получить последние 50 сообщений: get_messages("@channel", limit=50)
        2. Получить конкретное сообщение: get_messages("@channel", message_id=123)
        3. Пагинация: get_messages("@channel", offset_id=last_message_id, limit=20)
        """
        try:
            kwargs = {
                'entity': channel,
                'limit': min(limit, 200)  # Ограничиваем максимальный лимит
            }

            if message_id is not None:
                kwargs['ids'] = message_id
            if offset_id is not None:
                kwargs['offset_id'] = offset_id
            if reverse:
                kwargs['reverse'] = True

            messages = await self.client.get_messages(**kwargs)

            # Если запрашивали конкретное сообщение по ID, возвращаем его в списке
            if message_id is not None and messages:
                return [messages] if not isinstance(messages, list) else messages

            return list(messages)

        except Exception as e:
            print(f"Ошибка получения сообщений: {e}")
            return []
