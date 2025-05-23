from typing import Optional
from fastapi import FastAPI, HTTPException
import asyncio
import logging
from contextlib import asynccontextmanager
from telegram import TelegramService
from api.config import (
    API_ID, API_HASH, SESSION, PHONE_NUMBER,
    DEVICE_MODEL, SYSTEM_VERSION, APP_VERSION,
    LANG_CODE, SYSTEM_LANG_CODE
)
from fastapi import APIRouter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальный экземпляр сервиса
telegram_service = TelegramService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    try:
        # Инициализация клиента
        await telegram_service.initialize(
            session=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            phone=PHONE_NUMBER,
            device_model=DEVICE_MODEL,
            system_version=SYSTEM_VERSION,
            app_version=APP_VERSION,
            lang_code=LANG_CODE,
            system_lang_code=SYSTEM_LANG_CODE
        )
        yield
    except Exception as e:
        logger.error(f"Ошибка инициализации: {str(e)}")
        raise
    finally:
        await telegram_service.stop()

router = APIRouter()


@router.get('/connect')
async def connect():
    """Подключение к Telegram"""
    if not telegram_service.client:
        raise HTTPException(status_code=500, detail="Telegram client not initialized")

    if telegram_service.is_connected():
        return {
            "status": "success",
            "message": "Уже подключено"
        }

    try:
        await telegram_service.start(phone=PHONE_NUMBER)
        logger.info("Успешное подключение к Telegram")
        return {
            "status": "success",
            "message": "Подключение установлено"
        }
    except Exception as e:
        logger.error(f"Ошибка подключения: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Ошибка подключения",
                "error": str(e)
            }
        )

@router.get('/disconnect')
async def disconnect():
    """Отключение от Telegram"""
    if not telegram_service.is_connected():
        return {
            "status": "error",
            "message": "Не подключено",
            "details": {"active": False}
        }

    try:
        await telegram_service.stop()
        logger.info("Успешное отключение от Telegram")
        return {
            "status": "success",
            "message": "Отключено"
        }
    except Exception as e:
        logger.error(f"Ошибка отключения: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Ошибка отключения",
                "error": str(e)
            }
        )


@router.get('/status')
async def status():
    """Проверка состояния подключения и информации о клиенте"""
    if not telegram_service.client:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Клиент Telegram не инициализирован"
            }
        )

    try:
        client = telegram_service.client
        connected = telegram_service.is_connected()

        client_details = None
        if connected:
            me = await client.get_me()
            user_status = me.status if hasattr(me, 'status') else None

            client_details = {
                "is_bot": me.bot,
                "user_id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name if me.last_name else None,
                "username": me.username if me.username else None,
                "phone": me.phone if me.phone else None,
                "lang_code": me.lang_code if me.lang_code else None,
                "premium": me.premium if hasattr(me, 'premium') else None,
                "verified": me.verified if hasattr(me, 'verified') else None,
                "restricted": me.restricted if hasattr(me, 'restricted') else None,
                "status": user_status,
                "dc_id": me.dc_id if hasattr(me, 'dc_id') else None,
            }
            logger.info(f"Информация о клиенте: {client_details}")

        return {
            "status": "success",
            "connected": connected,
            "client_info": client_details if connected else None
        }

    except Exception as e:
        logger.error(f"Ошибка получения статуса: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Ошибка получения статуса",
                "error": str(e)
            }
        )