from typing import Optional, List, Dict, Any, Union, Set, TypeVar
from datetime import datetime
import logging
from telethon.tl.types import (
    Message, MessageMediaPhoto, MessageMediaDocument,
    DocumentAttributeVideo, DocumentAttributeAudio,
    DocumentAttributeAnimated, Document, User, Channel, Chat
)
from telethon.tl.custom import Message as CustomMessage
from schema import (
    Message as UnifiedMessage, TextMessage, PhotoMessage,
    VideoMessage, AudioMessage, ChatType, MessageType
)
from listener.parser import TextConverter, PhotoConverter, VideoConverter, AudioConverter, ContentAnalyzer

T = TypeVar('T', Message, CustomMessage)


class MessageConverter:
    """Оптимизированный конвертер сообщений с поддержкой медиа-групп"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._converters = {
            'text': TextConverter(),
            'photo': PhotoConverter(),
            'video': VideoConverter(),
            'audio': AudioConverter()
        }
        self._content_analyzer = ContentAnalyzer(self._converters, self.logger)

    async def convert(
            self,
            message: Union[Message, CustomMessage],
            *,
            download_func: Optional[callable] = None,
            load_media: bool = False,
            load_thumbnails: bool = True
    ) -> Optional[UnifiedMessage]:
        """Основной метод конвертации сообщения

        Args:
            message: Входящее сообщение для конвертации
            download_func: Функция для загрузки медиа
            load_media: Загружать ли медиа-контент
            load_thumbnails: Загружать ли превью

        Returns:
            UnifiedMessage или None в случае ошибки
        """
        try:
            if not isinstance(message, (Message, CustomMessage)):
                self.logger.warning(f"Invalid message type: {type(message)}")
                return None

            contents = await self._content_analyzer.extract_contents(
                message,
                download_func=download_func,
                load_media=load_media,
                load_thumbnails=load_thumbnails
            )
            if not contents:
                self.logger.debug(f"Message {getattr(message, 'id', '?')} has no contents")
                return None

            metadata = await self._extract_metadata(message)
            if not metadata:
                self.logger.warning(f"Failed to extract metadata for message {getattr(message, 'id', '?')}")
                return None

            return UnifiedMessage(
                **metadata,
                contents=contents,
                message_type=self._determine_message_type(contents),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        except Exception as e:
            self.logger.error(f"Failed to convert message {getattr(message, 'id', '?')}: {str(e)}", exc_info=True)
            return None

    async def _extract_metadata(
            self,
            message: Union[Message, CustomMessage]
    ) -> Dict[str, Any]:
        """Извлекает метаданные сообщения"""
        try:
            user_info = await self._get_user_info(message)
            chat_info = self._get_chat_info(message)

            # Обрабатываем forward_from и forward_from_chat отдельно
            forward_from = self._get_forward_info(message, 'from_id')
            forward_from_chat = self._get_forward_info(message, 'channel_id', 'chat_id')

            return {
                **user_info,
                **chat_info,
                'message_id': abs(getattr(message, 'id', 0)),
                'text': getattr(message, 'message', ''),
                'date': getattr(message, 'date', datetime.now()),
                'edit_date': getattr(message, 'edit_date', None),
                'is_outgoing': getattr(message, 'out', False),
                'reply_to_message_id': self._get_reply_id(message),
                'forward_from': forward_from if isinstance(forward_from, int) else None,
                'forward_from_chat': forward_from_chat if isinstance(forward_from_chat, int) else None,
                'forward_date': getattr(getattr(message, 'fwd_from', None), 'date', None),
                'via_bot_id': getattr(message, 'via_bot_id', None),
                'media_group_id': getattr(message, 'grouped_id', None),
                'author_signature': getattr(message, 'post_author', None),
                'views': getattr(message, 'views', 0),
                'forwards': getattr(message, 'forwards', 0),
                'has_media_spoiler': getattr(getattr(message, 'media', None), 'spoiler', False),
                'has_protected_content': bool(getattr(message, 'noforwards', False))
            }
        except Exception as e:
            self.logger.error(f"Metadata extraction failed: {str(e)}", exc_info=True)
            return {}

    async def _get_user_info(self, message: Union[Message, CustomMessage]) -> Dict[str, Any]:
        """Извлекает базовую информацию о пользователе из сообщения.

        Args:
            message: Объект сообщения Telethon

        Returns:
            Словарь с обязательными полями:
            - user_id: int или None
            - username: str или ''
            - first_name: str или ''
            - last_name: str или ''
            - language_code: str или ''
            - is_bot: bool
            - is_premium: bool
        """
        result = {
            'user_id': None,
            'username': '',
            'first_name': '',
            'last_name': '',
            'language_code': '',
            'is_bot': False,
            'is_premium': False
        }

        try:
            # Пытаемся получить sender самым эффективным способом
            sender = getattr(message, 'sender', None)
            if sender is None and hasattr(message, 'get_sender'):
                try:
                    sender = await message.get_sender()
                except (ValueError, TypeError):
                    pass

            # Заполняем данные из sender, если это User
            if isinstance(sender, User):
                result.update({
                    'user_id': sender.id,
                    'username': sender.username or '',
                    'first_name': sender.first_name or '',
                    'last_name': sender.last_name or '',
                    'is_bot': sender.bot,
                    'is_premium': getattr(sender, 'premium', False)
                })

                # language_code может быть не у всех пользователей
                if hasattr(sender, 'lang_code'):
                    result['language_code'] = sender.lang_code or ''

            # Если не получили sender, пробуем альтернативные способы получить user_id
            if result['user_id'] is None:
                if hasattr(message, 'sender_id') and message.sender_id:
                    result['user_id'] = message.sender_id
                elif hasattr(message, 'from_id'):
                    from_id = message.from_id
                    if hasattr(from_id, 'user_id') and from_id.user_id:
                        result['user_id'] = from_id.user_id


        except Exception as e:
            self.logger.debug(f"User info extraction warning: {str(e)}")
            # В случае ошибки возвращаем то, что успели собрать

        return result

    def _get_chat_info(self, message: T) -> Dict[str, Any]:
        """Извлекает информацию о чате"""
        try:
            chat_type = self._determine_chat_type(message)
            chat_id = self._get_chat_id(message)
            info = {'chat_id': chat_id, 'chat_type': chat_type}

            if chat := getattr(message, 'chat', None):
                if isinstance(chat, (Channel, Chat)):
                    info.update({
                        'title': chat.title or '',
                        'description': getattr(chat, 'about', ''),
                        'invite_link': getattr(chat, 'username', '')
                    })
            return info
        except Exception as e:
            self.logger.warning(f"Chat info extraction failed: {e}")
            return {'chat_id': 0, 'chat_type': ChatType.PRIVATE}

    def _determine_chat_type(self, message: T) -> ChatType:
        """Определяет тип чата"""
        if isinstance(message, CustomMessage):
            if message.is_private: return ChatType.PRIVATE
            if message.is_group: return ChatType.GROUP
            if message.is_channel: return ChatType.CHANNEL
            return ChatType.PRIVATE

        peer = getattr(message, 'peer_id', None)
        if not peer: return ChatType.PRIVATE

        if hasattr(peer, 'channel_id'): return ChatType.CHANNEL
        if hasattr(peer, 'chat_id'): return ChatType.GROUP
        if hasattr(peer, 'user_id'): return ChatType.PRIVATE
        return ChatType.PRIVATE

    def _get_chat_id(self, message: T) -> int:
        """Получает ID чата"""
        if isinstance(message, CustomMessage):
            return message.chat_id

        peer = getattr(message, 'peer_id', None)
        if not peer: return 0

        if hasattr(peer, 'channel_id'): return peer.channel_id
        if hasattr(peer, 'chat_id'): return peer.chat_id
        if hasattr(peer, 'user_id'): return peer.user_id
        return 0

    def _get_reply_id(self, message: T) -> Optional[int]:
        """Получает ID сообщения, на которое идет ответ"""
        try:
            if isinstance(message, CustomMessage):
                return message.reply_to_msg_id

            reply_to = getattr(message, 'reply_to', None)
            return getattr(reply_to, 'reply_to_msg_id', None) if reply_to else None
        except Exception as e:
            self.logger.debug(f"Reply ID extraction failed: {e}")
            return None

    def _get_forward_info(self, message: T, *attrs: str) -> Optional[int]:
        """Универсальный метод для получения информации о пересылке"""
        try:
            fwd = getattr(message, 'fwd_from', None)
            if not fwd:
                return None

            for attr in attrs:
                if hasattr(fwd, attr):
                    value = getattr(fwd, attr)
                    # Если это Peer объект, извлекаем ID
                    if hasattr(value, 'channel_id'):
                        return value.channel_id
                    if hasattr(value, 'chat_id'):
                        return value.chat_id
                    if hasattr(value, 'user_id'):
                        return value.user_id
                    return value
                if hasattr(getattr(fwd, 'from_id', None), attr):
                    value = getattr(fwd.from_id, attr)
                    if hasattr(value, 'channel_id'):
                        return value.channel_id
                    if hasattr(value, 'chat_id'):
                        return value.chat_id
                    if hasattr(value, 'user_id'):
                        return value.user_id
                    return value
        except Exception as e:
            self.logger.debug(f"Forward info extraction failed: {e}")

        return None

    def _determine_message_type(self, contents: List) -> MessageType:
        """Определяет тип сообщения на основе его содержимого"""
        if not contents:
            return MessageType.UNKNOWN

        content_types = {
            TextMessage: MessageType.TEXT,
            PhotoMessage: MessageType.PHOTO,
            VideoMessage: MessageType.VIDEO,
            AudioMessage: MessageType.AUDIO
        }

        types = {content_types.get(type(c)) for c in contents if type(c) in content_types}
        if not types:
            return MessageType.UNKNOWN
        if len(types) > 1:
            return MessageType.MIXED

        return types.pop()

    async def batch_convert(
            self,
            messages: List[Union[Message, CustomMessage]],
            **kwargs
    ) -> List[UnifiedMessage]:
        """Пакетная конвертация сообщений

        Args:
            messages: Список сообщений для конвертации
            **kwargs: Аргументы для convert()

        Returns:
            Список сконвертированных UnifiedMessage
        """
        contents_list = await self._content_analyzer.batch_extract_contents(
            messages,
            download_func=kwargs.get('download_func'),
            load_media=kwargs.get('load_media', False),
            load_thumbnails=kwargs.get('load_thumbnails', True)
        )

        results = []
        for i, contents in enumerate(contents_list):
            if not contents:
                continue

            try:
                msg = messages[i] if i < len(messages) else None
                if not msg:
                    continue

                metadata = await self._extract_metadata(msg)
                if not metadata:
                    continue

                results.append(UnifiedMessage(
                    **metadata,
                    contents=contents,
                    message_type=self._determine_message_type(contents),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ))
            except Exception as e:
                self.logger.error(f"Failed to convert message in batch: {str(e)}", exc_info=True)

        return results
