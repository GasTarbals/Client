import asyncio
import logging
from typing import Optional, Set, Any


class MediaDownloader:
    """Класс для загрузки медиафайлов."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self._download_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()  # Для потокобезопасности операций с задачами

    async def download(self, media: Any, path: Optional[str] = None) -> Optional[str]:
        """Загрузка медиафайла."""
        try:
            task = asyncio.create_task(
                self.client.download_media(media, file=bytes))
            await self._add_task(task)
            return await task
        except asyncio.CancelledError:
            logging.warning("Download was cancelled")
            return None
        except Exception as e:
            logging.error(f"Download error: {e}", exc_info=True)
            return None

    async def _add_task(self, task: asyncio.Task) -> None:
        """Добавление задачи загрузки в отслеживаемые."""
        async with self._lock:
            self._download_tasks.add(task)
            task.add_done_callback(self._remove_task)

    def _remove_task(self, task: asyncio.Task) -> None:
        """Удаление завершенной задачи."""
        # Используем remove вместо discard, чтобы ловить исключения если задача уже удалена
        try:
            self._download_tasks.remove(task)
        except KeyError:
            pass

    async def cancel_all(self) -> None:
        """Отмена всех активных загрузок."""
        async with self._lock:
            for task in self._download_tasks.copy():  # Копируем чтобы избежать изменений во время итерации
                try:
                    task.cancel()
                except Exception as e:
                    logging.error(f"Error cancelling task: {e}", exc_info=True)