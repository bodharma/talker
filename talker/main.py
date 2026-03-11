# talker/main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from talker.config import get_settings
from talker.routes.assess import router as assess_router
from talker.routes.history import router as history_router
from talker.routes.main import router as main_router
from talker.routes.report import router as report_router
from talker.routes.settings import router as settings_router
from talker.routes.voice import router as voice_router
from talker.services.database import create_session_factory, run_migrations
from talker.services.tracing import init_langfuse


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    run_migrations()
    init_langfuse(settings)
    app.state.db_session_factory = create_session_factory(settings)
    yield


app = FastAPI(title="Talker", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(main_router)
app.include_router(assess_router)
app.include_router(history_router)
app.include_router(report_router)
app.include_router(voice_router)
app.include_router(settings_router)
