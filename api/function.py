import asyncio

from telegram import TelegramService
from telethon.tl import functions
from telethon.tl.types import InputPeerChannel
from fastapi import Depends, HTTPException, APIRouter, Query, Path
from pydantic import BaseModel
from typing import Union, List, Optional, Dict, Any
import logging
from telethon.errors import (
    MessageIdInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    MessageDeleteForbiddenError
)


logger = logging.getLogger(__name__)
# Создаем роутер для обработки запросов
router_function = APIRouter()

# Инициализируем сервис Telegram (Singleton)
telegram_service = TelegramService()

# Модели запросов (DTO - Data Transfer Objects)
class JoinLeaveChannelRequest(BaseModel):
    """Модель запроса для входа/выхода из канала"""
    channel: Union[str, int]  # Может быть username (@channel) или ID канала

class SendMessageRequest(BaseModel):
    """Модель запроса для отправки сообщения"""
    chat: Union[str, int]  # ID чата или username
    text: str  # Текст сообщения

# Дополнительные модели запросов
class CommentRequest(BaseModel):
    """Модель запроса для работы с комментариями"""
    channel: Union[str, int]  # ID или username канала
    message_id: int  # ID сообщения
    text: Optional[str] = None  # Текст (только для добавления)
    comment_id: Optional[int] = None  # ID комментария (для удаления)


class GetMessageRequest(BaseModel):
    """Модель запроса для получения сообщений"""
    channel: Union[str, int]  # ID или username канала
    message_id: Optional[int] = None  # ID конкретного сообщения (опционально)
    limit: Optional[int] = 1  # Лимит сообщений (по умолчанию 1)

# Фабрика зависимостей для внедрения сервиса
async def get_telegram_service():
    """
    Зависимость для инъекции сервиса Telegram.
    Автоматически подключается, если нет активного соединения.
    """
    if not telegram_service.is_connected():
        await telegram_service.start()  # Устанавливаем соединение при необходимости
    return telegram_service

# Эндпоинты API
@router_function.get("/channels",
            response_model=List[Dict[str, Any]],
            summary="Получить список всех каналов/групп",
            description="Возвращает полную информацию о каналах включая ID, название и username")
async def get_channels(service: TelegramService = Depends(get_telegram_service)):
    """
    Получить полную информацию о всех каналах/группах

    Returns:
        List[Dict]: Список каналов с ключами:
        - id (int): ID канала
        - title (str): Название канала
        - username (str, optional): @username канала (если есть)
        - is_channel (bool): True для каналов, False для чатов
    """
    try:
        return await service.functions.get_all_channels()
    except Exception as e:
        logger.error(f"Failed to get channels: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to retrieve channels",
                "error": str(e)
            }
        )


@router_function.get("/channels/usernames",
            response_model=List[str],
            summary="Получить список username каналов",
            description="Возвращает только @usernames каналов (без приватных)")
async def get_channel_usernames(service: TelegramService = Depends(get_telegram_service)):
    """
    Получить только usernames публичных каналов

    Returns:
        List[str]: Список @usernames (без None значений)
    """
    try:
        channels = await service.functions.get_all_channels()
        return [c["username"] for c in channels if c["username"]]
    except Exception as e:
        logger.error(f"Failed to get usernames: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to retrieve usernames",
                "error": str(e)
            }
        )


@router_function.get("/channels/{channel_id}",
            response_model=Dict[str, Any],
            summary="Получить информацию о конкретном канале")
async def get_channel_info(
        channel_id: int,
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Получить информацию о конкретном канале по ID

    Returns:
        Dict: Информация о канале или 404 если не найден
    """
    try:
        channels = await service.functions.get_all_channels()
        channel = next((c for c in channels if c["id"] == channel_id), None)

        if not channel:
            raise HTTPException(
                status_code=404,
                detail={"message": "Channel not found"}
            )
        return channel
    except Exception as e:
        logger.error(f"Failed to get channel info: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to retrieve channel info",
                "error": str(e)
            }
        )
@router_function.post("/join", response_model=bool)
async def join_channel(
    request: JoinLeaveChannelRequest,
    service: TelegramService = Depends(get_telegram_service)
):
    """
    Присоединиться к каналу/группе
    Принимает username или ID канала
    Возвращает True при успешном вступлении
    """
    try:
        return await service.functions.join_channel(request.channel)
    except Exception as e:
        # Ошибка клиента (неправильный запрос)
        raise HTTPException(status_code=400, detail=str(e))

@router_function.post("/leave", response_model=bool)
async def leave_channel(
    request: JoinLeaveChannelRequest,
    service: TelegramService = Depends(get_telegram_service)
):
    """
    Покинуть канал/группу
    Принимает username или ID канала
    Возвращает True при успешном выходе
    """
    success = await service.functions.leave_channel(request.channel)
    if not success:
        raise HTTPException(status_code=400, detail="Unable to leave channel")
    return success

@router_function.post("/send", response_model=Union[str, None])
async def send_message(
    request: SendMessageRequest,
    service: TelegramService = Depends(get_telegram_service)
):
    """
    Отправить сообщение в чат/канал
    Возвращает ID отправленного сообщения
    """
    message = await service.functions.send_message(request.chat, request.text)
    if message is None:
        raise HTTPException(status_code=400, detail="Unable to send message")
    return message.id

@router_function.delete("/delete", response_model=bool)
async def delete_message(
    chat: Union[str, int],
    message_id: int,
    service: TelegramService = Depends(get_telegram_service)
):
    """
    Удалить сообщение по ID
    Принимает chat (username или ID) и message_id
    Возвращает True при успешном удалении
    """
    success = await service.functions.delete_message(chat, message_id)
    if not success:
        raise HTTPException(status_code=400, detail="Unable to delete message")
    return success

# Новые эндпоинты для работы с комментариями
@router_function.post("/comments/add", response_model=Union[int, None])
async def add_comment(
        request: CommentRequest,
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Добавить комментарий к сообщению
    Возвращает ID созданного комментария
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required for comment")

    comment = await service.functions.add_comment(
        channel=request.channel,
        message_id=request.message_id,
        text=request.text
    )
    if comment is None:
        raise HTTPException(status_code=400, detail="Failed to add comment")
    return comment.id


@router_function.delete("/comments/{comment_id}")
async def delete_comment(
        comment_id: int = Path(..., title="ID комментария", gt=0),
        channel: str = Query(..., description="Username канала (например, @test_channel)"),
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Удалить комментарий в канале с обсуждениями

    Требования:
    1. Канал должен иметь включенные обсуждения
    2. Бот должен быть администратором канала
    """
    try:
        # Получаем сущность канала в правильном формате
        try:
            channel_entity = await service.client.get_entity(channel)
            if not hasattr(channel_entity, 'channel_id'):
                raise ValueError("Указанная сущность не является каналом")

            input_peer = InputPeerChannel(
                channel_id=channel_entity.channel_id,
                access_hash=channel_entity.access_hash
            )
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Ошибка канала: {str(e)}")

        # 1. Проверка существования комментария
        try:
            await service.client(
                functions.messages.GetDiscussionMessageRequest(
                    peer=input_peer,
                    msg_id=comment_id
                )
            )
        except (MessageIdInvalidError, ValueError):
            raise HTTPException(status_code=404, detail="Комментарий не найден")

        # 2. Удаление
        try:
            await service.client.delete_messages(input_peer, [comment_id])
            return {"status": "success", "deleted_id": comment_id}

        except MessageDeleteForbiddenError:
            raise HTTPException(status_code=403, detail="Нет прав на удаление")
        except ChatAdminRequiredError:
            raise HTTPException(status_code=403, detail="Требуются права администратора")

    except ChannelPrivateError:
        raise HTTPException(status_code=400, detail="Канал приватный или недоступен")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сервера: {str(e)}"
        )


@router_function.get("/comments/latest", response_model=Union[dict, None])
async def get_last_comment(
        channel: Union[str, int] = Query(..., description="ID или username канала"),
        message_id: int = Query(..., description="ID сообщения"),
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Получить последний комментарий к сообщению
    Возвращает данные комментария в формате:
    {
        "id": int,
        "text": str,
        "date": str (ISO format)
    }
    """
    comment = await service.functions.get_last_comment(
        channel=channel,
        message_id=message_id
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="No comments found")

    return {
        "id": comment.id,
        "text": comment.message,
        "date": comment.date.isoformat()
    }


# Эндпоинты для работы с сообщениями
@router_function.get("/messages/latest", response_model=Union[dict, None])
async def get_last_message(
        channel: Union[str, int] = Query(..., description="ID или username канала"),
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Получить последнее сообщение в канале
    Возвращает данные сообщения в формате:
    {
        "id": int,
        "text": str,
        "date": str (ISO format)
    }
    """
    messages = await service.functions.get_last_message(
        channel=channel
    )

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found")

    # Возвращаем только последнее сообщение (как в оригинальной версии)
    last_message = messages
    return {
        "id": last_message.id,
        "text": last_message.message,
        "date": last_message.date.isoformat()
    }


from typing import List, Optional
from fastapi import Query, HTTPException


@router_function.get("/messages", response_model=List[dict])
async def get_messages(
        channel: Union[str, int] = Query(..., description="ID или username канала"),
        message_id: Optional[int] = Query(None, description="ID конкретного сообщения"),
        limit: Optional[int] = Query(1, description="Лимит сообщений"),
        service: TelegramService = Depends(get_telegram_service)
):
    """
    Получить список сообщений из канала

    Параметры:
    - channel: ID или username канала (обязательный)
    - message_id: ID конкретного сообщения (опционально)
    - limit: Количество возвращаемых сообщений (по умолчанию 1)

    Возвращает список сообщений в формате:
    [{
        "id": int,
        "text": str,
        "date": str (ISO format)
    }]
    """
    try:
        messages = await service.functions.get_messages(
            channel=channel,
            message_id=message_id,
            limit=limit
        )

        if not messages:
            raise HTTPException(status_code=404, detail="Messages not found")

        return [{
            "id": msg.id,
            "text": msg.message,
            "date": msg.date.isoformat()
        } for msg in messages]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")