from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Habit,
    HabitLog,
    StreakState,
)


@dataclass
class HabitStats:
    code: str
    current_streak: int
    best_streak: int

    rate_7: float | None
    rate_30: float | None
    rate_90: float | None


def _rate(
    logs: list[HabitLog],
    today: date,
    days: int,
):
    cutoff = today - timedelta(
        days=days - 1
    )

    eligible = [
        log
        for log in logs
        if log.local_date >= cutoff
        and log.state in ("DONE", "MISSED")
    ]

    if not eligible:
        return None

    done = sum(
        1
        for log in eligible
        if log.state == "DONE"
    )

    return (
        done / len(eligible)
    ) * 100


def calculate_stats(
    logs: list[HabitLog],
    today: date,
):
    ordered = sorted(
        logs,
        key=lambda log: log.local_date,
    )

    best = 0
    running = 0

    for log in ordered:
        if log.state == "DONE":
            running += 1
            best = max(best, running)

        elif log.state == "MISSED":
            running = 0

        elif log.state in (
            "PAUSED",
            "PENDING",
        ):
            continue

    current = 0

    for log in reversed(ordered):
        if log.state in (
            "PENDING",
            "PAUSED",
        ):
            continue

        if log.state == "DONE":
            current += 1
            continue

        if log.state == "MISSED":
            break

    return {
        "current": current,
        "best": best,

        "rate_7": _rate(
            ordered,
            today,
            7,
        ),

        "rate_30": _rate(
            ordered,
            today,
            30,
        ),

        "rate_90": _rate(
            ordered,
            today,
            90,
        ),
    }


def get_habit_stats(
    session: Session,
    habit_code: str,
    today: date,
):
    habit = session.scalar(
        select(Habit).where(
            Habit.code == habit_code
        )
    )

    if habit is None:
        raise RuntimeError(
            f"Habit not found: {habit_code}"
        )

    logs = session.scalars(
        select(HabitLog)
        .where(
            HabitLog.habit_id == habit.id,
            HabitLog.local_date <= today,
        )
        .order_by(HabitLog.local_date)
    ).all()

    stats = calculate_stats(
        logs,
        today,
    )

    state = session.scalar(
        select(StreakState).where(
            StreakState.habit_id == habit.id
        )
    )

    if state is None:
        state = StreakState(
            habit_id=habit.id
        )
        session.add(state)

    state.current_streak = stats["current"]
    state.best_streak = stats["best"]

    state.rate_7_bp = (
        None
        if stats["rate_7"] is None
        else round(stats["rate_7"] * 100)
    )

    state.rate_30_bp = (
        None
        if stats["rate_30"] is None
        else round(stats["rate_30"] * 100)
    )

    state.rate_90_bp = (
        None
        if stats["rate_90"] is None
        else round(stats["rate_90"] * 100)
    )

    return HabitStats(
        code=habit_code,
        current_streak=stats["current"],
        best_streak=stats["best"],
        rate_7=stats["rate_7"],
        rate_30=stats["rate_30"],
        rate_90=stats["rate_90"],
    )
