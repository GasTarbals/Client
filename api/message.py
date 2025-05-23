from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from telegram import TelegramCommentSchema, MediaType
import logging
from typing import Union, Optional
from telegram import TelegramService

logger = logging.getLogger(__name__)
router_message = APIRouter(prefix="/api/messages", tags=["Messages"])

# Создаем роутер для обработки запросов
router_function = APIRouter()

# Инициализируем сервис Telegram (Singleton)
telegram_service = TelegramService()
# Фабрика зависимостей для внедрения сервиса
async def get_telegram_service():
    """
    Зависимость для инъекции сервиса Telegram.
    Автоматически подключается, если нет активного соединения.
    """
    if not telegram_service.is_connected():
        await telegram_service.start()  # Устанавливаем соединение при необходимости
    return telegram_service

class CommentResponse(BaseModel):
    success: bool
    message: str
    comment_id: Optional[int] = None  # ID отправленного комментария


class ChannelCommentRequest(BaseModel):
    channel_identifier: Union[int, str]  # ID или username канала
    message: str
    reply_to_msg_id: int  # ID сообщения для ответа
    access_hash: Optional[str] = None


@router_message.post("/send-comment", response_model=CommentResponse)
async def send_comment(
        request: ChannelCommentRequest,
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Отправка комментария в канал (поддержка ID и username)

    Параметры:
    - channel_identifier: ID (число) или username (начинается с @) канала
    - message: Текст комментария
    - reply_to_msg_id: ID сообщения для ответа
    - access_hash: Хэш доступа (опционально)
    """
    try:

        sender = service.mtproto

        # Получаем информацию о канале
        channel = await service.client.get_entity(request.channel_identifier)

        # Отправляем комментарий
        result = await sender.safe_send_to_channel(
            channel_identifier=channel.id if hasattr(channel, 'id') else request.channel_identifier,
            message=request.message,
            reply_to_msg_id=request.reply_to_msg_id,
            access_hash=channel.access_hash if hasattr(channel, 'access_hash') else request.access_hash
        )

        if not result:
            return CommentResponse(
                success=False,
                message="Failed to post comment (check logs)"
            )

        # Получаем ID последнего сообщения (комментария)
        messages = await service.client.get_messages(channel, limit=1)
        comment_id = messages[0].id if messages else None

        return CommentResponse(
            success=True,
            message="Comment posted successfully",
            comment_id=comment_id
        )

    except ValueError as e:
        logger.error(f"Invalid channel identifier: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid channel identifier"
        )
    except Exception as e:
        logger.error(f"Comment posting error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )