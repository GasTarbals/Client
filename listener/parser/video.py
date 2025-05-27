from telethon.tl.types import (
    Message,
    Document,
    DocumentAttributeVideo,
    MessageMediaDocument,
    PhotoSize,
    PhotoCachedSize
)
from typing import Optional
import logging
from schema.video import VideoMessage, VideoThumbnail


class VideoConverter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def convert(
            self,
            message: Message,
            download_func: Optional[callable] = None
    ) -> Optional[VideoMessage]:
        """Конвертирует Telegram сообщение в VideoMessage"""
        if not self._is_video_message(message):
            return None

        try:
            doc = message.media.document
            video_attrs = self._get_video_attributes(doc)

            caption = message.message or ""
            # Обрезаем подпись до 1024 символов
            truncated_caption = caption[:1024] if caption else None

            # Основные параметры видео
            video_data = {
                'file_id': str(doc.id),
                'file_unique_id': str(doc.access_hash),
                'duration': video_attrs.get('duration', 0),
                'width': video_attrs.get('width', 0),
                'height': video_attrs.get('height', 0),
                'mime_type': doc.mime_type,
                'file_size': doc.size,
                'caption': truncated_caption,
                'is_outgoing': message.out,
                'video_bytes': await download_func(doc) if download_func else None,
                'thumbnail': await self._get_thumbnail(doc, download_func) if download_func else None
            }

            return VideoMessage(**video_data)

        except Exception as e:
            self.logger.error(f"Video conversion error: {e}", exc_info=True)
            return None

    async def _get_thumbnail(
            self,
            document: Document,
            download_func: callable
    ) -> Optional[VideoThumbnail]:
        """Получает миниатюру видео"""
        if not hasattr(document, 'thumbs') or not document.thumbs:
            return None

        try:
            thumb = document.thumbs[0]

            # Для разных типов миниатюр используем разные подходы
            if isinstance(thumb, (PhotoSize, PhotoCachedSize)):
                # Получаем bytes миниатюры
                thumb_bytes = await download_func(document, thumb=thumb)

                return VideoThumbnail(
                    file_id=f"thumb_{document.id}_{thumb.type}",
                    width=getattr(thumb, 'w', 0),
                    height=getattr(thumb, 'h', 0),
                    file_size=len(thumb_bytes),
                    image_bytes=thumb_bytes
                )
            return None

        except Exception as e:
            self.logger.warning(f"Failed to get thumbnail: {e}")
            return None

    def _get_video_attributes(self, document: Document) -> dict:
        """Извлекает атрибуты видео"""
        attrs = {}
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                duration = max(1, int(getattr(attr, 'duration', 1)))  # Гарантируем минимум 1
                attrs.update({
                    'duration': duration,
                    'width': getattr(attr, 'w', 0),
                    'height': getattr(attr, 'h', 0)
                })
        return attrs

    def _is_video_message(self, message: Message) -> bool:
        """Проверяет, является ли сообщение видео"""
        return (
                isinstance(message.media, MessageMediaDocument) and
                hasattr(message.media, 'document') and
                any(isinstance(a, DocumentAttributeVideo)
                    for a in message.media.document.attributes)
        )