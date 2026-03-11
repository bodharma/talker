from talker.services.auth import AuthService
from talker.services.invite import InviteService


def test_invite_service_init():
    svc = InviteService(db=None)
    assert svc.db is None


def test_generate_invite_token():
    token = AuthService.generate_token()
    assert len(token) > 20
    token2 = AuthService.generate_token()
    assert token != token2
