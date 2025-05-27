from typing import Optional, List, Any, Dict
import logging
from listener.database import BaseDBHandler
from schema import TextMessage, MessageEntity

class TextMessageDBHandler(BaseDBHandler):
    def __init__(self, db_connector):
        super().__init__(db_connector)
        self.logger = logging.getLogger(__name__)

    async def save_content(self, message: TextMessage, content: Any) -> bool:
        """Сохраняет текстовый контент в таблицу message_contents"""
        try:
            query = """
            INSERT INTO message_contents (
                message_id, chat_id, media_group_id, content_type, 
                text_content, caption
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """
            params = (
                message.message_id,
                message.chat_id,
                message.media_group_id,
                'text',
                content.text,
                getattr(content, 'caption', None)
            )

            success, _ = await self.db.execute_query(query, params)
            return success

        except Exception as e:
            self.logger.error(f"Ошибка сохранения текста: {str(e)}")
            return False

    async def load_content(self, message_id: int, chat_id: int) -> Optional[TextMessage]:
        """Полностью симметричный метод для загрузки текстового контента"""
        try:
            query = """
            SELECT text_content, caption, media_group_id
            FROM message_contents 
            WHERE message_id = $1 AND chat_id = $2 AND content_type = 'text'
            """
            success, result = await self.db.execute_query(query, (message_id, chat_id))

            if not success or not result:
                return None

            # Создаем объект TextMessage с минимально необходимыми полями
            text_message = TextMessage(
                text=result[0][0],
                entities=[],  # Восстановление entities потребует отдельной логики
                is_outgoing=False  # Это поле должно быть получено из другого источника
            )

            # Устанавливаем дополнительные поля
            if result[0][1]:  # caption
                setattr(text_message, 'caption', result[0][1])
            if result[0][2]:  # media_group_id
                setattr(text_message, 'media_group_id', result[0][2])

            return text_message

        except Exception as e:
            self.logger.error(f"Ошибка получения текста: {str(e)}", exc_info=True)
            return None


