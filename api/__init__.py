from api.server import lifespan, router, telegram_service
from api.function import router_function
from api.comment import router_comment

__all__ = ['lifespan', 'router', 'telegram_service', 'router_function', 'router_comment']