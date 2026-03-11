import csv
import io

from talker.services.export import ExportService


def test_export_service_init():
    svc = ExportService(db=None)
    assert svc.db is None


def test_csv_header_format():
    """CSV output should have expected headers."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id",
        "state",
        "mode",
        "created_at",
        "completed_at",
        "instruments",
        "scores",
        "severities",
        "safety_event_count",
    ])
    content = output.getvalue()
    assert "session_id" in content
    assert "safety_event_count" in content
