from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Annotated
from enum import Enum
import base64
from pydantic.functional_validators import AfterValidator
from PIL import Image
import io
from typing import Tuple

class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


def validate_base64(v: str) -> str:
    """Валидатор для Base64 строк"""
    try:
        base64.b64decode(v, validate=True)
        return v
    except ValueError as e:
        raise ValueError(f"Invalid Base64 string: {e}")


# Аннотированный тип для Base64 данных
Base64Str = Annotated[str, AfterValidator(validate_base64)]




class MediaAttachment(BaseModel):
    """Модель медиавложения с Base64 кодированием и превью"""
    model_config = ConfigDict(extra='forbid')

    type: MediaType
    data_base64: Base64Str
    caption: Optional[str] = Field(None, max_length=1024)
    thumbnail_base64: Optional[Base64Str] = None  # Base64 превью

    @property
    def binary_data(self) -> bytes:
        return base64.b64decode(self.data_base64)

    @property
    def thumbnail_data(self) -> Optional[bytes]:
        return base64.b64decode(self.thumbnail_base64) if self.thumbnail_base64 else None

    @classmethod
    def generate_thumbnail(cls, binary_data: bytes, size: Tuple[int, int] = (200, 200)) -> bytes:
        """Генерирует превью для медиафайла"""
        try:
            img = Image.open(io.BytesIO(binary_data))
            img.thumbnail(size)

            with io.BytesIO() as output:
                img.save(output, format='JPEG')
                return output.getvalue()
        except Exception:
            # Если не удалось сгенерировать превью (не изображение/ошибка)
            return None

    @classmethod
    def from_binary(
            cls,
            media_type: MediaType,
            data: bytes,
            caption: Optional[str] = None,
            auto_generate_thumbnail: bool = True
    ) -> 'MediaAttachment':
        """Создает из бинарных данных с автоматическим созданием превью"""
        thumbnail = None
        if auto_generate_thumbnail and media_type in [MediaType.PHOTO, MediaType.VIDEO]:
            thumbnail = cls.generate_thumbnail(data)

        return cls(
            type=media_type,
            data_base64=base64.b64encode(data).decode('utf-8'),
            caption=caption,
            thumbnail_base64=base64.b64encode(thumbnail).decode('utf-8') if thumbnail else None
        )


class TelegramCommentSchema(BaseModel):
    """Модель комментария с улучшенной поддержкой медиа"""
    model_config = ConfigDict(extra='forbid')

    text: Optional[str] = Field(None, max_length=4096)
    media: Optional[MediaAttachment] = None

    @field_validator('media', mode='after')
    @classmethod
    def validate_media_content(cls, v):
        if v is not None and not v.data_base64:
            raise ValueError("Media data cannot be empty")
        return v

    def validate_content(self):
        if not self.text and not self.media:
            raise ValueError("Comment must contain either text or media")
        return True

    @classmethod
    def with_media(
            cls,
            media_type: MediaType,
            data: bytes,
            caption: Optional[str] = None,
            text: Optional[str] = None,
            thumbnail: Optional[bytes] = None
    ) -> 'TelegramCommentSchema':
        """Фабричный метод с возможностью указать превью"""
        return cls(
            text=text,
            media=MediaAttachment(
                type=media_type,
                data_base64=base64.b64encode(data).decode('utf-8'),
                caption=caption,
                thumbnail_base64=base64.b64encode(thumbnail).decode('utf-8') if thumbnail else None
            )
        )