def test_clinician_routes_exist():
    """Clinician router has expected routes."""
    from talker.routes.clinician import router

    paths = [r.path for r in router.routes]
    assert "/clinician/" in paths
    assert "/clinician/invite" in paths
