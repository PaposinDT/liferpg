from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ScheduledJob
from app.settings import TIMEZONE_NAME


JOBS = [
    ("generate_today", "Prepare the current day", 0, 5),
    ("close_previous_day", "Close yesterday if still open", 3, 0),
    ("daily_checkin", "Evening Telegram check-in", 21, 0),
]


def main() -> None:
    with SessionLocal() as session:
        for code, description, hour, minute in JOBS:
            row = session.scalar(select(ScheduledJob).where(ScheduledJob.code == code))
            if row is None:
                row = ScheduledJob(code=code)
                session.add(row)
            row.description = description
            row.local_hour = hour
            row.local_minute = minute
            row.timezone = TIMEZONE_NAME
            row.enabled = True
        session.commit()
    print(f"Scheduler jobs applied: {len(JOBS)} ({TIMEZONE_NAME})")


if __name__ == "__main__":
    main()
