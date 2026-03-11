from datetime import datetime, timedelta

from talker.models.db import Invite, PatientLink, User
from talker.routes.deps import get_current_user_id
from talker.services.auth import AuthService


def test_user_model_defaults():
    user = User(email="test@example.com", name="Test")
    assert user.role == "patient"
    assert user.email_verified is False
    assert user.is_active is True
    assert user.password_hash is None
    assert user.oauth_provider is None


def test_patient_link_model():
    link = PatientLink(clinician_id=1, patient_id=2)
    assert link.clinician_id == 1
    assert link.patient_id == 2


def test_invite_model():
    invite = Invite(
        clinician_id=1,
        email="patient@example.com",
        token="abc123",
        expires_at=datetime.now() + timedelta(days=7),
    )
    assert invite.email == "patient@example.com"
    assert invite.accepted_at is None
    assert invite.instruments is None


def test_hash_and_verify_password():
    hashed = AuthService.hash_password("mysecret")
    assert hashed != "mysecret"
    assert AuthService.verify_password("mysecret", hashed)
    assert not AuthService.verify_password("wrong", hashed)


def test_hash_password_unique():
    h1 = AuthService.hash_password("same")
    h2 = AuthService.hash_password("same")
    assert h1 != h2  # bcrypt uses random salt


def test_get_current_user_returns_none_without_session():
    assert get_current_user_id({}) is None


def test_get_current_user_returns_id():
    assert get_current_user_id({"user_id": 42}) == 42
