import asyncio
from telethon import TelegramClient
from typing import List, Optional, Union
from telethon.tl.functions.channels import  GetFullChannelRequest
from telethon.tl.types import Message, DocumentAttributeVideo
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
import io
import base64
from telegram import TelegramCommentSchema, MediaType, MediaAttachment


class TelegramComment:
    def __init__(self, client: TelegramClient):
        self.client = client

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

    async def _validate_message_exists(self, channel_entity, message_id: int) -> None:
        """
        Проверяет существование сообщения в канале

        Args:
            channel_entity: Сущность канала
            message_id: ID сообщения

        Raises:
            ValueError: Если сообщение не найдено
        """
        try:
            target_msg = await self.client.get_messages(channel_entity, ids=message_id)
            if not target_msg:
                raise ValueError(f"Сообщение с ID {message_id} не найдено")
        except MessageIdInvalidError:
            raise ValueError(f"Сообщение с ID {message_id} не существует")
        except Exception as e:
            raise ValueError(f"Ошибка проверки сообщения: {str(e)}") from e

    async def _prepare_media_file(self, media: MediaAttachment) -> tuple:
        """
        Подготавливает файл и параметры для отправки медиа

        Args:
            media: Объект MediaAttachment

        Returns:
            tuple: (file, send_kwargs)
        """
        file = io.BytesIO(media.binary_data)

        extensions = {
            MediaType.PHOTO: 'jpg',
            MediaType.VIDEO: 'mp4',
            MediaType.AUDIO: 'mp3',
            MediaType.DOCUMENT: 'bin'
        }
        file.name = f"media.{extensions.get(media.type, 'bin')}"

        # Генерация превью
        thumbnail = None
        if not media.thumbnail_data and media.type in (MediaType.PHOTO, MediaType.VIDEO):
            try:
                thumbnail = MediaAttachment.generate_thumbnail(media.binary_data)
            except Exception as e:
                logger.warning(f"Не удалось сгенерировать превью: {str(e)}")

        # Базовые параметры отправки
        send_kwargs = {
            'file': file,
            'thumb': io.BytesIO(thumbnail) if thumbnail else None
        }

        # Специфичные настройки
        if media.type == MediaType.PHOTO:
            send_kwargs['force_document'] = False
        elif media.type == MediaType.VIDEO:
            send_kwargs.update({
                'supports_streaming': True,
                'attributes': [DocumentAttributeVideo(duration=0, w=0, h=0)],
                'force_document': False
            })
        else:
            send_kwargs['force_document'] = True

        return file, send_kwargs

    async def add_comment(
            self,
            channel: Union[str, int],
            channel_message_id: int,
            comment: TelegramCommentSchema
    ) -> Optional[Message]:
        """
        Добавляет комментарий к сообщению в группе обсуждения канала.

        Args:
            channel: @username или ID канала
            channel_message_id: ID сообщения в канале, к которому добавляется комментарий
            comment: Данные комментария (текст и/или медиа)

        Returns:
            Message: Объект отправленного сообщения или None в случае ошибки

        Raises:
            ValueError: При ошибках валидации или проблемах с отправкой
        """
        try:
            # Валидация входных данных
            comment.validate_content()

            if channel_message_id <= 0:
                raise ValueError("Некорректный ID сообщения в канале")

            # Получаем сущность канала и группы обсуждения
            channel_entity, linked_chat = await self._get_channel_and_discussion(channel)

            # Проверяем существование исходного сообщения в канале
            await self._validate_message_exists(channel_entity, channel_message_id)

            # Находим соответствующее сообщение в группе обсуждения
            discussion_msg = await self._find_discussion_message(channel_entity, linked_chat, channel_message_id)
            if not discussion_msg:
                raise ValueError(
                    f"Не найдено соответствующее сообщение в группе обсуждения для сообщения {channel_message_id}")

            # Отправляем текстовый комментарий
            if not comment.media:
                return await self.client.send_message(
                    entity=linked_chat,
                    message=comment.text,
                    reply_to=discussion_msg.id
                )

            # Отправляем медиа-комментарий
            file, send_kwargs = await self._prepare_media_file(comment.media)
            send_kwargs.update({
                'entity': linked_chat,
                'caption': comment.text or comment.media.caption,
                'reply_to': discussion_msg.id
            })

            return await self.client.send_file(**send_kwargs)

        except ChatWriteForbiddenError:
            raise ValueError("Нет прав на комментирование в группе обсуждения")
        except PeerIdInvalidError:
            raise ValueError("Некорректный ID группы обсуждения")
        except ValueError as ve:
            logger.error(f"[VALIDATION ERROR] {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"[CRITICAL ERROR] {str(e)}", exc_info=True)
            raise ValueError(f"Ошибка при отправке комментария: {str(e)}") from e

    async def _find_discussion_message(
            self,
            channel_entity,
            linked_chat,
            channel_message_id: int
    ) -> Optional[Message]:
        """
        Находит сообщение в группе обсуждения по ID сообщения в канале

        Args:
            channel_entity: Сущность канала
            linked_chat: Сущность группы обсуждения
            channel_message_id: ID сообщения в канале

        Returns:
            Optional[Message]: Найденное сообщение или None
        """
        try:
            # Получаем исходное сообщение из канала
            channel_msg = await self.client.get_messages(channel_entity, ids=channel_message_id)
            if not channel_msg:
                return None

            # Ищем сообщение в группе обсуждения
            async for msg in self.client.iter_messages(linked_chat):
                # Сравниваем по дате (±5 секунды) и тексту (если есть)
                if abs(msg.date.timestamp() - channel_msg.date.timestamp()) <= 5:
                    if channel_msg.text:
                        if msg.text == channel_msg.text:
                            return msg
                    else:
                        # Для медиа-сообщений сравниваем captions
                        if getattr(msg, 'caption', '') == getattr(channel_msg, 'caption', ''):
                            return msg

            return None

        except Exception as e:
            logger.error(f"Ошибка поиска сообщения в группе обсуждения: {str(e)}")
            raise ValueError(f"Не удалось найти сообщение: {str(e)}") from e

    async def delete_comment(
            self,
            channel: Union[str, int],
            comment_id: int
    ) -> bool:
        """
        Удаляет комментарий из группы обсуждения канала

        Args:
            channel: @username или ID канала
            comment_id: ID комментария для удаления в группе обсуждения

        Returns:
            bool: True если удаление успешно, False если нет

        Raises:
            ValueError: Если канал/сообщение не найдены или нет прав
        """
        try:
            if  comment_id <= 0:
                raise ValueError("Некорректный ID сообщения")

            # Получаем группу обсуждения
            _, linked_chat = await self._get_channel_and_discussion(channel)

            # Удаляем комментарий
            await self.client.delete_messages(linked_chat, [comment_id])
            return True

        except ChatAdminRequiredError:
            raise ValueError("Нет прав администратора для удаления сообщений")
        except MessageDeleteForbiddenError:
            raise ValueError("Нельзя удалить это сообщение (возможно, прошло слишком много времени)")
        except Exception as e:
            logger.error(f"Ошибка при удалении комментария: {str(e)}")
            raise ValueError(f"Ошибка при удалении: {str(e)}") from e

