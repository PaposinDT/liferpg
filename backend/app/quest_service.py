import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Quest,
    QuestSchedule,
    Skill,
)


TIMEZONE_NAME = os.getenv(
    "LIFERPG_TIMEZONE",
    "UTC",
)


@dataclass
class WeeklyOperation:
    quest_code: str
    title: str
    skill_code: str
    skill_name: str

    current: int
    minimum: int
    stretch: int

    minimum_met: bool
    stretch_met: bool

    week_start: date
    week_end: date


def life_timezone():
    return ZoneInfo(
        TIMEZONE_NAME
    )


def current_local_date():
    return datetime.now(
        life_timezone()
    ).date()


def week_dates(
    day: date | None = None,
):
    if day is None:
        day = current_local_date()

    monday = day - timedelta(
        days=day.weekday()
    )

    sunday = monday + timedelta(
        days=6
    )

    return monday, sunday


def utc_window_for_local_dates(
    start_day: date,
    end_day: date,
):
    tz = life_timezone()

    start_local = datetime.combine(
        start_day,
        time.min,
        tzinfo=tz,
    )

    # Exclusive upper bound.
    end_local = datetime.combine(
        end_day + timedelta(days=1),
        time.min,
        tzinfo=tz,
    )

    return (
        start_local.astimezone(
            timezone.utc
        ),
        end_local.astimezone(
            timezone.utc
        ),
    )


def count_skill_sessions(
    session: Session,
    skill_id: int,
    start_day: date,
    end_day: date,
):
    start_utc, end_utc = (
        utc_window_for_local_dates(
            start_day,
            end_day,
        )
    )

    activities = session.scalars(
        select(Activity).where(
            Activity.primary_skill_id
            == skill_id,

            Activity.deleted_at.is_(None),

            Activity.occurred_at
            >= start_utc,

            Activity.occurred_at
            < end_utc,
        )
    ).all()

    return len(activities)


def get_weekly_operations(
    session: Session,
    day: date | None = None,
):
    week_start, week_end = (
        week_dates(day)
    )

    rows = session.execute(
        select(
            Quest,
            QuestSchedule,
            Skill,
        )
        .join(
            QuestSchedule,
            QuestSchedule.quest_id
            == Quest.id,
        )
        .join(
            Skill,
            Skill.id == Quest.skill_id,
        )
        .where(
            Quest.status == "ACTIVE",
            QuestSchedule.active.is_(True),
            QuestSchedule.cadence
            == "WEEKLY",
        )
        .order_by(
            Quest.id
        )
    ).all()

    operations = []

    for quest, schedule, skill in rows:
        current = count_skill_sessions(
            session=session,
            skill_id=skill.id,
            start_day=week_start,
            end_day=week_end,
        )

        minimum = (
            schedule.minimum_required
            or 0
        )

        stretch = (
            schedule.stretch_target
            or minimum
        )

        operations.append(
            WeeklyOperation(
                quest_code=quest.code,
                title=quest.title,
                skill_code=skill.code,
                skill_name=skill.name,

                current=current,
                minimum=minimum,
                stretch=stretch,

                minimum_met=(
                    current >= minimum
                ),
                stretch_met=(
                    current >= stretch
                ),

                week_start=week_start,
                week_end=week_end,
            )
        )

    return operations


def priority_operations(
    session: Session,
    limit: int = 3,
):
    operations = get_weekly_operations(
        session
    )

    pending = [
        operation
        for operation in operations
        if not operation.minimum_met
    ]

    priority_rank = {
        "MAIN": 0,
        "SIDE": 1,
        "MAINTENANCE": 2,
        "BACKGROUND": 3,
    }

    skill_priority = {
        skill.code: skill.priority
        for skill in session.scalars(select(Skill)).all()
    }

    def sort_key(operation):
        rank = priority_rank.get(
            skill_priority.get(operation.skill_code, "BACKGROUND"),
            9,
        )
        ratio = (
            operation.current / operation.minimum
            if operation.minimum > 0
            else 1.0
        )
        return (rank, ratio, operation.skill_name.lower())

    pending.sort(
        key=sort_key
    )

    return pending[:limit]
