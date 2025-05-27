from typing import Optional, List, Any, Dict, Union
import logging
from io import BytesIO
from PIL import Image  # Только для внутренней обработки размеров
from schema import PhotoMessage, PhotoSize, PhotoSizeType
from telethon.tl.types import (
    Message,
    Photo,
    Document,
    MessageMediaPhoto,
    MessageMediaDocument,
    DocumentAttributeAnimated,
    DocumentAttributeVideo
)



class PhotoConverter:
    def __init__(self, base_file_url: Optional[str] = None):
        """
        Инициализация конвертера фотографий

        Args:
            base_file_url: Базовый URL для доступа к файлам (опционально)
        """
        self.logger = logging.getLogger(f"{__name__}.PhotoConverter")
        self.base_file_url = base_file_url

        # Настройка логгера
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    async def convert(
            self,
            message: Message,
            download_func: Optional[callable] = None,
            load_images: bool = True,
            load_best_only: bool = True,
            max_size: Optional[int] = None
    ) -> Optional[PhotoMessage]:
        try:
            if not isinstance(message, Message):
                raise ValueError("Input must be a Telethon Message object")

            self.logger.debug(f"Converting message {message.id}")

            # Получаем медиа объект из сообщения
            media = getattr(message, 'media', None)
            if not media:
                return None

            # Конвертируем в PhotoMessage
            photo_msg = self._convert_message(message)
            if not photo_msg:
                return None

            # Загрузка изображений
            if load_images and download_func:
                await self._load_image_data(
                    photo_msg,
                    lambda file_id: download_func(media),  # Передаем медиа объект, а не file_id
                    load_best_only=load_best_only,
                    max_size=max_size
                )

            return photo_msg

        except Exception as e:
            self.logger.error(f"Conversion error: {str(e)}", exc_info=True)
            return None

    def _convert_message(self, message: Message) -> Optional[PhotoMessage]:
        """Базовая конвертация сообщения без загрузки медиа"""
        media = getattr(message, 'media', None)
        if not media:
            return None

        # Обработка фото
        if isinstance(media, MessageMediaPhoto) and hasattr(media, 'photo'):
            return self._convert_photo(media.photo, message.message)

        # Обработка документов (анимированные изображения)
        if isinstance(media, MessageMediaDocument) and hasattr(media, 'document'):
            document = media.document
            if self._is_animated_document(document):
                return self._convert_document_as_photo(document, message.message)

        return None

    def _convert_photo(self, photo: Photo, caption: Optional[str]) -> PhotoMessage:
        """Конвертация объекта Photo в PhotoMessage"""
        if not isinstance(photo, Photo):
            raise ValueError("Input must be a Photo object")

        sizes = self._get_photo_sizes(photo)
        if not sizes:
            sizes = [self._create_fallback_size(photo)]

        # Обрезаем подпись до 1024 символов
        truncated_caption = caption[:1024] if caption else None

        return PhotoMessage(
            photo=sizes,
            caption=truncated_caption,  # Используем обрезанную версию
            is_animated=self._is_animated(photo)
        )

    def _convert_document_as_photo(self, document: Document, caption: Optional[str]) -> PhotoMessage:
        """Конвертация документа в PhotoMessage"""
        sizes = [self._create_document_size(document)]

        # Обрезаем подпись до 1024 символов
        truncated_caption = caption[:1024] if caption else None

        return PhotoMessage(
            photo=sizes,
            caption=truncated_caption,  # Используем обрезанную версию
            is_animated=True
        )

    async def _load_image_data(
            self,
            photo_msg: PhotoMessage,
            download_func: callable,
            load_best_only: bool = True,
            max_size: Optional[int] = None
    ) -> None:
        """Загружает данные изображений"""
        try:
            if load_best_only:
                best_size = photo_msg.best_quality
                if best_size:
                    await self._load_single_image(best_size, download_func, max_size)
            else:
                for size in photo_msg.photo:
                    await self._load_single_image(size, download_func, max_size)

        except Exception as e:
            self.logger.error(f"Failed to load images: {str(e)}", exc_info=True)

    async def _load_single_image(
            self,
            photo_size: PhotoSize,
            download_func: callable,
            max_size: Optional[int] = None
    ) -> None:
        """Загружает данные одного изображения"""
        try:
            # В Telethon download_func обычно принимает объект медиа, а не file_id
            # Нужно либо передавать полный объект, либо использовать client.download_media
            image_bytes = await download_func(photo_size.file_id)  # Здесь может быть проблема

            if not image_bytes:
                self.logger.debug(f"No image data received for {photo_size.file_id}")
                return

            if max_size and len(image_bytes) > max_size:
                self.logger.warning(
                    f"Image too large ({len(image_bytes)} > {max_size}), skipping"
                )
                return

            # Обновляем размеры на основе реальных данных
            with Image.open(BytesIO(image_bytes)) as img:
                photo_size.width, photo_size.height = img.size

            photo_size.load_from_bytes(image_bytes)
            self.logger.debug(f"Successfully loaded image {photo_size.file_id}")

        except Exception as e:
            self.logger.error(f"Failed to load image {photo_size.file_id}: {str(e)}", exc_info=True)

    def _create_photo_size(self, photo: Photo, size: Any) -> PhotoSize:
        """Создает объект PhotoSize из данных Telethon"""
        return PhotoSize(
            file_id=self._generate_file_id(photo, size),
            file_unique_id=self._generate_file_unique_id(photo, size),
            width=getattr(size, 'w', 800),
            height=getattr(size, 'h', 600),
            file_size=getattr(size, 'size', None),
            type=self._determine_size_type(
                getattr(size, 'w', 800),
                getattr(size, 'h', 600)
            )
        )

    def _create_document_size(self, document: Document) -> PhotoSize:
        """Создает PhotoSize из документа"""
        width, height = 800, 600  # Значения по умолчанию
        for attr in getattr(document, 'attributes', []):
            if hasattr(attr, 'w') and hasattr(attr, 'h'):
                width, height = attr.w, attr.h
                break

        return PhotoSize(
            file_id=self._generate_document_id(document),
            file_unique_id=self._generate_document_unique_id(document),
            width=width,
            height=height,
            file_size=getattr(document, 'size', None),
            type=self._determine_size_type(width, height)
        )

    def _create_fallback_size(self, photo: Photo) -> PhotoSize:
        """Создает размер по умолчанию если нет доступных"""
        return PhotoSize(
            file_id=self._generate_file_id(photo),
            file_unique_id=self._generate_file_unique_id(photo),
            width=800,
            height=600,
            file_size=getattr(photo, 'size', None),
            type=PhotoSizeType.MEDIUM
        )

    def _determine_size_type(self, width: int, height: int) -> PhotoSizeType:
        """Определяет тип размера по ширине"""
        if width <= 320:
            return PhotoSizeType.SMALL
        elif width <= 800:
            return PhotoSizeType.MEDIUM
        elif width <= 1280:
            return PhotoSizeType.LARGE
        elif width <= 2560:
            return PhotoSizeType.XLARGE
        return PhotoSizeType.HD

    def _is_animated(self, photo: Photo) -> bool:
        """Проверяет, является ли фото анимированным"""
        return any(
            attr.__class__.__name__ == 'DocumentAttributeAnimated'
            for attr in getattr(photo, 'attributes', [])
        )

    def _is_animated_document(self, document: Document) -> bool:
        """Проверяет, является ли документ анимированным изображением"""
        if not isinstance(document, Document):
            return False

        # Проверка атрибутов анимации
        is_animated = any(
            isinstance(attr, (DocumentAttributeAnimated, DocumentAttributeVideo))
            for attr in getattr(document, 'attributes', [])
        )

        # Проверка mime type
        mime_type = getattr(document, 'mime_type', '')
        return is_animated or mime_type in ['image/gif', 'video/mp4']

    def _generate_file_id(self, photo: Photo, size: Any = None) -> str:
        """Генерирует file_id для фото"""
        parts = [str(photo.id), str(getattr(photo, 'access_hash', ''))]
        if size and hasattr(size, 'location'):
            loc = size.location
            parts.extend([
                str(getattr(loc, 'volume_id', '')),
                str(getattr(loc, 'local_id', ''))
            ])
        return '-'.join(parts) or 'default_file_id'

    def _generate_document_id(self, document: Document) -> str:
        """Генерирует file_id для документа"""
        parts = [str(document.id), str(getattr(document, 'access_hash', ''))]
        return '-'.join(parts) or 'default_document_id'

    def _generate_file_unique_id(self, photo: Photo, size: Any = None) -> str:
        """Генерирует уникальный file_id"""
        parts = [
            str(photo.id),
            str(getattr(photo, 'access_hash', '')),
            str(getattr(size, 'type', ''))
        ]

        if hasattr(size, 'location'):
            loc = size.location
            parts.extend([
                str(getattr(loc, 'volume_id', '')),
                str(getattr(loc, 'local_id', ''))
            ])

        return '-'.join(filter(None, parts)) or 'default_unique_id'

    def _generate_document_unique_id(self, document: Document) -> str:
        """Генерирует уникальный file_id для документа"""
        parts = [
            str(document.id),
            str(getattr(document, 'access_hash', '')),
            str(getattr(document, 'version', 0))
        ]
        return '-'.join(filter(None, parts)) or 'default_document_unique_id'

    async def batch_convert(
            self,
            messages: List[Message],
            download_func: Optional[callable] = None,
            load_images: bool = True,
            max_workers: int = 5
    ) -> List[PhotoMessage]:
        results = []
        for msg in messages:
            try:
                converted = await self.convert(
                    msg,
                    download_func=download_func,
                    load_images=load_images
                )
                if converted:
                    results.append(converted)
            except Exception as e:
                self.logger.error(f"Failed to convert message {msg.id}: {str(e)}")
        return results  # Исправлено: было 'result'

    def _get_photo_sizes(self, photo: Photo) -> List[PhotoSize]:
        """Получает все доступные размеры фото"""
        sizes = []
        if not hasattr(photo, 'sizes') or not photo.sizes:
            self.logger.debug("No photo sizes available")
            return sizes

        for size in photo.sizes:
            try:
                # Пропускаем нестандартные типы размеров
                if size.__class__.__name__ in ['PhotoStrippedSize', 'PhotoSizeProgressive']:
                    continue

                sizes.append(self._create_photo_size(photo, size))
            except Exception as e:
                self.logger.warning(f"Skipping invalid photo size {type(size)}: {str(e)}")

        return sizes