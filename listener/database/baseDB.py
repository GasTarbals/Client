from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from schema import Message, TextMessage, PhotoMessage, VideoMessage, AudioMessage, ChatType
from listener.database import (
    TextMessageDBHandler,
    PhotoMessageDBHandler,
    VideoMessageDBHandler,
    AudioMessageDBHandler,
    BaseDBHandler
)
from listener.database.connectDB import PostgreSQLConnector

class TelegramMessageHandler:
    def __init__(self, db_connector: PostgreSQLConnector):
        self.db = db_connector
        self.logger = logging.getLogger(__name__)

        self.handlers = {
            "text": TextMessageDBHandler(db_connector),
            "photo": PhotoMessageDBHandler(db_connector),
            "video": VideoMessageDBHandler(db_connector),
            "audio": AudioMessageDBHandler(db_connector)
        }

    async def save_message(self, message: Message) -> bool:
        """Основной асинхронный метод сохранения сообщения"""
        try:
            # 1. Гарантируем существование чата
            if not await self._ensure_chat_exists(message):
                self.logger.error(f"Не удалось создать/найти чат {message.chat_id}")
                return False

            # 2. Гарантируем существование пользователя
            if message.user_id and not await self._ensure_user_exists(message):
                self.logger.error(f"Не удалось создать/найти пользователя {message.user_id}")
                return False

            # 3. Сохраняем метаданные сообщения
            if not await self._save_message_metadata(message):
                return False

            # 4. Сохраняем содержимое сообщения

            return await self._save_message_contents(message)

        except Exception as e:
            self.logger.error(f"Ошибка сохранения сообщения {message.message_id}: {str(e)}", exc_info=True)
            return False

    async def _ensure_chat_exists(self, message: Message) -> bool:
        """Асинхронно гарантирует существование чата"""
        try:
            query = """
            INSERT INTO chats (
                chat_id, chat_type, title, description, invite_link, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id) DO UPDATE SET
                chat_type = EXCLUDED.chat_type,
                title = COALESCE(EXCLUDED.title, chats.title),
                description = COALESCE(EXCLUDED.description, chats.description),
                invite_link = COALESCE(EXCLUDED.invite_link, chats.invite_link),
                updated_at = EXCLUDED.updated_at
            RETURNING 1
            """
            now = datetime.now()
            params = (
                message.chat_id,
                message.chat_type.value if isinstance(message.chat_type, ChatType) else message.chat_type,
                message.title,
                message.description,
                message.invite_link,
                now,
                now
            )
            success, _ = await self.db.execute_query(query, params)
            return success
        except Exception as e:
            self.logger.error(f"Ошибка при создании/обновлении чата {message.chat_id}: {str(e)}")
            return False

    async def _ensure_user_exists(self, message: Message) -> bool:
        """Асинхронно гарантирует существование пользователя"""
        try:
            query = """
            INSERT INTO users (
                user_id, username, first_name, last_name, language_code, 
                is_bot, is_premium, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                language_code = COALESCE(EXCLUDED.language_code, users.language_code),
                is_bot = COALESCE(EXCLUDED.is_bot, users.is_bot),
                is_premium = COALESCE(EXCLUDED.is_premium, users.is_premium),
                updated_at = EXCLUDED.updated_at
            RETURNING 1
            """
            now = datetime.now()
            params = (
                message.user_id,
                message.username,
                message.first_name,
                message.last_name,
                message.language_code,
                message.is_bot,
                message.is_premium,
                now,
                now
            )
            success, _ = await self.db.execute_query(query, params)
            return success
        except Exception as e:
            self.logger.error(f"Ошибка при создании/обновлении пользователя {message.user_id}: {str(e)}")
            return False

    async def _save_message_metadata(self, message: Message) -> bool:
        """Асинхронно сохраняет метаданные сообщения"""
        try:
            query = """
            INSERT INTO messages (
                message_id, chat_id, user_id, text, message_type, date, edit_date,
                is_outgoing, reply_to_message_id, reply_to_chat_id, forward_from,
                forward_from_chat, forward_date, via_bot_id, media_group_id,
                author_signature, views, forwards, has_media_spoiler,
                has_protected_content, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, 
                $16, $17, $18, $19, $20, $21
            )
            ON CONFLICT (message_id, chat_id) DO UPDATE SET
                text = COALESCE(EXCLUDED.text, messages.text),
                edit_date = COALESCE(EXCLUDED.edit_date, messages.edit_date),
                views = COALESCE(EXCLUDED.views, messages.views),
                forwards = COALESCE(EXCLUDED.forwards, messages.forwards)
            RETURNING 1
            """
            params = (
                message.message_id,
                message.chat_id,
                message.user_id,
                message.text,
                message.message_type.value if hasattr(message.message_type, 'value') else message.message_type,
                message.date,
                message.edit_date,
                message.is_outgoing,
                message.reply_to_message_id,
                message.reply_to_chat_id,
                message.forward_from,
                message.forward_from_chat,
                message.forward_date,
                message.via_bot_id,
                message.media_group_id,
                message.author_signature,
                message.views,
                message.forwards,
                message.has_media_spoiler,
                message.has_protected_content,
                datetime.now()
            )
            success, _ = await self.db.execute_query(query, params)
            return success
        except Exception as e:
            self.logger.error(f"Ошибка сохранения метаданных сообщения {message.message_id}: {str(e)}")
            return False

    async def _save_message_contents(self, message: Message) -> bool:
        """Асинхронно сохраняет содержимое сообщения"""
        for content in message.contents:
            content_type = self._get_content_type(content)
            if not content_type:
                self.logger.error(f"Неизвестный тип контента: {type(content)}")
                return False

            handler = self.handlers.get(content_type)
            if not handler:
                self.logger.error(f"Нет обработчика для типа {content_type}")
                return False

            if not await handler.save_content(message, content):
                self.logger.error(f"Ошибка сохранения контента типа {content_type}")
                return False
            self.logger.debug(f"Сохранено сообщение {message.text}")
        return True

    def _get_content_type(self, content) -> Optional[str]:
        """Определяет тип контента (синхронный метод)"""
        if isinstance(content, TextMessage):
            return "text"
        elif isinstance(content, PhotoMessage):
            return "photo"
        elif isinstance(content, VideoMessage):
            return "video"
        elif isinstance(content, AudioMessage):
            return "audio"
        return None

    async def load_message(self, message_id: int, chat_id: int) -> Optional[Message]:
        """
        Асинхронно загружает сообщение из базы данных, включая все его содержимое

        Args:
            message_id: ID сообщения
            chat_id: ID чата

        Returns:
            Объект Message или None, если сообщение не найдено или произошла ошибка
        """
        try:
            # 1. Загружаем метаданные сообщения
            message_meta = await self._load_message_metadata(message_id, chat_id)
            if not message_meta:
                self.logger.debug(f"Message {message_id} not found in chat {chat_id}")
                return None

            # 2. Загружаем информацию о чате
            chat_info = await self._load_chat_info(chat_id)
            if not chat_info:
                self.logger.warning(f"Chat {chat_id} not found for message {message_id}")
                return None

            # 3. Загружаем информацию о пользователе (если есть)
            user_info = None
            if message_meta['user_id']:
                user_info = await self._load_user_info(message_meta['user_id'])

            # 4. Загружаем содержимое сообщения
            contents = await self._load_message_contents(message_id, chat_id)
            if contents is None:  # None означает ошибку, пустой список - сообщение без контента
                return None

            # 5. Собираем объект Message
            return Message(
                message_id=message_id,
                chat_id=chat_id,
                chat_type=chat_info['chat_type'],
                user_id=message_meta['user_id'],
                username=user_info['username'] if user_info else None,
                first_name=user_info['first_name'] if user_info else None,
                last_name=user_info['last_name'] if user_info else None,
                language_code=user_info['language_code'] if user_info else None,
                is_bot=user_info['is_bot'] if user_info else False,
                is_premium=user_info['is_premium'] if user_info else False,
                title=chat_info['title'],
                description=chat_info['description'],
                invite_link=chat_info['invite_link'],
                text=message_meta['text'],
                message_type=message_meta['message_type'],
                date=message_meta['date'],
                edit_date=message_meta['edit_date'],
                is_outgoing=message_meta['is_outgoing'],
                reply_to_message_id=message_meta['reply_to_message_id'],
                reply_to_chat_id=message_meta['reply_to_chat_id'],
                forward_from=message_meta['forward_from'],
                forward_from_chat=message_meta['forward_from_chat'],
                forward_date=message_meta['forward_date'],
                via_bot_id=message_meta['via_bot_id'],
                media_group_id=message_meta['media_group_id'],
                author_signature=message_meta['author_signature'],
                views=message_meta['views'],
                forwards=message_meta['forwards'],
                has_media_spoiler=message_meta['has_media_spoiler'],
                has_protected_content=message_meta['has_protected_content'],
                contents=contents
            )

        except Exception as e:
            self.logger.error(f"Error loading message {message_id}: {str(e)}", exc_info=True)
            return None

    async def _load_message_metadata(self, message_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
        """Загружает метаданные сообщения из таблицы messages"""
        try:
            query = """
            SELECT 
                user_id, text, message_type, date, edit_date,
                is_outgoing, reply_to_message_id, reply_to_chat_id,
                forward_from, forward_from_chat, forward_date,
                via_bot_id, media_group_id, author_signature,
                views, forwards, has_media_spoiler, has_protected_content
            FROM messages
            WHERE message_id = $1 AND chat_id = $2
            """
            success, result = await self.db.execute_query(query, (message_id, chat_id))

            if not success or not result:
                return None

            return {
                'user_id': result[0][0],
                'text': result[0][1],
                'message_type': result[0][2],
                'date': result[0][3],
                'edit_date': result[0][4],
                'is_outgoing': result[0][5],
                'reply_to_message_id': result[0][6],
                'reply_to_chat_id': result[0][7],
                'forward_from': result[0][8],
                'forward_from_chat': result[0][9],
                'forward_date': result[0][10],
                'via_bot_id': result[0][11],
                'media_group_id': result[0][12],
                'author_signature': result[0][13],
                'views': result[0][14],
                'forwards': result[0][15],
                'has_media_spoiler': result[0][16],
                'has_protected_content': result[0][17]
            }

        except Exception as e:
            self.logger.error(f"Error loading message metadata: {str(e)}")
            return None

    async def _load_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Загружает информацию о чате"""
        try:
            query = """
            SELECT chat_type, title, description, invite_link
            FROM chats
            WHERE chat_id = $1
            """
            success, result = await self.db.execute_query(query, (chat_id,))

            if not success or not result:
                return None

            return {
                'chat_type': result[0][0],
                'title': result[0][1],
                'description': result[0][2],
                'invite_link': result[0][3]
            }

        except Exception as e:
            self.logger.error(f"Error loading chat info: {str(e)}")
            return None

    async def _load_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Загружает информацию о пользователе"""
        try:
            query = """
            SELECT username, first_name, last_name, language_code, is_bot, is_premium
            FROM users
            WHERE user_id = $1
            """
            success, result = await self.db.execute_query(query, (user_id,))

            if not success or not result:
                return None

            return {
                'username': result[0][0],
                'first_name': result[0][1],
                'last_name': result[0][2],
                'language_code': result[0][3],
                'is_bot': result[0][4],
                'is_premium': result[0][5]
            }

        except Exception as e:
            self.logger.error(f"Error loading user info: {str(e)}")
            return None

    async def _load_message_contents(self, message_id: int, chat_id: int) -> Optional[List[Any]]:
        """Загружает все содержимое сообщения"""
        try:
            # Получаем типы контента для этого сообщения
            query = """
            SELECT DISTINCT content_type 
            FROM message_contents 
            WHERE message_id = $1 AND chat_id = $2
            """
            success, result = await self.db.execute_query(query, (message_id, chat_id))

            if not success:
                return None

            contents = []
            for row in result:
                content_type = row[0]
                handler = self.handlers.get(content_type)
                if not handler:
                    self.logger.warning(f"No handler for content type {content_type}")
                    continue

                content = await handler.load_content(message_id, chat_id)
                if content:
                    contents.append(content)

            return contents

        except Exception as e:
            self.logger.error(f"Error loading message contents: {str(e)}")
            return None