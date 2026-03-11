from datetime import datetime

from talker.services.admin_repo import SessionFilter, SessionListItem


def test_admin_password_required():
    """Admin panel is disabled when no password is configured."""
    from talker.config import Settings

    settings = Settings(admin_password="")
    assert not settings.admin_password


def test_session_filter_defaults():
    f = SessionFilter()
    assert f.state is None
    assert f.severity is None
    assert f.has_safety_events is None
    assert f.page == 1
    assert f.per_page == 25


def test_session_list_item_model():
    item = SessionListItem(
        id="abc-123",
        created_at=datetime.now(),
        state="completed",
        instruments=["phq-9", "gad-7"],
        highest_severity="moderate",
        safety_event_count=1,
    )
    assert item.safety_event_count == 1
    assert item.instruments == ["phq-9", "gad-7"]


def test_session_filter_with_values():
    f = SessionFilter(
        state="completed",
        severity="severe",
        has_safety_events=True,
        page=3,
    )
    assert f.state == "completed"
    assert f.severity == "severe"
    assert f.has_safety_events is True
    assert f.page == 3


def test_admin_config_fields():
    from talker.config import Settings

    settings = Settings(admin_username="superadmin", admin_password="secret123")
    assert settings.admin_username == "superadmin"
    assert settings.admin_password == "secret123"
