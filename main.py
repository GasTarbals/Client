from fastapi import FastAPI
from api import lifespan, router, router_function, router_comment, router_listener
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
# Создаем экземпляр FastAPI с обработчиками жизненного цикла
app = FastAPI(lifespan=lifespan)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все домены (для разработки)
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP-методы (GET, POST, PUT и т.д.)
    allow_headers=["*"],  # Разрешить все заголовки
)

# Подключаем роутер
app.include_router(router)
app.include_router(router_function)

app.include_router(router_comment)

app.include_router(router_listener)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
