from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import InputPeerChannel, InputReplyToMessage
from telethon.errors import ChatWriteForbiddenError, ChannelPrivateError
import random
from typing import List, Optional, Union, Dict, Any
from telethon.tl.functions.channels import  GetFullChannelRequest
import logging

logger = logging.getLogger(__name__)

class MTProtoSender:
    def __init__(self, client):
        self.client = client

    async def safe_send_to_channel(
            self,
            channel_identifier: Union[int, str],
            message: str,
            reply_to_msg_id: Optional[int] = None,
            access_hash: Optional[str] = None
    ) -> bool:
        """
        Безопасная отправка сообщения или комментария в канал/группу обсуждения

        Args:
            channel_identifier: ID канала (число) или username (строка с @)
            message: Текст сообщения/комментария
            reply_to_msg_id: ID сообщения в канале для ответа (опционально)
            access_hash: Хэш доступа (если известен, опционально)

        Returns:
            bool: True если отправка успешна
        """
        try:
            # Получаем сущность канала и группы обсуждения
            channel_entity, linked_chat = await self._get_channel_and_discussion(channel_identifier)

            # Если указан reply_to_msg_id - это комментарий к сообщению в канале
            if reply_to_msg_id:
                # Находим соответствующее сообщение в группе обсуждения
                discussion_msg_id = await self.get_discussion_message_id(
                    channel_identifier,
                    reply_to_msg_id
                )

                if not discussion_msg_id:
                    print(f"Не найдено сообщение в группе обсуждения для {reply_to_msg_id}")
                    return False

                # Отправляем в группу обсуждения как ответ
                peer = InputPeerChannel(
                    channel_id=linked_chat.id,
                    access_hash=linked_chat.access_hash
                )
                await self.client(SendMessageRequest(
                    peer=peer,
                    message=message,
                    no_webpage=True,
                    random_id=random.randint(0, 0x7fffffff),
                    reply_to=InputReplyToMessage(discussion_msg_id)
                ))
            else:
                # Простая отправка сообщения в канал
                peer = InputPeerChannel(
                    channel_id=channel_entity.id,
                    access_hash=channel_entity.access_hash if not access_hash else access_hash
                )
                await self.client(SendMessageRequest(
                    peer=peer,
                    message=message,
                    no_webpage=True,
                    random_id=random.randint(0, 0x7fffffff)
                ))

            return True

        except ChannelPrivateError:
            print(f"Ошибка: Нет доступа к каналу {channel_identifier}")
        except ChatWriteForbiddenError:
            print(f"Ошибка: Нет прав на отправку в {channel_identifier}")
        except ValueError as ve:
            print(f"Ошибка валидации: {str(ve)}")
        except Exception as e:
            print(f"Неизвестная ошибка при отправке в {channel_identifier}: {str(e)}")

        return False

    async def _get_channel_and_discussion(self, channel: Union[str, int]) -> tuple:
        """
        Получает сущность канала и его группы обсуждения

        Args:
            channel: @username или ID канала

        Returns:
            tuple: (channel_entity, linked_chat)

        Raises:
            ValueError: Если канал не найден или нет группы обсуждения
        """
        try:
            channel_entity = await self.client.get_entity(channel)
            full_channel = await self.client(GetFullChannelRequest(channel=channel_entity))

            if not full_channel.full_chat.linked_chat_id:
                raise ValueError("У канала нет привязанной группы обсуждения")

            linked_chat = await self.client.get_entity(full_channel.full_chat.linked_chat_id)
            return channel_entity, linked_chat

        except (TypeError, ValueError, ChannelPrivateError) as e:
            raise ValueError(f"Канал {channel} не найден или недоступен") from e
        except Exception as e:
            raise ValueError(f"Ошибка получения группы обсуждения: {str(e)}") from e

    async def get_discussion_message_id(
            self,
            channel: Union[str, int],
            channel_message_id: int
    ) -> Optional[int]:
        """
        Находит ID сообщения в группе обсуждения по его ID в канале

        Args:
            channel: ID канала или @username
            channel_message_id: ID сообщения в канале

        Returns:
            int: ID сообщения в группе обсуждения или None, если не найдено

        Raises:
            ValueError: Если канал не найден или нет группы обсуждения
        """
        try:
            # Получаем сущность канала и группы обсуждения
            channel_entity, linked_chat = await self._get_channel_and_discussion(channel)

            # Получаем исходное сообщение из канала
            channel_msg = await self.client.get_messages(
                channel_entity,
                ids=channel_message_id
            )
            if not channel_msg:
                return None

            # Критерии поиска в группе обсуждения:
            search_params = {
                'limit': 100,  # Ограничиваем количество проверяемых сообщений
                'reverse': True,  # Ищем от новых к старым
                'search': channel_msg.text[:100] if channel_msg.text else None
            }

            # Ищем сообщение в группе обсуждения
            async for msg in self.client.iter_messages(linked_chat, **search_params):
                # Сравниваем по тексту и дате отправки (±5 секунд)
                if (msg.text == channel_msg.text and
                        abs(msg.date.timestamp() - channel_msg.date.timestamp()) < 5):
                    return msg.id

            return None

        except Exception as e:
            logger.error(f"Ошибка поиска сообщения в группе обсуждения: {str(e)}")
            raise ValueError(f"Не удалось найти сообщение: {str(e)}") from e