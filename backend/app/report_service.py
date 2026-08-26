from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    DailySnapshot,
    Habit,
    HabitLog,
    Report,
    Skill,
    WeightLog,
)

from app.today_service import (
    local_today,
    utc_day_window,
)


def previous_week():
    today = local_today()

    monday = today - timedelta(
        days=today.weekday()
    )

    return (
        monday - timedelta(days=7),
        monday - timedelta(days=1),
    )


def previous_month():
    today = local_today()

    first_current = date(
        today.year,
        today.month,
        1,
    )

    end = first_current - timedelta(days=1)

    start = date(
        end.year,
        end.month,
        1,
    )

    return start, end


def latest_report(
    session,
    report_type,
    start,
    end,
):
    return session.scalar(
        select(Report)
        .where(
            Report.report_type == report_type,
            Report.period_start == start,
            Report.period_end == end,
        )
        .order_by(
            Report.version.desc()
        )
        .limit(1)
    )


def build_report(
    session: Session,
    report_type: str,
    start: date,
    end: date,
):
    start_utc, _ = utc_day_window(
        start
    )

    _, end_utc = utc_day_window(
        end
    )

    activities = session.scalars(
        select(Activity)
        .where(
            Activity.deleted_at.is_(None),
            Activity.occurred_at >= start_utc,
            Activity.occurred_at < end_utc,
        )
        .order_by(Activity.occurred_at)
    ).all()

    skills = {
        skill.id: skill.name
        for skill in session.scalars(
            select(Skill)
        ).all()
    }

    total_minutes = sum(
        activity.duration_minutes or 0
        for activity in activities
    )

    by_skill = {}

    for activity in activities:
        name = skills.get(
            activity.primary_skill_id,
            "Unknown",
        )

        data = by_skill.setdefault(
            name,
            [0, 0],
        )

        data[0] += 1
        data[1] += (
            activity.duration_minutes or 0
        )

    closed_days = session.scalar(
        select(
            func.count(
                DailySnapshot.id
            )
        ).where(
            DailySnapshot.local_date >= start,
            DailySnapshot.local_date <= end,
            DailySnapshot.status == "CLOSED",
        )
    ) or 0

    lines = [
        report_type + " REPORT",
        "",
        (
            f"{start.strftime('%d %b %Y')} "
            f"-> {end.strftime('%d %b %Y')}"
        ),
        "",
        "OPERATIONS",
        f"Activities: {len(activities)}",
        f"Logged time: {total_minutes} min",
        f"Closed days: {closed_days}",
    ]

    if by_skill:
        lines.extend([
            "",
            "SKILLS",
        ])

        for name, data in sorted(
            by_skill.items(),
            key=lambda x: (
                -x[1][0],
                x[0],
            ),
        ):
            lines.append(
                f"- {name}: "
                f"{data[0]} sessions, "
                f"{data[1]} min"
            )

    lines.extend([
        "",
        "HABITS",
    ])

    habits = session.scalars(
        select(Habit).where(
            Habit.status == "ACTIVE"
        )
    ).all()

    for habit in habits:
        logs = session.scalars(
            select(HabitLog).where(
                HabitLog.habit_id == habit.id,
                HabitLog.local_date >= start,
                HabitLog.local_date <= end,
                HabitLog.state.in_(
                    ["DONE", "MISSED"]
                ),
            )
        ).all()

        if not logs:
            lines.append(
                f"- {habit.name}: no data"
            )
            continue

        done = sum(
            log.state == "DONE"
            for log in logs
        )

        rate = (
            done / len(logs) * 100
        )

        lines.append(
            f"- {habit.name}: "
            f"{done}/{len(logs)} "
            f"({rate:.0f}%)"
        )

    weights = session.scalars(
        select(WeightLog)
        .where(
            WeightLog.valid.is_(True),
            WeightLog.local_date >= start,
            WeightLog.local_date <= end,
        )
        .order_by(
            WeightLog.measured_at
        )
    ).all()

    lines.extend([
        "",
        "BODY",
    ])

    if not weights:
        lines.append(
            "- No valid weigh-ins"
        )

    else:
        first = (
            weights[0].weight_g / 1000
        )

        latest = (
            weights[-1].weight_g / 1000
        )

        lines.append(
            f"- First: {first:.1f} kg"
        )

        lines.append(
            f"- Latest: {latest:.1f} kg"
        )

        lines.append(
            f"- Change: "
            f"{latest - first:+.1f} kg"
        )

    if (
        len(activities) == 0
        and closed_days == 0
    ):
        lines.extend([
            "",
            "DATA STATUS: insufficient history.",
        ])

    return "\n".join(lines)


def get_report(
    session: Session,
    report_type: str,
    refresh: bool = False,
):
    report_type = report_type.upper()

    if report_type == "WEEKLY":
        start, end = previous_week()

    elif report_type == "MONTHLY":
        start, end = previous_month()

    else:
        raise ValueError(
            "Use WEEKLY or MONTHLY."
        )

    existing = latest_report(
        session,
        report_type,
        start,
        end,
    )

    if (
        existing is not None
        and not refresh
    ):
        return existing, False

    version = (
        1
        if existing is None
        else existing.version + 1
    )

    report = Report(
        report_type=report_type,
        period_start=start,
        period_end=end,
        version=version,
        status="FROZEN",
        content_text=build_report(
            session,
            report_type,
            start,
            end,
        ),
    )

    session.add(report)
    session.flush()

    return report, True
