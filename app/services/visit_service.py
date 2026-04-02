from __future__ import annotations

from datetime import datetime, timedelta

from app.database.db import SessionLocal
from app.database.models import Visit as VisitRecord
from app.models.schemas import Visit


class VisitService:
    @staticmethod
    def _to_visit(record: VisitRecord) -> Visit:
        return Visit(ip=record.ip, time=record.visited_at)

    def log_visit(self, ip_address: str) -> None:
        db = SessionLocal()
        try:
            db.add(VisitRecord(ip=ip_address.strip() or "unknown"))
            db.commit()
        finally:
            db.close()

    def list_visits(self) -> list[Visit]:
        db = SessionLocal()
        try:
            records = db.query(VisitRecord).order_by(VisitRecord.visited_at.asc()).all()
            return [self._to_visit(record) for record in records]
        finally:
            db.close()

    def summary(self) -> dict[str, int]:
        visits = self.list_visits()
        today_key = datetime.now().strftime("%Y-%m-%d")
        return {
            "total": len(visits),
            "today": sum(1 for visit in visits if visit.time.strftime("%Y-%m-%d") == today_key),
            "unique_ips": len({visit.ip for visit in visits}),
        }

    def analytics(self, period: str) -> dict[str, object]:
        visits = self.list_visits()
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        config = {
            "week": (now - timedelta(days=7), "Last 7 Days", "%Y-%m-%d", "%a %d"),
            "month": (now - timedelta(days=30), "Last 30 Days", "%Y-%m-%d", "%b %d"),
            "year": (now - timedelta(days=365), "Last 12 Months", "%Y-%m", "%b %Y"),
            "all": (datetime(2000, 1, 1), "All Time", "%Y-%m", "%b %Y"),
        }
        active_period = period if period in {"today", *config.keys()} else "week"

        if active_period == "today":
            label = "Today"
            group_key = "%H"
            display_format = "%I %p"
            filtered = [
                visit for visit in visits if visit.time.strftime("%Y-%m-%d") == today_key
            ]
        else:
            cutoff, label, group_key, display_format = config[active_period]
            filtered = [visit for visit in visits if visit.time >= cutoff]

        grouped: dict[str, int] = {}
        for visit in filtered:
            key = visit.time.strftime(group_key)
            grouped[key] = grouped.get(key, 0) + 1

        max_count = max(grouped.values(), default=1)
        chart = []
        for key in sorted(grouped):
            count = grouped[key]
            chart.append(
                {
                    "key": key,
                    "count": count,
                    "height": max(4, round((count / max_count) * 100)),
                    "label": datetime.strptime(key, group_key).strftime(display_format),
                }
            )

        ip_counts: dict[str, int] = {}
        for visit in filtered:
            ip_counts[visit.ip] = ip_counts.get(visit.ip, 0) + 1

        return {
            "period": active_period,
            "label": label,
            "filtered": filtered,
            "chart": chart,
            "today_count": sum(
                1 for visit in filtered if visit.time.strftime("%Y-%m-%d") == today_key
            ),
            "unique_ips": len({visit.ip for visit in filtered}),
            "all_time_total": len(visits),
            "top_ips": sorted(ip_counts.items(), key=lambda item: item[1], reverse=True)[:10],
        }
