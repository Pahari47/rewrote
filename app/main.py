from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.routes.job import router as jobs_router
from app.api.routes.media import router as media_router
from app.api.routes.metrics import router as metrics_router
from app.core.logging import get_logger, setup_logging
from app.core.redis import redis_client
from app.database import engine

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger("app")
    logger.info("startup", extra={"event": "startup", "component": "api"})

    try:
        async with engine.connect():
            print("Connected to the database")
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        raise

    try:
        await redis_client.ping()
        app.state.redis_client = redis_client
        print("Connected to the Redis")
    except Exception as e:
        print(f"Error connecting to the Redis: {e}")
        raise

    yield

    await engine.dispose()
    await redis_client.close()
    print("Disconnected from the database")
    print("Disconnected from the Redis")

app = FastAPI(lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(metrics_router)
app.include_router(media_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}