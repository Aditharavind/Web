from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DataAccessError
from app.database.db import SessionLocal
from app.database.models import Visit as VisitRecord
from app.models.schemas import Visit

logger = logging.getLogger(__name__)


class VisitService:
    def log_visit(self, ip_address: str) -> None:
        with SessionLocal() as db:
            try:
                db.add(VisitRecord(ip=ip_address.strip() or "unknown"))
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Failed to record visit.")

    def recent_visits(self, limit: int = 50) -> list[Visit]:
        with SessionLocal() as db:
            rows = (
                db.query(VisitRecord)
                .order_by(VisitRecord.visited_at.desc())
                .limit(limit)
                .all()
            )
            return [Visit(ip=row.ip, time=row.visited_at) for row in reversed(rows)]

    def summary(self) -> dict[str, int]:
        today = (
            datetime.now(UTC)
            .replace(tzinfo=None)
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        with SessionLocal() as db:
            total, today_count, unique_ips = db.query(
                func.count(VisitRecord.id),
                func.coalesce(
                    func.sum(case((VisitRecord.visited_at >= today, 1), else_=0)), 0
                ),
                func.count(func.distinct(VisitRecord.ip)),
            ).one()
            return {"total": total, "today": today_count, "unique_ips": unique_ips}

    def analytics(self, period: str) -> dict[str, object]:
        now = datetime.now(UTC).replace(tzinfo=None)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        config = {
            "today": (today, "Today", "%Y-%m-%d %H", "YYYY-MM-DD HH24", "%I %p"),
            "week": (
                now - timedelta(days=7),
                "Last 7 Days",
                "%Y-%m-%d",
                "YYYY-MM-DD",
                "%a %d",
            ),
            "month": (
                now - timedelta(days=30),
                "Last 30 Days",
                "%Y-%m-%d",
                "YYYY-MM-DD",
                "%b %d",
            ),
            "year": (
                now - timedelta(days=365),
                "Last 12 Months",
                "%Y-%m",
                "YYYY-MM",
                "%b %Y",
            ),
            "all": (datetime(2000, 1, 1), "All Time", "%Y-%m", "YYYY-MM", "%b %Y"),
        }
        period = period if period in config else "week"
        cutoff, label, sqlite_format, pg_format, display_format = config[period]
        try:
            with SessionLocal() as db:
                query = db.query(VisitRecord).filter(VisitRecord.visited_at >= cutoff)
                bucket = (
                    func.strftime(sqlite_format, VisitRecord.visited_at)
                    if db.bind.dialect.name == "sqlite"
                    else func.to_char(VisitRecord.visited_at, pg_format)
                )
                grouped = (
                    query.with_entities(bucket, func.count())
                    .group_by(bucket)
                    .order_by(bucket)
                    .all()
                )
                maximum = max((count for _, count in grouped), default=1)
                total = sum(count for _, count in grouped)
                today_count, unique_ips = query.with_entities(
                    func.coalesce(
                        func.sum(case((VisitRecord.visited_at >= today, 1), else_=0)), 0
                    ),
                    func.count(func.distinct(VisitRecord.ip)),
                ).one()
                recent = query.order_by(VisitRecord.visited_at.desc()).limit(50).all()
                return {
                    "period": period,
                    "label": label,
                    "total": total,
                    "filtered": [
                        Visit(ip=row.ip, time=row.visited_at)
                        for row in reversed(recent)
                    ],
                    "today_count": today_count,
                    "unique_ips": unique_ips,
                    "all_time_total": db.query(VisitRecord).count(),
                    "top_ips": query.with_entities(VisitRecord.ip, func.count())
                    .group_by(VisitRecord.ip)
                    .order_by(func.count().desc())
                    .limit(10)
                    .all(),
                    "chart": [
                        {
                            "key": key,
                            "count": count,
                            "height": max(4, round(count / maximum * 100)),
                            "label": datetime.strptime(key, sqlite_format).strftime(
                                display_format
                            ),
                        }
                        for key, count in grouped
                    ],
                }
        except SQLAlchemyError as exc:
            raise DataAccessError("Unable to load visitor analytics.") from exc
