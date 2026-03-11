# talker/main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from talker.config import get_settings
from talker.middleware import SecurityHeadersMiddleware
from talker.routes.admin import router as admin_router
from talker.routes.auth import router as auth_router, setup_oauth
from talker.routes.clinician import router as clinician_router
from talker.routes.assess import router as assess_router
from talker.routes.history import router as history_router
from talker.routes.main import router as main_router
from talker.routes.report import router as report_router
from talker.routes.settings import router as settings_router
from talker.routes.livekit import router as livekit_router
from talker.routes.voice import router as voice_router
from talker.services.database import create_session_factory, run_migrations
from talker.services.tracing import init_langfuse

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    run_migrations()
    init_langfuse(settings)
    app.state.db_session_factory = create_session_factory(settings)

    # Bootstrap admin user
    if settings.admin_email:
        from talker.services.auth import AuthService

        async with app.state.db_session_factory() as db:
            auth = AuthService(db)
            await auth.ensure_admin(settings.admin_email, settings.admin_password)

    # Setup OAuth
    setup_oauth()

    yield


app = FastAPI(title="Talker", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down."},
    )


# Error pages
error_templates = Jinja2Templates(directory="talker/templates")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    return error_templates.TemplateResponse(
        request=request,
        name="errors/404.html",
        status_code=404,
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: StarletteHTTPException):
    return error_templates.TemplateResponse(
        request=request,
        name="errors/500.html",
        status_code=500,
    )


# Middleware (order matters: last added = first executed)
app.add_middleware(SessionMiddleware, secret_key=get_settings().app_secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

allowed = [h.strip() for h in get_settings().allowed_hosts.split(",")]
if "*" not in allowed:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)


# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(main_router)
app.include_router(assess_router)
app.include_router(history_router)
app.include_router(report_router)
app.include_router(voice_router)
app.include_router(livekit_router)
app.include_router(settings_router)
app.include_router(auth_router)
app.include_router(clinician_router)
app.include_router(admin_router)
