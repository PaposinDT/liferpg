from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailySnapshot, HabitLog
from app.settings import FOCUS_HABIT_CODE, NUTRITION_ENABLED
from app.streak_service import get_habit_stats
from app.today_service import (
    find_habit,
    get_or_create_habit_log,
    get_or_create_nutrition,
    local_today,
    sync_focus_habit,
)


@dataclass
class DayCloseResult:
    local_date: date
    focus_state: str
    nutrition_state: str
    closed_days: int
    disc_ranked: bool

    @property
    def russian_state(self) -> str:
        return self.focus_state


def get_daily_snapshot(session: Session, day: date):
    return session.scalar(
        select(DailySnapshot).where(DailySnapshot.local_date == day)
    )


def is_day_closed(session: Session, day: date | None = None):
    if day is None:
        day = local_today()
    snapshot = get_daily_snapshot(session, day)
    return snapshot is not None and snapshot.status == "CLOSED"


def closed_day_count(session: Session):
    return len(
        session.scalars(
            select(DailySnapshot).where(DailySnapshot.status == "CLOSED")
        ).all()
    )


def disc_status(session: Session):
    count = closed_day_count(session)
    return {
        "ranked": False,
        "score": None,
        "closed_days": count,
    }


def close_day(
    session: Session,
    day: date | None = None,
    manual: bool = False,
):
    if day is None:
        day = local_today()

    _, _, focus_state, _ = sync_focus_habit(session, day)
    focus_habit = find_habit(session, FOCUS_HABIT_CODE)
    if focus_habit is not None and focus_habit.status == "ACTIVE":
        focus_log = get_or_create_habit_log(session, focus_habit, day)
        if focus_log.state == "PENDING":
            focus_log.state = "MISSED"
            focus_log.finalized_by_close = True
        focus_state = focus_log.state
    else:
        focus_log = None
        focus_state = "DISABLED"

    nutrition_state = "DISABLED"
    nutrition = get_or_create_nutrition(session, day)
    nutrition_habit = (
        find_habit(session, "nutrition_target")
        or find_habit(session, "nutrition_surplus")
    )
    if NUTRITION_ENABLED and nutrition is not None and nutrition_habit is not None:
        nutrition_log = get_or_create_habit_log(session, nutrition_habit, day)
        if nutrition_log.state == "PENDING":
            nutrition_log.state = "MISSED"
            nutrition_log.finalized_by_close = True
            nutrition.target_reached = False
        nutrition_state = nutrition_log.state
    else:
        nutrition_log = None

    snapshot = get_daily_snapshot(session, day)
    if snapshot is None:
        snapshot = DailySnapshot(local_date=day)
        session.add(snapshot)

    snapshot.status = "CLOSED"
    snapshot.closed_at = datetime.now(timezone.utc)
    snapshot.closed_manually = manual
    # Legacy column name retained for migration compatibility; it stores the configured daily focus state.
    snapshot.russian_state = focus_state
    snapshot.nutrition_state = nutrition_state
    snapshot.disc_ranked = False
    snapshot.disc_score = None

    session.flush()

    if focus_habit is not None and focus_habit.status == "ACTIVE":
        get_habit_stats(session, focus_habit.code, day)
    if nutrition_habit is not None and nutrition_habit.status == "ACTIVE":
        get_habit_stats(session, nutrition_habit.code, day)

    count = closed_day_count(session)
    return DayCloseResult(
        local_date=day,
        focus_state=focus_state,
        nutrition_state=nutrition_state,
        closed_days=count,
        disc_ranked=False,
    )


def reopen_day(session: Session, day: date | None = None):
    if day is None:
        day = local_today()

    snapshot = get_daily_snapshot(session, day)
    if snapshot is None or snapshot.status != "CLOSED":
        raise ValueError("Day is not closed.")

    logs = session.scalars(
        select(HabitLog).where(
            HabitLog.local_date == day,
            HabitLog.finalized_by_close.is_(True),
        )
    ).all()

    nutrition_habit = (
        find_habit(session, "nutrition_target")
        or find_habit(session, "nutrition_surplus")
    )
    nutrition = get_or_create_nutrition(session, day)

    for log in logs:
        log.state = "PENDING"
        log.finalized_by_close = False
        if (
            nutrition_habit is not None
            and nutrition is not None
            and log.habit_id == nutrition_habit.id
            and nutrition.target_reached is False
        ):
            nutrition.target_reached = None

    snapshot.status = "OPEN"
    snapshot.closed_at = None
    snapshot.closed_manually = False
    snapshot.disc_ranked = False
    snapshot.disc_score = None
    session.flush()
    return snapshot
