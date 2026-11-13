"""Analytics totals and background recording regression checks."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import event
from starlette.requests import Request

from app.api.routes.public import _render_page, _track_visit
from app.database.db import SessionLocal, engine
from app.database.models import Visit
from app.main import app
from app.services.visit_service import VisitService


def test_empty_analytics():
    service = VisitService()
    assert service.summary() == {"total": 0, "today": 0, "unique_ips": 0}
    result = service.analytics("invalid")
    assert result["period"] == "week"
    assert result["total"] == result["today_count"] == result["unique_ips"] == 0
    assert result["chart"] == result["filtered"] == []


def test_aggregate_counts_and_query_budget():
    now = datetime.now(UTC).replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        db.add_all(
            [
                Visit(ip="one", visited_at=today),
                Visit(ip="one", visited_at=today),
                Visit(ip="two", visited_at=today - timedelta(days=1)),
                Visit(ip="old", visited_at=today - timedelta(days=40)),
            ]
        )
        db.commit()
    queries = []

    def record_query(connection, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", record_query)
    try:
        service = VisitService()
        assert service.summary() == {"total": 4, "today": 2, "unique_ips": 3}
        assert len(queries) == 1
        queries.clear()
        result = service.analytics("week")
        assert result["total"] == 3
        assert result["today_count"] == 2
        assert result["unique_ips"] == 2
        assert result["all_time_total"] == 4
        assert sum(item["count"] for item in result["chart"]) == 3
        assert len(queries) == 5
    finally:
        event.remove(engine, "before_cursor_execute", record_query)


@pytest.mark.asyncio
async def test_visit_recording_is_attached_to_response():
    request = Request(
        {
            "app": app,
            "type": "http",
            "method": "GET",
            "path": "/contact",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 123),
            "headers": [],
            "query_string": b"",
        }
    )
    service = Mock()
    _track_visit(request, service)
    response = _render_page(request, "contact.html")
    service.log_visit.assert_not_called()
    assert response.background is not None
    await response.background()
    service.log_visit.assert_called_once_with("127.0.0.1")


def test_visits_older_than_the_retention_period_are_deleted_once_a_day():
    from datetime import UTC, datetime, timedelta

    from app.database.db import SessionLocal
    from app.database.models import Visit as VisitRecord
    from app.services import visit_service as module

    now = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as db:
        db.add_all([
            VisitRecord(ip="old", visited_at=now - timedelta(days=module.RETENTION_DAYS + 5)),
            VisitRecord(ip="recent", visited_at=now - timedelta(days=30)),
        ])
        db.commit()
    module.VisitService._last_prune = None
    module.VisitService().log_visit("9.9.9.9")
    with SessionLocal() as db:
        remaining = {row.ip for row in db.query(VisitRecord).all()}
    assert "old" not in remaining and {"recent", "9.9.9.9"} <= remaining
    # a second visit the same day does not prune again
    with SessionLocal() as db:
        db.add(VisitRecord(ip="old2", visited_at=now - timedelta(days=module.RETENTION_DAYS + 5)))
        db.commit()
    module.VisitService().log_visit("8.8.8.8")
    with SessionLocal() as db:
        assert db.query(VisitRecord).filter(VisitRecord.ip == "old2").count() == 1
