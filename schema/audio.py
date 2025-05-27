# Аудио сообщения
from datetime import datetime
from typing import Optional, Annotated
from pydantic import BaseModel, Field, UrlConstraints, HttpUrl


class AudioMessage(BaseModel):
    """
    Модель для представления аудио-сообщения Telegram.
    """
    file_id: str = Field(
        ...,
        description="Уникальный идентификатор аудиофайла в системе Telegram",
        min_length=10,
        max_length=255
    )
    file_unique_id: str = Field(
        ...,
        description="Уникальный идентификатор файла, который должен быть одинаковым для разных ботов",
        min_length=8,
        max_length=64
    )
    duration: int = Field(
        ...,
        description="Длительность аудио в секундах",
        ge=1,
        le=86400  # Максимум 24 часа
    )
    performer: Optional[str] = Field(
        None,
        description="Исполнитель аудио (если указан)",
        max_length=128
    )
    title: Optional[str] = Field(
        None,
        description="Название трека (если указано)",
        max_length=128
    )
    file_name: Optional[str] = Field(
        None,
        description="Имя исходного файла (если доступно)",
        max_length=255
    )
    mime_type: Optional[str] = Field(
        None,
        description="MIME-тип файла (если доступен)",
        max_length=64
    )
    file_size: Optional[int] = Field(
        None,
        description="Размер файла в байтах (если доступен)",
        ge=1
    )
    date: datetime = Field(
        ...,
        description="Дата и время отправки аудио-сообщения"
    )
    thumbnail_url: Optional[HttpUrl] = Field(
        None,
        description="URL обложки аудио (если доступна)"
    )
    audio_url: Optional[HttpUrl] = Field(
        None,
        description="URL для загрузки аудиофайла"
    )
