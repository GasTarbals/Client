from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import asyncio
import logging
from telegram import TelegramService

logger = logging.getLogger(__name__)

# Инициализация сервиса Telegram
telegram_service = TelegramService()

# Фабрика зависимостей
async def get_telegram_service() -> TelegramService:
    if not telegram_service.is_connected():
        await telegram_service.start()
    return telegram_service

# Создаем роутер
router_listener = APIRouter(prefix="/api/listener", tags=["Telegram Listener"])

@router_listener.get('/start', summary="Start Telegram monitoring")
async def start_monitoring(service: TelegramService = Depends(get_telegram_service)):
    """Запуск мониторинга Telegram"""
    try:

        if service.monitor.is_running():
            return {
                "status": "success",
                "message": "Monitoring is already running",
                "details": service.monitor.get_status()
            }

        await service.monitor.start_monitor()


        return {
            "status": "success",
            "message": "Monitoring started successfully",
            "details": service.monitor.get_status()
        }

    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to start monitoring",
                "error": str(e)
            }
        )

@router_listener.get('/stop', summary="Stop Telegram monitoring")
async def stop_monitoring(service: TelegramService = Depends(get_telegram_service)):
    """Остановка мониторинга Telegram"""
    try:
        if not service.monitor.is_running:
            return {
                "status": "success",
                "message": "Monitoring was not running",
                "details": service.monitor.get_status()
            }

        await service.monitor.stop_monitor()

        return {
            "status": "success",
            "message": "Monitoring stopped successfully",
            "details": service.monitor.get_status()
        }

    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to stop monitoring",
                "error": str(e)
            }
        )

@router_listener.get('/status', summary="Get monitoring status")
async def get_status(service: TelegramService = Depends(get_telegram_service)):
    """Получение текущего статуса мониторинга"""
    try:
        return {
            "status": "success",
            "details": service.monitor.get_status()
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to get status",
                "error": str(e)
            }
        )