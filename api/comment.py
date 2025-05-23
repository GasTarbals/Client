from telegram import TelegramService
from fastapi import Depends, HTTPException, APIRouter, Query, Path
from pydantic import BaseModel
from telegram import TelegramCommentSchema, MediaType
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)
# Создаем роутер для обработки запросов
router_comment = APIRouter()

# Инициализируем сервис Telegram (Singleton)
telegram_service = TelegramService()


class CommentResponse(BaseModel):
    message_id: Union[int, None]
    details: str


class DeleteCommentResponse(BaseModel):
    success: bool
    message: str
    deleted_comment_id: Optional[int] = None


# Фабрика зависимостей для внедрения сервиса
async def get_telegram_service():
    """
    Зависимость для инъекции сервиса Telegram.
    Автоматически подключается, если нет активного соединения.
    """
    if not telegram_service.is_connected():
        await telegram_service.start()  # Устанавливаем соединение при необходимости
    return telegram_service


# Новые эндпоинты для работы с комментариями
@router_comment.post("/add", response_model=CommentResponse)
async def add_comment(
        channel: str,  # Параметр для канала
        message_id: int,  # Параметр для ID сообщения
        request: TelegramCommentSchema,  # Параметр для комментария
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Добавляет комментарий к сообщению в Telegram канале

    Параметры:
    - channel: username или ID канала (например, "@my_channel" или -100123456)
    - message_id: ID сообщения в канале
    - request: Объект TelegramCommentSchema с данными комментария

    Возвращает:
    - ID созданного комментария или None в случае ошибки
    - Детали операции
    """

    try:
        # Валидация уже происходит в TelegramCommentSchema, дополнительная проверка не нужна

        # Получаем экземпляр класса TelegramComment из сервиса
        comment_service = service.comment

        # Отправляем комментарий
        result = await comment_service.add_comment(
            channel=channel,
            channel_message_id=message_id,
            comment=request  # Передаем весь объект схемы
        )

        return CommentResponse(
            message_id=result.id if result else None,
            details="Comment successfully added" if result else "Failed to add comment"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router_comment.delete("/{comment_id}", response_model=DeleteCommentResponse)
async def delete_comment(
        comment_id: int = Path(..., title="ID комментария", gt=0),
        channel: str = Query(..., description="Username канала (например, @test_channel)"),
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Удаляет комментарий из группы обсуждения Telegram канала

    Параметры:
    - comment_id: ID удаляемого комментария (должен быть > 0)
    - channel: username канала (начинается с @) или его ID
    - message_id: ID сообщения в канале, к которому прикреплен комментарий

    Возвращает:
    - success: Статус операции
    - message: Детали выполнения
    - deleted_comment_id: ID удаленного комментария (если успешно)
    """
    try:
        # Получаем экземпляр класса TelegramComment из сервиса
        comment_service = service.comment

        # Выполняем удаление
        result = await comment_service.delete_comment(
            channel=channel,
            comment_id=comment_id
        )

        if result:
            return DeleteCommentResponse(
                success=True,
                message="Комментарий успешно удален",
                deleted_comment_id=comment_id
            )
        else:
            return DeleteCommentResponse(
                success=False,
                message="Не удалось удалить комментарий"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )