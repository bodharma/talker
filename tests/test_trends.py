from talker.services.trends import TrendService


def test_trend_service_init():
    svc = TrendService(db=None)
    assert svc.db is None
