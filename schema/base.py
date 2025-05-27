from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from enum import Enum, auto
import json
from schema.text import TextMessage
from schema.photo import PhotoMessage
from schema.video import VideoMessage
from schema.audio import AudioMessage


class MessageType(str, Enum):
    """Типы сообщений"""
    TEXT = "text"          # Текстовое сообщение
    PHOTO = "photo"        # Сообщение с фото
    VIDEO = "video"        # Сообщение с видео
    AUDIO = "audio"        # Аудиосообщение
    MIXED = "mixed"        # Комбинированное сообщение
    UNKNOWN = "unknown"    # Неизвестный тип


class ChatType(str, Enum):
    """Типы чатов"""
    PRIVATE = "private"     # Личный чат (private
    GROUP = "group"         # Группа
    CHANNEL = "channel"     # Канал
    SUPERGROUP = "supergroup"   # Супергруппа


class Message(BaseModel):
    """
    Универсальный класс для представления сообщений с поддержкой любых медиа-комбинаций.
    Может содержать текст, фото, видео и аудио в любых сочетаниях.
    """

    """
    Универсальный класс для представления сообщений с поддержкой любых медиа-комбинаций.
    """
    # User fields
    user_id: Optional[int] = Field(None, description="ID пользователя")
    username: Optional[str] = Field(None, description="Юзернейм пользователя")
    first_name: Optional[str] = Field(None, description="Имя пользователя")
    last_name: Optional[str] = Field(None, description="Фамилия пользователя")
    language_code: Optional[str] = Field(None, description="Код языка пользователя")
    is_bot: bool = Field(False, description="Является ли пользователь ботом")
    is_premium: bool = Field(False, description="Имеет ли Premium подписку")

    # Chat fields
    chat_id: int =  Field(..., description="Идентификатор чата (может быть отрицательным для каналов/групп)")
    chat_type: ChatType = Field(..., description="Тип чата")
    title: Optional[str] = Field(None, description="Название чата/группы")
    description: Optional[str] = Field(None, description="Описание чата/канала")
    invite_link: Optional[str] = Field(None, description="Ссылка-приглашение")

    # Message fields
    message_id: int = Field(..., gt=0, description="Уникальный идентификатор сообщения")
    text: Optional[str] = Field(None, description="Текст сообщения")
    message_type: str = Field(..., description="Тип сообщения")
    date: datetime = Field(..., description="Дата и время отправки")
    edit_date: Optional[datetime] = Field(None, description="Дата и время редактирования")
    is_outgoing: bool = Field(False, description="Исходящее ли сообщение")
    reply_to_message_id: Optional[int] = Field(None, gt=0, description="ID сообщения, на которое дан ответ")
    reply_to_chat_id: Optional[int] = Field(None, gt=0, description="ID чата сообщения, на которое дан ответ")
    forward_from: Optional[int] = Field(None, gt=0, description="ID оригинального отправителя")
    forward_from_chat: Optional[int] = Field(None, gt=0, description="ID оригинального чата")
    forward_date: Optional[datetime] = Field(None, description="Дата оригинального сообщения")
    via_bot_id: Optional[int] = Field(None, gt=0, description="ID бота, через которого отправлено")
    media_group_id: Optional[int] = Field(None, description="ID медиагруппы (для альбомов)")
    author_signature: Optional[str] = Field(None, description="Подпись автора (для каналов)")
    views: Optional[int] = Field(None, ge=0, description="Количество просмотров")
    forwards: Optional[int] = Field(None, ge=0, description="Количество пересылок")
    has_media_spoiler: bool = Field(False, description="Содержит ли спойлер для медиа")
    has_protected_content: bool = Field(False, description="Защищённое ли содержимое")


    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания записи")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления записи")

    # Содержимое сообщения (может быть несколько элементов разных типов)
    contents: List[Union[TextMessage, PhotoMessage, VideoMessage, AudioMessage]] = Field(
        default_factory=list,
        min_length=1,
        description="Список всего содержимого сообщения"
    )

    @property
    def message_type(self) -> MessageType:
        """Определяет основной тип сообщения на основе его содержимого"""
        content_types = {type(c) for c in self.contents}

        if not content_types:
            return MessageType.UNKNOWN

        if len(content_types) == 1:
            content_type = content_types.pop()
            if content_type == TextMessage:
                return MessageType.TEXT
            elif content_type == PhotoMessage:
                return MessageType.PHOTO
            elif content_type == VideoMessage:
                return MessageType.VIDEO
            elif content_type == AudioMessage:
                return MessageType.AUDIO

        return MessageType.MIXED

    @property
    def text_content(self) -> Optional[str]:
        """Возвращает первый текстовый контент, если он существует"""
        for content in self.contents:
            if isinstance(content, TextMessage):
                return content.text
        return None

    @property
    def captions(self) -> List[str]:
        """Возвращает все непустые подписи к медиа"""
        return [
            content.caption for content in self.contents
            if hasattr(content, 'caption') and content.caption
        ]

    def get_contents_of_type(self, content_type: type) -> List:
        """Возвращает всё содержимое указанного типа"""
        return [c for c in self.contents if isinstance(c, content_type)]

    def get_photos(self) -> List[PhotoMessage]:
        """Возвращает все фото из сообщения"""
        return self.get_contents_of_type(PhotoMessage)

    def get_videos(self) -> List[VideoMessage]:
        """Возвращает все видео из сообщения"""
        return self.get_contents_of_type(VideoMessage)

    def get_audios(self) -> List[AudioMessage]:
        """Возвращает все аудио из сообщения"""
        return self.get_contents_of_type(AudioMessage)

    def get_texts(self) -> List[TextMessage]:
        """Возвращает весь текстовый контент"""
        return self.get_contents_of_type(TextMessage)

    def has_media(self) -> bool:
        """Проверяет, содержит ли сообщение медиа"""
        return any(not isinstance(c, TextMessage) for c in self.contents)

    def is_forwarded(self) -> bool:
        """Проверяет, является ли сообщение пересланным"""
        return self.forward_from is not None

    def is_edited(self) -> bool:
        """Проверяет, редактировалось ли сообщение"""
        return self.edit_date is not None

    def to_json(self, indent: Optional[int] = None) -> str:
        """Сериализует сообщение в JSON с правильной обработкой дат"""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Десериализует сообщение из JSON"""
        return cls.model_validate_json(json_str)

    def add_content(self, content: Union[TextMessage, PhotoMessage, VideoMessage, AudioMessage]):
        """Добавляет новый контент в сообщение"""
        self.contents.append(content)

    def merge_message(self, other: 'Message'):
        """Объединяет содержимое с другим сообщением"""
        self.contents.extend(other.contents)
        if other.extra_metadata:
            self.extra_metadata.update(other.extra_metadata)