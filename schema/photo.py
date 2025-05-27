from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum
import logging
from io import BytesIO
from PIL import Image  # Только для внутренней обработки


class PhotoSizeType(str, Enum):
    SMALL = "s"
    MEDIUM = "m"
    LARGE = "x"
    XLARGE = "y"
    HD = "w"


class PhotoSize(BaseModel):
    """Модель одного размера изображения (только данные, без PIL)"""

    file_id: str = Field(..., min_length=1, description="Идентификатор файла")
    file_unique_id: str = Field(..., min_length=1, description="Уникальный ID")
    width: int = Field(..., gt=0, le=20000, description="Ширина в пикселях")
    height: int = Field(..., gt=0, le=20000, description="Высота в пикселях")
    file_size: Optional[int] = Field(None, ge=0, description="Размер файла в байтах")
    type: Optional[PhotoSizeType] = Field(None, description="Тип размера")
    image_data: Optional[bytes] = Field(
        None,
        exclude=True,
        description="Бинарные данные изображения"
    )

class PhotoMessage(BaseModel):
    """Сообщение с изображением (без PIL, только bytes)"""

    photo: List[PhotoSize] = Field(..., min_length=1, description="Доступные размеры")
    caption: Optional[str] = Field(None, max_length=1024, description="Подпись")
    is_animated: bool = Field(False, description="Анимированное ли изображение")
    image_data: Optional[bytes] = Field(
        None,
        exclude=True,
        description="Бинарные данных основного изображения"
    )

    @property
    def best_quality(self) -> Optional[PhotoSize]:
        """Возвращает вариант с наилучшим качеством"""
        return max(self.photo, key=lambda x: x.width * x.height, default=None)

    def clear_images(self):
        """Очищает все изображения из памяти"""
        for size in self.photo:
            size.clear_image()
        self.image_data = None

    async def load_images(
            self,
            download_func: callable,
            load_main: bool = True,
            load_all_sizes: bool = False
    ):
        """
        Загружает изображения:
        - download_func: функция загрузки (например client.download_media)
        - load_main: загружать ли основное изображение
        - load_all_sizes: загружать ли все размеры
        """
        if load_main and self.best_quality:
            try:
                image_bytes = await download_func(self.best_quality.file_id)
                if image_bytes:
                    self.image_data = image_bytes
            except Exception as e:
                logging.error(f"Failed to load main image: {e}")

        if load_all_sizes:
            for size in self.photo:
                try:
                    image_bytes = await download_func(size.file_id)
                    if image_bytes:
                        size.load_from_bytes(image_bytes)
                except Exception as e:
                    logging.error(f"Failed to load size {size.type}: {e}")

    def get_image_as_pil(self) -> Optional[Image.Image]:
        """Временное получение PIL.Image (использовать только локально)"""
        if not self.image_data:
            return None
        try:
            return Image.open(BytesIO(self.image_data))
        except Exception as e:
            logging.error(f"Failed to create PIL image: {e}")
            return None

