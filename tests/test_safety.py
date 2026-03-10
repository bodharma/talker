from talker.agents.safety import SafetyMonitor, SafetyInterrupt


def test_safe_message():
    monitor = SafetyMonitor()
    result = monitor.check("I've been feeling tired lately")
    assert result is None


def test_detects_suicidal_ideation():
    monitor = SafetyMonitor()
    result = monitor.check("I want to kill myself")
    assert result is not None
    assert isinstance(result, SafetyInterrupt)
    assert len(result.resources) > 0


def test_detects_self_harm():
    monitor = SafetyMonitor()
    result = monitor.check("I've been cutting myself")
    assert result is not None


def test_detects_harm_to_others():
    monitor = SafetyMonitor()
    result = monitor.check("I want to hurt someone")
    assert result is not None


def test_case_insensitive():
    monitor = SafetyMonitor()
    result = monitor.check("I WANT TO KILL MYSELF")
    assert result is not None


def test_crisis_resources_included():
    monitor = SafetyMonitor()
    result = monitor.check("I want to end my life")
    assert "988" in str(result.resources) or "Suicide" in str(result.resources)
