def test_security_middleware_import():
    from talker.middleware import SecurityHeadersMiddleware
    assert SecurityHeadersMiddleware is not None


def test_health_endpoint_exists():
    from talker.main import app
    paths = [r.path for r in app.routes]
    assert "/health" in paths


def test_allowed_hosts_config():
    from talker.config import Settings
    settings = Settings(allowed_hosts="example.com,localhost")
    assert settings.allowed_hosts == "example.com,localhost"
