from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes.daily_record import router as daily_record_router
from .api.routes.prescription import router as prescription_router
from .core.config import settings
from .core.cors import setup_cors
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

setup_cors(app)

app.include_router(daily_record_router)
app.include_router(prescription_router)


@app.get("/")
async def health_check() -> dict[str, str]:
    return {
        "message": "智能骨科康复伴侣后端运行中",
        "version": settings.app_version,
    }
