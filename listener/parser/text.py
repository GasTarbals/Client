from typing import Optional, List, Dict
from datetime import datetime
from telethon.tl.types import Message, MessageEntityUrl, MessageEntityTextUrl, MessageEntityMentionName
from telethon.tl.types import MessageEntityBold, MessageEntityItalic
from schema.text import MessageEntity, MessageEntityType
from schema import TextMessage


class TextConverter:
    """Конвертер сообщений Telethon в TextMessage"""

    def convert(self, message: Message) -> TextMessage:
        """Основной метод преобразования"""
        if not message.message:
            raise ValueError("Message doesn't contain text content")

        return TextMessage(
            is_outgoing=message.out,
            text=message.message,
            entities=self._parse_entities(message.entities),
            reply_to_message_id=self._get_reply_to_id(message),
            forward_from=self._get_forward_from(message),
            forward_date=self._get_forward_date(message),
            link_preview=self._parse_link_preview(message),
            via_bot=message.via_bot_id,
            edit_date=message.edit_date
        )

    def _get_chat_id(self, message: Message) -> int:
        """Получает ID чата из сообщения.

        Args:
            message: Объект сообщения Telethon.

        Returns:
            ID чата.

        Raises:
            ValueError: Если не удается определить ID чата.
        """
        if hasattr(message.peer_id, 'user_id'):
            return message.peer_id.user_id
        elif hasattr(message.peer_id, 'channel_id'):
            return message.peer_id.channel_id
        elif hasattr(message.peer_id, 'chat_id'):
            return message.peer_id.chat_id
        raise ValueError("Could not determine chat ID from message")

    def _parse_entities(self, entities) -> Optional[List[MessageEntity]]:
        """Преобразует entities из Telethon в наш формат"""
        if not entities:
            return None

        result = []
        for entity in entities:
            entity_type = self._map_entity_type(entity)
            if not entity_type:
                continue

            new_entity = {
                'type': entity_type,
                'offset': entity.offset,
                'length': entity.length
            }

            if isinstance(entity, MessageEntityTextUrl):
                new_entity['url'] = entity.url
            elif isinstance(entity, MessageEntityMentionName):
                new_entity['user_id'] = entity.user_id

            result.append(MessageEntity(**new_entity))

        return result if result else None

    def _map_entity_type(self, entity) -> Optional[MessageEntityType]:
        """Сопоставляет типы entities Telethon с MessageEntityType.

        Поддерживаемые типы:
            - URL (MessageEntityUrl)
            - TEXT_LINK (MessageEntityTextUrl)
            - BOLD (MessageEntityBold)
            - ITALIC (MessageEntityItalic)
        """
        if isinstance(entity, MessageEntityUrl):
            return MessageEntityType.URL
        elif isinstance(entity, MessageEntityTextUrl):
            return MessageEntityType.TEXT_LINK
        elif isinstance(entity, MessageEntityBold):
            return MessageEntityType.BOLD
        elif isinstance(entity, MessageEntityItalic):
            return MessageEntityType.ITALIC
        # Добавьте другие типы по мере необходимости
        return None

    def _get_forward_from(self, message: Message) -> Optional[int]:
        """Получает ID оригинального отправителя для пересланных сообщений"""
        if message.fwd_from and message.fwd_from.from_id:
            if hasattr(message.fwd_from.from_id, 'user_id'):
                return message.fwd_from.from_id.user_id
        return None

    def _get_forward_date(self, message: Message) -> Optional[datetime]:
        """Получает дату оригинального сообщения"""
        if message.fwd_from and hasattr(message.fwd_from, 'date'):
            return message.fwd_from.date
        return None

    def _parse_link_preview(self, message: Message) -> Optional[Dict]:
        """Обрабатывает превью ссылок"""
        if not message.media:
            return None

        # Здесь можно добавить логику обработки превью
        return None

    def _get_reply_to_id(self, message: Message) -> Optional[int]:
        """Получает ID сообщения, на которое идет ответ"""
        if hasattr(message, 'reply_to') and hasattr(message.reply_to, 'reply_to_msg_id'):
            return message.reply_to.reply_to_msg_id
        return None