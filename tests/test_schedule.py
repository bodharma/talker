from talker.services.schedule import RECURRENCE_DAYS, ScheduleService


def test_schedule_service_init():
    svc = ScheduleService(db=None)
    assert svc.db is None


def test_recurrence_days():
    assert RECURRENCE_DAYS["weekly"] == 7
    assert RECURRENCE_DAYS["biweekly"] == 14
    assert RECURRENCE_DAYS["monthly"] == 30
