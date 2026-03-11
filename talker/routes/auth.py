"""Authentication routes — login, signup, OAuth callbacks."""

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from talker.config import get_settings
from talker.services.auth import AuthService

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/auth")
log = logging.getLogger(__name__)

oauth = OAuth()


def setup_oauth():
    """Register OAuth providers. Called once at startup."""
    settings = get_settings()
    if settings.google_client_id:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    if settings.apple_client_id:
        oauth.register(
            name="apple",
            client_id=settings.apple_client_id,
            client_secret=settings.apple_client_secret,
            server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email name"},
        )


@router.get("/login")
async def login_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "error": request.query_params.get("error"),
            "google_enabled": bool(settings.google_client_id),
            "apple_enabled": bool(settings.apple_client_id),
        },
    )


@router.post("/login")
async def login(request: Request, email: str = Form(), password: str = Form()):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        auth = AuthService(db)
        user = await auth.authenticate(email, password)

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Invalid email or password",
                "google_enabled": bool(get_settings().google_client_id),
                "apple_enabled": bool(get_settings().apple_client_id),
            },
        )

    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["user_name"] = user.name

    if user.role == "admin":
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin/", status_code=303)
    elif user.role == "clinician":
        return RedirectResponse(url="/clinician/", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@router.get("/signup")
async def signup_page(request: Request):
    invite_token = request.query_params.get("invite")
    return templates.TemplateResponse(
        request=request,
        name="auth/signup.html",
        context={"error": None, "invite_token": invite_token or ""},
    )


@router.post("/signup")
async def signup(
    request: Request,
    name: str = Form(),
    email: str = Form(),
    password: str = Form(),
    invite_token: str = Form(default=""),
):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        auth = AuthService(db)

        existing = await auth.get_user_by_email(email)
        if existing:
            return templates.TemplateResponse(
                request=request,
                name="auth/signup.html",
                context={"error": "Email already registered", "invite_token": invite_token},
            )

        user = await auth.create_user(email=email, name=name, password=password)

        if invite_token:
            from talker.services.invite import InviteService

            invite_svc = InviteService(db)
            await invite_svc.accept_invite(invite_token, user.id)

        await db.commit()

    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["user_name"] = user.name
    return RedirectResponse(url="/", status_code=303)


@router.get("/login/{provider}")
async def oauth_login(request: Request, provider: str):
    client = oauth.create_client(provider)
    if not client:
        return RedirectResponse(url="/auth/login?error=Provider+not+configured")
    settings = get_settings()
    redirect_uri = f"{settings.base_url}/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def oauth_callback(request: Request, provider: str):
    client = oauth.create_client(provider)
    if not client:
        return RedirectResponse(url="/auth/login?error=Provider+not+configured")

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/auth/login?error=OAuth+failed")

    userinfo = token.get("userinfo") or await client.userinfo(token=token)
    if not userinfo:
        return RedirectResponse(url="/auth/login?error=No+user+info")

    oauth_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name") or email.split("@")[0]

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        auth = AuthService(db)
        user = await auth.get_user_by_oauth(provider, oauth_id)
        if not user:
            user = await auth.get_user_by_email(email)
            if user:
                user.oauth_provider = provider
                user.oauth_id = oauth_id
                user.email_verified = True
            else:
                user = await auth.create_user(
                    email=email,
                    name=name,
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                )
        await db.commit()

    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["user_name"] = user.name

    if user.role == "admin":
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin/", status_code=303)
    elif user.role == "clinician":
        return RedirectResponse(url="/clinician/", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@router.get("/invite/{token}")
async def accept_invite(request: Request, token: str):
    """Redirect to signup with invite context."""
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        from talker.services.invite import InviteService

        svc = InviteService(db)
        invite = await svc.get_invite_by_token(token)

    if not invite:
        return RedirectResponse(url="/auth/login?error=Invalid+or+expired+invite")

    user_id = request.session.get("user_id")
    if user_id:
        async with session_factory() as db:
            svc = InviteService(db)
            await svc.accept_invite(token, user_id)
            await db.commit()
        return RedirectResponse(url="/", status_code=303)

    return RedirectResponse(url=f"/auth/signup?invite={token}", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=303)
