from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import func, select

from app.character_service import get_character
from app.db import SessionLocal
from app.settings import TIMEZONE_NAME
from app.models import (
    Achievement,
    AchievementUnlock,
    Category,
    Character,
    DailySnapshot,
    Habit,
    HabitLog,
    NutritionDaily,
    Quest,
    QuestInstance,
    QuestSchedule,
    Report,
    Skill,
    SkillLevelThreshold,
    SkillProgressionVersion,
    Checkpoint,
    TimelineEvent,
    WeightLog,
)
from app.quest_service import (
    get_weekly_operations,
    priority_operations,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


def local_today():
    tz = ZoneInfo(TIMEZONE_NAME)
    return datetime.now(tz).date()


@router.get("/overview")
def dashboard_overview():
    day = local_today()

    with SessionLocal() as session:
        character = get_character(session)

        weekly = get_weekly_operations(
            session,
            day,
        )

        priority = priority_operations(
            session=session,
            limit=3,
        )

        habits = session.execute(
            select(Habit, HabitLog)
            .outerjoin(
                HabitLog,
                (HabitLog.habit_id == Habit.id)
                & (HabitLog.local_date == day),
            )
            .where(
                Habit.status == "ACTIVE",
                Habit.code.notin_(["nutrition_target", "nutrition_surplus"]),
            )
            .order_by(Habit.id)
        ).all()

        nutrition = session.scalar(
            select(NutritionDaily).where(
                NutritionDaily.local_date == day
            )
        )

        latest_weight = session.scalar(
            select(WeightLog)
            .where(
                WeightLog.valid.is_(True)
            )
            .order_by(
                WeightLog.measured_at.desc()
            )
            .limit(1)
        )

        daily = session.scalar(
            select(DailySnapshot).where(
                DailySnapshot.local_date == day
            )
        )

        return {
            "date": day.isoformat(),
            "character": (
                {
                    "name": character.name,
                    "level": character.character_level,
                    "xp": character.character_xp,
                    "title": character.current_title,
                }
                if character
                else None
            ),
            "priority_operations": [
                {
                    "quest_code": op.quest_code,
                    "title": op.title,
                    "skill_code": op.skill_code,
                    "skill": op.skill_name,
                    "current": op.current,
                    "minimum": op.minimum,
                    "stretch": op.stretch,
                }
                for op in priority
            ],

            "weekly_operations": [
                {
                    "quest_code": op.quest_code,
                    "title": op.title,
                    "skill_code": op.skill_code,
                    "skill": op.skill_name,
                    "current": op.current,
                    "minimum": op.minimum,
                    "stretch": op.stretch,
                    "minimum_met": op.minimum_met,
                    "stretch_met": op.stretch_met,
                }
                for op in weekly
            ],
            "habits": [
                {
                    "code": habit.code,
                    "name": habit.name,
                    "minimum_minutes": habit.minimum_minutes,
                    "state": (
                        log.state
                        if log
                        else "PENDING"
                    ),
                    "value": (
                        log.value_int
                        if log
                        else None
                    ),
                }
                for habit, log in habits
            ],

            "nutrition": (
                {
                    "base_target_kcal":
                        nutrition.base_target_kcal,
                    "adjusted_target_kcal":
                        nutrition.adjusted_target_kcal,
                    "target_reached":
                        nutrition.target_reached,
                }
                if nutrition
                else None
            ),
            "weight": (
                {
                    "kg": latest_weight.weight_g / 1000,
                    "date":
                        latest_weight.local_date.isoformat(),
                }
                if latest_weight
                else None
            ),
            "day": (
                {
                    "status": daily.status,
                    "disc_ranked": daily.disc_ranked,
                    "disc_score": daily.disc_score,
                }
                if daily
                else None
            ),
        }


@router.get("/character")
def dashboard_character():
    with SessionLocal() as session:
        character = get_character(session)

        unlocked = session.scalar(
            select(
                func.count(
                    AchievementUnlock.id
                )
            )
        ) or 0

        total = session.scalar(
            select(
                func.count(
                    Achievement.id
                )
            ).where(
                Achievement.active.is_(True)
            )
        ) or 0

        return {
            "character": (
                {
                    "name": character.name,
                    "level": character.character_level,
                    "xp": character.character_xp,
                    "title": character.current_title,
                }
                if character
                else None
            ),
            "achievements": {
                "unlocked": unlocked,
                "total": total,
            },
        }


@router.get("/skills")
def dashboard_skills():
    with SessionLocal() as session:
        rows = session.execute(
            select(Skill, Category)
            .join(
                Category,
                Category.id == Skill.category_id,
            )
            .where(
                Skill.deleted_at.is_(None)
            )
            .order_by(
                Category.sort_order,
                Skill.name,
            )
        ).all()

        result = []

        for skill, category in rows:
            progression = session.scalar(
                select(SkillProgressionVersion)
                .where(
                    SkillProgressionVersion.skill_id
                    == skill.id,
                    SkillProgressionVersion.active.is_(True),
                )
                .limit(1)
            )

            current_threshold = 0
            next_threshold = None

            if progression:
                current_threshold = (
                    session.scalar(
                        select(
                            SkillLevelThreshold
                            .cumulative_xp_required
                        ).where(
                            SkillLevelThreshold
                            .progression_version_id
                            == progression.id,
                            SkillLevelThreshold.level
                            == skill.current_level,
                        )
                    )
                    or 0
                )

                if skill.current_level < skill.level_cap:
                    next_threshold = session.scalar(
                        select(
                            SkillLevelThreshold
                            .cumulative_xp_required
                        ).where(
                            SkillLevelThreshold
                            .progression_version_id
                            == progression.id,
                            SkillLevelThreshold.level
                            == skill.current_level + 1,
                        )
                    )

            checkpoint = session.scalar(
                select(Checkpoint)
                .where(
                    Checkpoint.skill_id == skill.id,
                    Checkpoint.level >= skill.current_level,
                    Checkpoint.status != "CLEARED",
                )
                .order_by(Checkpoint.level)
                .limit(1)
            )

            span = (
                next_threshold - current_threshold
                if next_threshold is not None
                else 0
            )

            progress = (
                skill.total_xp - current_threshold
                if span > 0
                else 0
            )

            progress_pct = (
                max(
                    0,
                    min(
                        100,
                        round(progress / span * 100),
                    ),
                )
                if span > 0
                else 100
            )

            result.append({
                "code": skill.code,
                "name": skill.name,
                "category": category.name,
                "level": skill.current_level,
                "xp": skill.total_xp,
                "banked_xp": skill.banked_xp,
                "cap": skill.level_cap,
                "priority": skill.priority,
                "status": skill.status,
                "state": skill.current_state,
                "end_goal": skill.end_goal,

                "level_progress": {
                    "current_threshold":
                        current_threshold,
                    "next_threshold":
                        next_threshold,
                    "xp_into_level":
                        max(0, progress),
                    "xp_required":
                        span,
                    "percent":
                        progress_pct,
                },

                "checkpoint": (
                    {
                        "level": checkpoint.level,
                        "name": checkpoint.name,
                        "status": checkpoint.status,
                        "reached":
                            checkpoint.reached_at
                            is not None,
                    }
                    if checkpoint
                    else None
                ),
            })

        return result


@router.get("/quests")
def dashboard_quests():
    day = local_today()

    with SessionLocal() as session:
        weekly_map = {
            op.quest_code: op
            for op in get_weekly_operations(
                session,
                day,
            )
        }

        latest_weight = session.scalar(
            select(WeightLog)
            .where(
                WeightLog.valid.is_(True)
            )
            .order_by(
                WeightLog.measured_at.desc()
            )
            .limit(1)
        )

        rows = session.execute(
            select(
                Quest,
                Skill,
                QuestSchedule,
            )
            .outerjoin(
                Skill,
                Skill.id == Quest.skill_id,
            )
            .outerjoin(
                QuestSchedule,
                QuestSchedule.quest_id
                == Quest.id,
            )
            .where(
                Quest.deleted_at.is_(None)
            )
            .order_by(
                Quest.status,
                Quest.quest_type,
                Quest.id,
            )
        ).all()

        result = []

        for quest, skill, schedule in rows:
            weekly = weekly_map.get(
                quest.code
            )

            weekly_progress = None

            if weekly is not None:
                weekly_progress = {
                    "current": weekly.current,
                    "minimum": weekly.minimum,
                    "stretch": weekly.stretch,
                    "minimum_met":
                        weekly.minimum_met,
                    "stretch_met":
                        weekly.stretch_met,
                    "percent": (
                        min(
                            100,
                            round(
                                weekly.current
                                / weekly.minimum
                                * 100
                            ),
                        )
                        if weekly.minimum > 0
                        else 100
                    ),
                }

            goal_progress = None

            target = (
                float(quest.target_value)
                if quest.target_value
                is not None
                else None
            )

            unit = (
                quest.target_unit or ""
            ).upper()

            current = None
            source = None

            if (
                skill is not None
                and unit in {
                    "LVL",
                    "LEVEL",
                    "LEVELS",
                    "SKILL_LEVEL",
                }
            ):
                current = float(
                    skill.current_level
                )
                source = "SKILL_LEVEL"

            elif (
                latest_weight is not None
                and unit in {
                    "G",
                    "GRAM",
                    "GRAMS",
                    "WEIGHT_G",
                }
            ):
                current = float(
                    latest_weight.weight_g
                )
                source = "WEIGHT"

            else:
                instance = session.scalar(
                    select(QuestInstance)
                    .where(
                        QuestInstance.quest_id
                        == quest.id
                    )
                    .order_by(
                        QuestInstance.local_date
                        .desc()
                    )
                    .limit(1)
                )

                if (
                    instance is not None
                    and instance.progress_current
                    is not None
                ):
                    current = float(
                        instance.progress_current
                    )
                    source = "INSTANCE"

                    if (
                        target is None
                        and instance.progress_target
                        is not None
                    ):
                        target = float(
                            instance.progress_target
                        )

            if (
                current is not None
                and target is not None
                and target > 0
            ):
                goal_progress = {
                    "current": current,
                    "target": target,
                    "unit": quest.target_unit,
                    "source": source,
                    "percent": max(
                        0,
                        min(
                            100,
                            round(
                                current
                                / target
                                * 100
                            ),
                        ),
                    ),
                }

            result.append({
                "code": quest.code,
                "title": quest.title,
                "type": quest.quest_type,
                "status": quest.status,
                "description":
                    quest.description,

                "skill_code": (
                    skill.code
                    if skill
                    else None
                ),
                "skill": (
                    skill.name
                    if skill
                    else None
                ),

                "target_value":
                    quest.target_value,
                "target_unit":
                    quest.target_unit,

                "target_date": (
                    quest.target_date.isoformat()
                    if quest.target_date
                    else None
                ),

                "schedule": (
                    {
                        "cadence":
                            schedule.cadence,
                        "minimum":
                            schedule.minimum_required,
                        "stretch":
                            schedule.stretch_target,
                        "active":
                            schedule.active,
                    }
                    if schedule
                    else None
                ),

                "weekly_progress":
                    weekly_progress,

                "goal_progress":
                    goal_progress,
            })

        return result


@router.get("/timeline")
def dashboard_timeline(limit: int = 100):
    limit = max(1, min(limit, 250))

    with SessionLocal() as session:
        rows = session.scalars(
            select(TimelineEvent)
            .order_by(
                TimelineEvent.occurred_at.desc()
            )
            .limit(limit)
        ).all()

        return [
            {
                "type": row.event_type,
                "date": row.local_date.isoformat(),
                "occurred_at":
                    row.occurred_at.isoformat(),
                "title": row.title,
                "description": row.description,
                "significance": row.significance,
            }
            for row in rows
        ]


@router.get("/reports")
def dashboard_reports():
    with SessionLocal() as session:
        rows = session.scalars(
            select(Report)
            .order_by(
                Report.generated_at.desc()
            )
            .limit(100)
        ).all()

        return [
            {
                "id": row.id,
                "type": row.report_type,
                "period_start":
                    row.period_start.isoformat(),
                "period_end":
                    row.period_end.isoformat(),
                "version": row.version,
                "status": row.status,
                "content": row.content_text,
                "generated_at":
                    row.generated_at.isoformat(),
            }
            for row in rows
        ]


@router.get("/achievements")
def dashboard_achievements():
    with SessionLocal() as session:
        rows = session.execute(
            select(
                Achievement,
                AchievementUnlock,
            )
            .outerjoin(
                AchievementUnlock,
                AchievementUnlock.achievement_id
                == Achievement.id,
            )
            .where(
                Achievement.active.is_(True)
            )
            .order_by(
                Achievement.rarity,
                Achievement.name,
            )
        ).all()

        result = []

        for achievement, unlock in rows:
            unlocked = unlock is not None
            hidden = (
                achievement.secret
                and not unlocked
            )

            result.append({
                "code": achievement.code,
                "name": (
                    "CLASSIFIED"
                    if hidden
                    else achievement.name
                ),
                "description": (
                    "Requirements classified."
                    if hidden
                    else achievement.description
                ),
                "category":
                    achievement.category,
                "rarity":
                    achievement.rarity,
                "secret":
                    achievement.secret,
                "unlocked": unlocked,
                "unlocked_at": (
                    unlock.unlocked_at.isoformat()
                    if unlock
                    else None
                ),
            })

        return result
