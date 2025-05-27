from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin
from telethon.tl.types import (
    Message,
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    MessageMediaDocument
)

from schema.audio import AudioMessage


class AudioConverter:
    """Класс для преобразования аудио-сообщений из Telethon в AudioMessage"""

    def __init__(self, base_file_url: Optional[str] = None):
        """
        :param base_file_url: Базовый URL для доступа к файлам (если нужны прямые ссылки)
        """
        self.base_file_url = base_file_url

    async def convert(self, message: Message) -> Optional[AudioMessage]:
        """Преобразует сообщение Telethon в AudioMessage.
        Возвращает None, если сообщение не содержит аудио.
        """
        try:
            # Получаем документ с аудио
            document = await self._get_audio_document(message)
            if not document:
                return None

            # Парсим атрибуты
            attributes = self._parse_attributes(document.attributes)

            # Получаем URL превью
            thumbnail_url = await self._get_thumbnail_url(document)

            return AudioMessage(
                file_id=str(document.id),
                file_unique_id=str(document.access_hash),
                duration=attributes.get('duration', 0),
                performer=attributes.get('performer'),
                title=attributes.get('title'),
                file_name=attributes.get('file_name'),
                mime_type=document.mime_type,
                file_size=document.size,
                date=self._get_message_date(message),
                thumbnail_url=thumbnail_url,
                audio_url=self._get_audio_url(document) )
        except Exception as e:
            print(f"Error converting audio message: {e}")
            return None

    async def _get_audio_document(self, message: Message) -> Optional[Document]:
        """Извлекает аудио-документ из сообщения."""
        try:
            # Проверяем наличие медиа в сообщении
            if not hasattr(message, 'media') or not message.media:
                return None

            # Для медиа-документов
            if isinstance(message.media, MessageMediaDocument):
                document = message.media.document
                if isinstance(document, Document):
                    # Проверяем атрибуты на наличие аудио
                    for attr in document.attributes:
                        if isinstance(attr, DocumentAttributeAudio):
                            return document
            return None
        except Exception as e:
            print(f"Error getting audio document: {e}")
            return None

    def _parse_attributes(self, attributes: list) -> Dict[str, Any]:
        """Парсит атрибуты аудиофайла"""
        result = {
            'duration': 0,
            'performer': None,
            'title': None,
            'file_name': None
        }

        for attr in attributes:
            if isinstance(attr, DocumentAttributeAudio):
                result['duration'] = attr.duration
                if hasattr(attr, 'performer') and attr.performer:
                    result['performer'] = attr.performer
                if hasattr(attr, 'title') and attr.title:
                    result['title'] = attr.title
            elif isinstance(attr, DocumentAttributeFilename):
                result['file_name'] = attr.file_name

        return result

    def _get_message_date(self, message: Message) -> datetime:
        """Получает дату сообщения"""
        return message.date

    async def _get_thumbnail_url(self, document: Document) -> Optional[str]:
        """Генерирует URL для обложки"""
        try:
            if hasattr(document, 'thumbs') and document.thumbs:
                if self.base_file_url:
                    return urljoin(self.base_file_url, f"thumb/{document.id}")
        except Exception as e:
            print(f"Error getting thumbnail URL: {e}")
        return None

    def _get_audio_url(self, document: Document) -> Optional[str]:
        """Генерирует URL для аудиофайла"""
        if self.base_file_url:
            return urljoin(self.base_file_url, f"audio/{document.id}")
        return None