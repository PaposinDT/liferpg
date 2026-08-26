from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    AchievementUnlock,
    Activity,
    Character,
    Checkpoint,
    Skill,
    TimelineEvent,
    WeightLog,
)

from app.today_service import local_today


RARITY_SCORE = {
    "COMMON": 1,
    "UNCOMMON": 2,
    "RARE": 3,
    "EPIC": 4,
    "LEGENDARY": 5,
}


def metric_value(session, achievement):
    kind = achievement.criteria_type

    if kind == "CHARACTER_LEVEL":
        char = session.scalar(
            select(Character).limit(1)
        )
        return char.character_level if char else 0

    if kind == "ANY_SKILL_LEVEL":
        return session.scalar(
            select(func.max(Skill.current_level))
        ) or 0

    if kind == "SKILL_LEVEL":
        skill = session.scalar(
            select(Skill).where(
                Skill.code
                == achievement.criteria_skill_code
            )
        )
        return skill.current_level if skill else 0

    if kind == "ACTIVITY_COUNT":
        return session.scalar(
            select(func.count(Activity.id)).where(
                Activity.deleted_at.is_(None)
            )
        ) or 0

    if kind == "CHECKPOINT_COUNT":
        return session.scalar(
            select(func.count(Checkpoint.id)).where(
                Checkpoint.status == "CLEARED"
            )
        ) or 0

    if kind == "WEIGHT_G":
        weight = session.scalar(
            select(WeightLog)
            .where(WeightLog.valid.is_(True))
            .order_by(WeightLog.measured_at.desc())
            .limit(1)
        )
        return weight.weight_g if weight else 0

    return 0


def add_timeline(
    session,
    key,
    event_type,
    title,
    description,
    significance=1,
):
    existing = session.scalar(
        select(TimelineEvent).where(
            TimelineEvent.event_key == key
        )
    )

    if existing:
        return existing

    event = TimelineEvent(
        event_key=key,
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc),
        local_date=local_today(),
        title=title,
        description=description,
        significance=significance,
    )

    session.add(event)
    session.flush()

    return event


def refresh_achievements(
    session: Session,
    source_type="SYSTEM",
):
    achievements = session.scalars(
        select(Achievement).where(
            Achievement.active.is_(True)
        )
    ).all()

    unlocked = set(
        session.scalars(
            select(
                AchievementUnlock.achievement_id
            )
        ).all()
    )

    new = []

    for achievement in achievements:
        if achievement.id in unlocked:
            continue

        if (
            metric_value(
                session,
                achievement,
            )
            < achievement.threshold_value
        ):
            continue

        session.add(
            AchievementUnlock(
                achievement_id=achievement.id,
                source_type=source_type,
            )
        )

        add_timeline(
            session,
            key=(
                "achievement:"
                + achievement.code
            ),
            event_type="ACHIEVEMENT",
            title=achievement.name,
            description=(
                achievement.rarity.title()
                + " achievement unlocked."
            ),
            significance=RARITY_SCORE.get(
                achievement.rarity,
                1,
            ),
        )

        new.append(achievement)

    session.flush()

    return new
