from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging
from listener.database.connectDB import PostgreSQLConnector

class BaseDBHandler(ABC):
    def __init__(self, db_connector: PostgreSQLConnector):
        self.db = db_connector
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _record_exists(self, table: str, conditions: Dict[str, Any]) -> bool:
        """Общий метод проверки существования записи"""
        try:
            where_clause = " AND ".join([f"{k} = ${i+1}" for i, k in enumerate(conditions.keys())])
            query = f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {where_clause})"

            success, result = await self.db.execute_query(query, tuple(conditions.values()))
            return bool(result[0][0]) if success and result else False
        except Exception as e:
            self.logger.error(f"Error in _record_exists: {str(e)}", exc_info=True)
            return False

    @abstractmethod
    async def save_content(self, message, content) -> bool:
        """Абстрактный метод для сохранения контента"""
        pass