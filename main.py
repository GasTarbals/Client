from fastapi import FastAPI
from api import lifespan, router, router_function, router_comment, router_message
import uvicorn
# Создаем экземпляр FastAPI с обработчиками жизненного цикла
app = FastAPI(lifespan=lifespan)

# Подключаем роутер
app.include_router(router)
app.include_router(router_function)

app.include_router(router_comment)
#app.include_router(router_message)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
