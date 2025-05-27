from typing import Optional, Dict, Any
import logging
from listener.database import BaseDBHandler
from pydantic import BaseModel


class VideoMessageDBHandler(BaseDBHandler):
    MAX_INLINE_SIZE = 50_000_000  # 50MB - максимальный размер для хранения в таблице

    def __init__(self, db_connector):
        super().__init__(db_connector)
        self.logger = logging.getLogger(__name__)

    async def save_content(self, message: Any, video_content: BaseModel) -> bool:
        """
        Асинхронно сохраняет видео контент в базу данных

        Args:
            message: Родительское сообщение (должен содержать message_id и chat_id)
            video_content: Объект VideoMessage с данными видео

        Returns:
            bool: True если сохранение успешно
        """
        try:
            # Определяем способ хранения бинарных данных
            binary_data = getattr(video_content, 'video_bytes', None)
            if binary_data and len(binary_data) > self.MAX_INLINE_SIZE:
                binary_data = None
                self.logger.warning(
                    f"Video too large ({len(getattr(video_content, 'video_bytes', b''))} bytes), "
                    "storing without binary data"
                )

            # Подготовка данных миниатюры
            thumbnail_url = None
            if hasattr(video_content, 'thumbnail') and video_content.thumbnail:
                thumbnail_url = getattr(video_content.thumbnail, 'file_id', None)

            query = """
            INSERT INTO message_contents (
                message_id, chat_id, media_group_id, content_type, caption,
                file_id, file_unique_id, file_size, width, height,
                duration, mime_type, thumbnail_url, binary_data
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """
            params = (
                message.message_id,
                message.chat_id,
                getattr(message, 'media_group_id', None),
                'video',
                getattr(video_content, 'caption', None),
                video_content.file_id,
                getattr(video_content, 'file_unique_id', None),
                getattr(video_content, 'file_size', None),
                getattr(video_content, 'width', None),
                getattr(video_content, 'height', None),
                getattr(video_content, 'duration', None),
                getattr(video_content, 'mime_type', None),
                thumbnail_url,
                binary_data
            )

            success, _ = await self.db.execute_query(query, params)
            return success

        except Exception as e:
            self.logger.error(f"Ошибка сохранения видео: {str(e)}", exc_info=True)
            return False

    async def load_content(self, message_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Асинхронно загружает видео контент из базы данных

        Args:
            message_id: ID сообщения
            chat_id: ID чата

        Returns:
            Словарь с данными видео или None, если не найдено или произошла ошибка
        """
        try:
            query = """
            SELECT 
                caption, file_id, file_unique_id, file_size,
                width, height, duration, mime_type,
                thumbnail_url, binary_data, media_group_id
            FROM message_contents 
            WHERE message_id = $1 AND chat_id = $2 AND content_type = 'video'
            """
            success, result = await self.db.execute_query(query, (message_id, chat_id))

            if not success or not result:
                self.logger.debug(f"Video content not found for message {message_id} in chat {chat_id}")
                return None

            row = result[0]

            # Формируем словарь с данными видео
            video_data = {
                'caption': row[0],
                'file_id': row[1],
                'file_unique_id': row[2],
                'file_size': row[3],
                'width': row[4],
                'height': row[5],
                'duration': row[6],
                'mime_type': row[7],
                'thumbnail': {'file_id': row[8]} if row[8] else None,
                'video_bytes': row[9],
                'media_group_id': row[10]
            }

            # Удаляем None значения для чистоты данных
            return {k: v for k, v in video_data.items() if v is not None}

        except Exception as e:
            self.logger.error(f"Error loading video content: {str(e)}", exc_info=True)
            return None