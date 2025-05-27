from datetime import datetime
from typing import Optional, Dict, Any
import logging
from listener.database import BaseDBHandler
from schema import PhotoMessage, Message, PhotoSize, PhotoSizeType


class PhotoMessageDBHandler(BaseDBHandler):
    MAX_INLINE_SIZE = 5_000_000  # 5MB - максимальный размер для хранения в таблице message_contents

    def __init__(self, db_connector):
        super().__init__(db_connector)
        self.logger = logging.getLogger(__name__)

    async def save_content(self, message: Message, photo_content: PhotoMessage) -> bool:
        """
        Сохраняет фото контент в базу данных с полным соответствием структуре PhotoMessage
        и схеме таблицы message_contents.
        """
        try:
            if not photo_content.photo:
                self.logger.warning("No photo sizes available to save")
                return False

            best_quality = photo_content.best_quality
            if not best_quality or not best_quality.file_id:
                self.logger.warning("No valid photo size found or missing file_id")
                return False

            binary_data = best_quality.image_data
            if binary_data and len(binary_data) > self.MAX_INLINE_SIZE:
                self.logger.warning(f"Photo size {len(binary_data)} exceeds max inline size, storing metadata only")
                binary_data = None

            # Явное преобразование числовых ID в строки
            file_id = str(best_quality.file_id)
            file_unique_id = str(best_quality.file_unique_id)

            # Подготовка параметров для запроса
            params = {
                'message_id': message.message_id,
                'chat_id': message.chat_id,
                'media_group_id': getattr(message, 'media_group_id', None),
                'content_type': 'photo',
                'caption': photo_content.caption,
                'file_id': file_id,
                'file_unique_id': file_unique_id,
                'file_size': best_quality.file_size,
                'width': best_quality.width,
                'height': best_quality.height,
                'binary_data': binary_data,
                'created_at': datetime.now()
            }

            # Проверка существования записи
            exists_query = """
            SELECT EXISTS(
                SELECT 1 FROM message_contents 
                WHERE message_id = $1 AND chat_id = $2 AND content_type = 'photo'
            )
            """

            success, exists_result = await self.db.execute_query(
                exists_query,
                (params['message_id'], params['chat_id'])
            )
            if not success:
                self.logger.error("Failed to check record existence")
                return False

            record_exists = exists_result[0]['exists'] if exists_result else False

            # Выбор соответствующего запроса
            if record_exists:
                query = """
                UPDATE message_contents SET
                    media_group_id = $3,
                    caption = $4,
                    file_id = $5,
                    file_unique_id = $6,
                    file_size = $7,
                    width = $8,
                    height = $9,
                    binary_data = $10,
                    created_at = NOW()
                WHERE message_id = $1 AND chat_id = $2 AND content_type = 'photo'
                """
                query_params = (
                    params['message_id'],
                    params['chat_id'],
                    params['media_group_id'],
                    params['caption'],
                    params['file_id'],
                    params['file_unique_id'],
                    params['file_size'],
                    params['width'],
                    params['height'],
                    params['binary_data']
                )
            else:
                query = """
                INSERT INTO message_contents (
                    message_id, chat_id, media_group_id, content_type,
                    caption, file_id, file_unique_id, file_size,
                    width, height, binary_data, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """
                query_params = tuple(params.values())

            success, _ = await self.db.execute_query(query, query_params)
            return success

        except Exception as e:
            self.logger.error(f"Error saving photo content: {str(e)}", exc_info=True)
            return False