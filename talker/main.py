# talker/main.py
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from talker.config import Settings
from talker.routes.assess import router as assess_router
from talker.routes.history import router as history_router
from talker.routes.main import router as main_router
from talker.services.database import create_session_factory
from talker.services.tracing import init_langfuse


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_langfuse(settings)
    app.state.db_session_factory = create_session_factory(settings)
    yield


app = FastAPI(title="Talker", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(main_router)
app.include_router(assess_router)
app.include_router(history_router)
