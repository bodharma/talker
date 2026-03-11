"""Tests for the LiveKit integration routes."""

from unittest.mock import patch

import pytest

from talker.routes.livekit import router


class TestLivekitTokenEndpoint:
    """Tests for POST /api/livekit/token."""

    @pytest.mark.asyncio
    async def test_token_generation_without_credentials(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(router)

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_api_key = ""
            settings.livekit_api_secret = ""
            settings.livekit_url = "wss://test.livekit.cloud"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/livekit/token",
                    json={"persona": "receptionist"},
                )
                assert resp.status_code == 503
                assert "not configured" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_token_generation_with_credentials(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(router)

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_api_key = "devkey"
            settings.livekit_api_secret = "secret-that-is-at-least-32-chars-long!"
            settings.livekit_url = "wss://test.livekit.cloud"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/livekit/token",
                    json={"persona": "receptionist", "name": "Test User"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "token" in data
                assert "room" in data
                assert data["room"].startswith("talker-receptionist-")
                assert data["livekit_url"] == "wss://test.livekit.cloud"
                assert "participant_id" in data

    @pytest.mark.asyncio
    async def test_token_default_persona(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(router)

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_api_key = "devkey"
            settings.livekit_api_secret = "secret-that-is-at-least-32-chars-long!"
            settings.livekit_url = "wss://test.livekit.cloud"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/livekit/token",
                    json={},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["room"].startswith("talker-receptionist-")


def _make_app():
    """Create a FastAPI app with session middleware for template rendering."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(router)
    try:
        app.mount("/static", StaticFiles(directory="talker/static"), name="static")
    except Exception:
        pass
    return app


class TestLivekitVoicePage:
    """Tests for GET /livekit/voice."""

    @pytest.mark.asyncio
    async def test_page_requires_livekit_url(self):
        from httpx import ASGITransport, AsyncClient

        app = _make_app()

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_url = ""

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/livekit/voice")
                assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_receptionist_serves_without_auth(self):
        from httpx import ASGITransport, AsyncClient

        app = _make_app()

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_url = "wss://test.livekit.cloud"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/livekit/voice?persona=receptionist")
                assert resp.status_code == 200
                assert "livekit-client" in resp.text
                assert "receptionist" in resp.text.lower()

    @pytest.mark.asyncio
    async def test_assessor_redirects_without_auth(self):
        from httpx import ASGITransport, AsyncClient

        app = _make_app()

        with patch("talker.routes.livekit.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.livekit_url = "wss://test.livekit.cloud"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/livekit/voice?persona=assessor",
                    follow_redirects=False,
                )
                assert resp.status_code == 303
                assert "/auth/login" in resp.headers.get("location", "")
