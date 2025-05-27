# Текстовые сообщения
from pydantic import BaseModel, Field, validator, field_validator
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import re


class MessageEntityType(str, Enum):
    """Типы форматирования текста в Telegram"""
    MENTION = "mention"
    HASHTAG = "hashtag"
    CASHTAG = "cashtag"
    BOT_COMMAND = "bot_command"
    URL = "url"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    SPOILER = "spoiler"
    CODE = "code"
    PRE = "pre"
    TEXT_LINK = "text_link"
    TEXT_MENTION = "text_mention"


class MessageEntity(BaseModel):
    """Модель форматирования текста"""
    type: MessageEntityType
    offset: int = Field(..., ge=0)
    length: int = Field(..., gt=0)
    url: Optional[str] = None  # Только для TEXT_LINK
    user_id: Optional[int] = None  # Только для TEXT_MENTION

    @field_validator('url')
    def validate_url(cls, v):
        if v and not re.match(r'^https?://\S+$', v):
            raise ValueError('Invalid URL format')
        return v


class TextMessage(BaseModel):
    """Модель текстового сообщения Telegram с полной валидацией"""
    # Базовые метаданные
    is_outgoing: bool = Field(False, description="Исходящее ли сообщение")

    # Текст и форматирование
    text: str = Field(..., max_length=4096, description="Текст сообщения")
    entities: Optional[List[MessageEntity]] = Field(
        None,
        description="Специальные форматирования в тексте"
    )

    # Контекст сообщения
    reply_to_message_id: Optional[int] = Field(
        None, gt=0, description="ID сообщения, на которое отвечаем"
    )
    forward_from: Optional[int] = Field(
        None, gt=0, description="ID оригинального отправителя (для пересланных)"
    )
    forward_date: Optional[datetime] = Field(
        None, description="Дата оригинального сообщения (для пересланных)"
    )

    # Дополнительные данные
    link_preview: Optional[Dict] = Field(
        None, description="Превращение ссылки в превью"
    )
    via_bot: Optional[int] = Field(
        None, gt=0, description="ID бота, через которого отправлено"
    )
    edit_date: Optional[datetime] = Field(
        None, description="Дата последнего редактирования"
    )