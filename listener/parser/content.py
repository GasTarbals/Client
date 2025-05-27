import asyncio
from typing import Optional, List, Dict, Any, Union, Set
import logging
from telethon.tl.types import (
    Message, MessageMediaPhoto, MessageMediaDocument,
    DocumentAttributeVideo, DocumentAttributeAudio,
    DocumentAttributeAnimated, Document
)
from telethon.tl.custom import Message as CustomMessage
from schema import (
    TextMessage, PhotoMessage,
    VideoMessage, AudioMessage
)

class ContentAnalyzer:
    """Анализатор содержимого сообщений с поддержкой медиа-групп"""

    def __init__(self, converters: Dict[str, Any], logger: logging.Logger):
        self._converters = converters
        self.logger = logger

    async def extract_contents(
            self,
            message: Union[Message, CustomMessage],
            download_func: Optional[callable],
            load_media: bool,
            load_thumbnails: bool,
            processed_ids: Optional[Set[int]] = None
    ) -> List[Union[TextMessage, PhotoMessage, VideoMessage, AudioMessage]]:
        """Извлекает содержимое с информацией о медиа-группах"""
        processed_ids = processed_ids or set()
        if message.id in processed_ids:
            return []
        processed_ids.add(message.id)

        contents = []

        # Обработка текста (если есть)
        if text := getattr(message, 'message', None):
            if text_msg := self._converters['text'].convert(message):
                contents.append(text_msg)

        # Обработка медиа
        if hasattr(message, 'media'):
            media_contents = await self._process_media(
                message,
                download_func=download_func,
                load_media=load_media,
                load_thumbnails=load_thumbnails
            )

            # Добавляем информацию о медиа-группе если есть
            if (isinstance(message, Message) and
                    getattr(message, 'grouped_id', None)):
                group_id = message.grouped_id

                # Добавляем информацию о группе к каждому медиа
                for media in media_contents:
                    if hasattr(media, 'group_info'):
                        media.group_info = group_id

            contents.extend(media_contents)

        return contents

    async def _process_media(
            self,
            message: Union[Message, CustomMessage],
            *,
            download_func: Optional[callable] = None,
            load_media: bool = False,
            load_thumbnails: bool = True
    ) -> List[Union[PhotoMessage, VideoMessage, AudioMessage]]:
        """Обрабатывает медиа контент в сообщении"""
        media = getattr(message, 'media', None)
        if not media:
            return []

        result = []

        try:
            # Обработка фото
            if isinstance(media, MessageMediaPhoto) or getattr(message, 'photo', None):
                photo_msg = await self._converters['photo'].convert(
                    message,
                    download_func=download_func if load_media else None,
                    load_images=load_thumbnails,
                    load_best_only=True
                )
                if photo_msg:
                    result.append(photo_msg)

            # Обработка документов
            elif isinstance(media, MessageMediaDocument):
                doc_result = await self._process_document(
                    media.document,
                    message,
                    download_func=download_func,
                    load_media=load_media,
                    load_thumbnails=load_thumbnails
                )
                result.extend(doc_result)

        except Exception as e:
            self.logger.error(f"Media processing failed: {e}")

        return result

    async def _process_document(
            self,
            document: Optional[Document],
            message: Union[Message, CustomMessage],
            *,
            download_func: Optional[callable] = None,
            load_media: bool = False,
            load_thumbnails: bool = True
    ) -> List[Union[PhotoMessage, VideoMessage, AudioMessage]]:
        """Обрабатывает документы как медиа контент"""
        if not document or not hasattr(document, 'attributes'):
            return []

        try:
            # Видео
            if any(isinstance(a, DocumentAttributeVideo) for a in document.attributes):
                video_kwargs = {'download_func': download_func} if load_media else {}
                if video_msg := await self._converters['video'].convert(message, **video_kwargs):
                    return [video_msg]

            # Аудио
            elif any(isinstance(a, DocumentAttributeAudio) for a in document.attributes):
                if audio_msg := await self._converters['audio'].convert(message):
                    return [audio_msg]

            # Анимированные/GIF
            elif any(isinstance(a, DocumentAttributeAnimated) for a in document.attributes):
                photo_msg = await self._converters['photo'].convert(
                    message,
                    download_func=download_func if load_media else None,
                    load_images=load_thumbnails,
                    load_best_only=True
                )
                if photo_msg:
                    photo_msg.is_animated = True
                    return [photo_msg]

            # Обычные изображения
            elif getattr(document, 'mime_type', '').startswith('image/'):
                photo_msg = await self._converters['photo'].convert(
                    message,
                    download_func=download_func if load_media else None,
                    load_images=load_thumbnails,
                    load_best_only=True
                )
                if photo_msg:
                    return [photo_msg]

        except Exception as e:
            self.logger.error(f"Document processing error: {e}")

        return []