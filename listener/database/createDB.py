from typing import Optional, Dict, Any
from listener.database.connectDB import PostgreSQLConnector
import logging
import asyncio


class DatabaseCreator:
    def __init__(self):
        """Инициализация с логгером"""
        self.logger = logging.getLogger(__name__)
        self.db = PostgreSQLConnector()

    async def initialize_database(self) -> None:
        """Асинхронно создает таблицы с поддержкой медиа-данных"""
        creation_order = [
            self._get_users_table(),
            self._get_chats_table(),
            self._get_messages_table(),
            self._get_message_contents_table()
        ]

        await self.db.connect()
        self.logger.info("Инициализация структуры базы данных...")

        try:
            created_tables = set()
            remaining_tables = [table["name"] for table in creation_order]

            while remaining_tables:
                made_progress = False

                for table in creation_order:
                    if table["name"] not in remaining_tables:
                        continue

                    if all(dep in created_tables for dep in table["deps"]):
                        if not await self._table_exists(table["name"]):
                            success, _ = await self.db.execute_query(table["query"])
                            if success:
                                self.logger.info(f"✅ Таблица {table['name']} создана")
                                created_tables.add(table["name"])
                                remaining_tables.remove(table["name"])
                                made_progress = True
                        else:
                            self.logger.info(f"ℹ️ Таблица {table['name']} уже существует")
                            created_tables.add(table["name"])
                            remaining_tables.remove(table["name"])
                            made_progress = True

                if not made_progress:
                    self.logger.error(f"Не удалось создать таблицы: {remaining_tables}")
                    break

        except Exception as e:
            self.logger.error(f"Ошибка при инициализации БД: {str(e)}", exc_info=True)
            raise
        finally:
            await self.db.disconnect()

    def _get_users_table(self) -> Dict[str, Any]:
        return {
            "name": "users",
            "query": """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255) NOT NULL,
                last_name VARCHAR(255),
                language_code VARCHAR(10),
                is_bot BOOLEAN DEFAULT FALSE,
                is_premium BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )""",
            "deps": []
        }

    def _get_chats_table(self) -> Dict[str, Any]:
        return {
            "name": "chats",
            "query": """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id BIGINT PRIMARY KEY,
                chat_type VARCHAR(20) NOT NULL CHECK (
                    chat_type IN ('private', 'group', 'supergroup', 'channel')
                ),
                title VARCHAR(255),
                username VARCHAR(255),
                description TEXT,
                invite_link VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )""",
            "deps": []
        }

    def _get_messages_table(self) -> Dict[str, Any]:
        return {
            "name": "messages",
            "query": """
            CREATE TABLE IF NOT EXISTS messages (
                message_id BIGINT,
                chat_id BIGINT NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
                text TEXT,
                message_type VARCHAR(20) NOT NULL,
                date TIMESTAMPTZ NOT NULL,
                edit_date TIMESTAMPTZ,
                is_outgoing BOOLEAN NOT NULL,
                reply_to_message_id BIGINT,
                reply_to_chat_id BIGINT,
                forward_from BIGINT,
                forward_from_chat BIGINT,
                forward_date TIMESTAMPTZ,
                via_bot_id BIGINT,
                media_group_id VARCHAR(255),
                author_signature VARCHAR(255),
                views INTEGER,
                forwards INTEGER,
                has_media_spoiler BOOLEAN DEFAULT FALSE,
                has_protected_content BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (message_id, chat_id),
                FOREIGN KEY (reply_to_message_id, reply_to_chat_id) 
                    REFERENCES messages(message_id, chat_id) ON DELETE SET NULL
            )""",
            "deps": ["users", "chats"]
        }

    def _get_message_contents_table(self) -> Dict[str, Any]:
        return {
            "name": "message_contents",
            "query": """
            CREATE TABLE IF NOT EXISTS message_contents (
                content_id SERIAL PRIMARY KEY,
                message_id BIGINT NOT NULL,
                media_group_id VARCHAR(255),
                chat_id BIGINT NOT NULL,
                content_type VARCHAR(20) NOT NULL CHECK (
                    content_type IN ('text', 'photo', 'video', 'audio')),
                text_content TEXT,
                caption TEXT,
                file_id VARCHAR(255),
                file_unique_id VARCHAR(255),
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                duration INTEGER,
                mime_type VARCHAR(100),
                performer VARCHAR(255),
                title VARCHAR(255),
                thumbnail_url TEXT,
                file_url TEXT,
                binary_data BYTEA,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                FOREIGN KEY (message_id, chat_id) 
                    REFERENCES messages(message_id, chat_id) ON DELETE CASCADE,
                CONSTRAINT content_check CHECK (
                    (content_type = 'text' AND text_content IS NOT NULL) OR
                    (content_type IN ('photo', 'video', 'audio') AND file_id IS NOT NULL)
                )
            )""",
            "deps": ["messages"]
        }

    async def _table_exists(self, table_name: str) -> bool:
        """Асинхронно проверяет существование таблицы"""
        query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = $1
        )
        """

        success, result = await self.db.execute_query(query, (table_name,))
        return result[0][0] if success and result else False


async def main():
    db_creator = DatabaseCreator()
    await db_creator.initialize_database()


if __name__ == "__main__":
    asyncio.run(main())