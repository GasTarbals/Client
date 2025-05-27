
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import timedelta
from typing import Optional, List, Dict
from enum import Enum

class VideoMessageType(str, Enum):
    REGULAR = "regular"
    NOTE = "video_note"
    SHORT = "short"
    ANIMATION = "animation"


class VideoQuality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UHD = "uhd"


class VideoThumbnail(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_id: str
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    file_size: Optional[int] = Field(None, gt=0)
    image_bytes: Optional[bytes] = None  # Храним только байты

class VideoMessage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Основные идентификаторы
    file_id: str
    file_unique_id: str

    # Видео характеристики
    duration: int = Field(
        ...,
        description="Длительность видео в секундах",
        ge=1,
        le=86400  # Максимум 24 часа
    )
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    fps: Optional[float] = Field(None, gt=0)
    codec: Optional[str] = None
    bitrate: Optional[int] = Field(None, gt=0)

    # Метаданные
    video_type: VideoMessageType = VideoMessageType.REGULAR
    mime_type: Optional[str] = None
    quality: VideoQuality = VideoQuality.MEDIUM
    is_animated: bool = False
    has_spoiler: bool = False

    # Контент
    video_bytes: Optional[bytes] = None
    thumbnail: Optional[VideoThumbnail] = None

    # Опциональные поля
    caption: Optional[str] = Field(None, max_length=1024)
    caption_entities: Optional[List[Dict]] = None
    file_size: Optional[int] = Field(None, gt=0)
    is_outgoing: bool = False
    views: Optional[int] = Field(None, ge=0)
    forwards: Optional[int] = Field(None, ge=0)
