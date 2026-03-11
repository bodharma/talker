"""Shared auth dependencies for route protection."""

from fastapi import HTTPException, Request

from talker.services.auth import AuthService


def get_current_user_id(session: dict) -> int | None:
    """Extract user_id from session dict. Returns None if not logged in."""
    return session.get("user_id")


async def verify_auth(request: Request):
    """Dependency: require logged-in user. Redirects to login if not."""
    user_id = get_current_user_id(request.session)
    if not user_id:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user_id


async def verify_role(*roles: str):
    """Factory for role-checking dependencies."""
    async def _check(request: Request):
        user_id = await verify_auth(request)
        session_factory = request.app.state.db_session_factory
        async with session_factory() as db:
            auth = AuthService(db)
            user = await auth.get_user_by_id(user_id)
        if not user or user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _check


async def verify_admin(request: Request):
    """Dependency: require admin role."""
    user_id = await verify_auth(request)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        auth = AuthService(db)
        user = await auth.get_user_by_id(user_id)
    if not user or user.role != "admin":
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user


async def verify_clinician(request: Request):
    """Dependency: require clinician or admin role."""
    user_id = await verify_auth(request)
    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        auth = AuthService(db)
        user = await auth.get_user_by_id(user_id)
    if not user or user.role not in ("clinician", "admin"):
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user
