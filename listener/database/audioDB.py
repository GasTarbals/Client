from listener.database import BaseDBHandler
from typing import Optional, Awaitable

class AudioMessageDBHandler(BaseDBHandler):
    async def save_content(self, message, audio_content) -> Optional[int]:
        """Асинхронно сохраняет аудио контент в БД"""
        try:
            query = """
            INSERT INTO message_contents (
                message_id, chat_id, content_type,
                file_id, file_unique_id, file_size, duration,
                mime_type, performer, title, thumbnail_url
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING content_id
            """
            params = (
                message.message_id, message.chat_id, "audio",
                audio_content.file_id, audio_content.file_unique_id,
                audio_content.file_size, audio_content.duration,
                audio_content.mime_type, audio_content.performer,
                audio_content.title, audio_content.thumbnail_url
            )

            success, result = await self.db.execute_query(query, params)
            return result[0][0] if success and result else None

        except Exception as e:
            self.logger.error(f"Audio save error: {str(e)}", exc_info=True)
            return None