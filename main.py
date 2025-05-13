from fastapi import FastAPI
from api import lifespan, router, router_function
import uvicorn
# Создаем экземпляр FastAPI с обработчиками жизненного цикла
app = FastAPI(lifespan=lifespan)

# Подключаем роутер
app.include_router(router)
app.include_router(router_function)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
