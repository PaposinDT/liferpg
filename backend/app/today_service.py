from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Habit, HabitLog, NutritionDaily, Skill, WeightLog
from app.settings import (
    FOCUS_HABIT_CODE,
    FOCUS_HABIT_LABEL,
    NUTRITION_ENABLED,
    NUTRITION_TARGET_KCAL,
    TIMEZONE_NAME,
    WEIGHT_TRACKING_ENABLED,
)


@dataclass
class TodaySnapshot:
    local_date: date
    focus_code: str | None
    focus_name: str
    focus_minutes: int
    focus_target: int
    focus_state: str
    nutrition_state: str
    nutrition_target_kcal: int
    latest_weight_kg: float | None
    latest_weight_date: date | None
    weight_due: bool

    # Compatibility aliases for the v1 schema/callers. These no longer imply Russian.
    @property
    def russian_minutes(self) -> int:
        return self.focus_minutes

    @property
    def russian_target(self) -> int:
        return self.focus_target

    @property
    def russian_state(self) -> str:
        return self.focus_state


def life_timezone() -> ZoneInfo:
    return ZoneInfo(TIMEZONE_NAME)


def local_today() -> date:
    return datetime.now(life_timezone()).date()


def utc_day_window(day: date):
    tz = life_timezone()
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def find_habit(session: Session, code: str) -> Habit | None:
    if not code:
        return None
    return session.scalar(select(Habit).where(Habit.code == code))


def get_habit(session: Session, code: str) -> Habit:
    habit = find_habit(session, code)
    if habit is None:
        raise RuntimeError(f"Habit not found: {code}")
    return habit


def get_or_create_habit_log(
    session: Session,
    habit: Habit,
    day: date,
    default_state: str = "PENDING",
):
    log = session.scalar(
        select(HabitLog).where(
            HabitLog.habit_id == habit.id,
            HabitLog.local_date == day,
        )
    )
    if log is None:
        log = HabitLog(
            habit_id=habit.id,
            local_date=day,
            state=default_state,
            finalized_by_close=False,
        )
        session.add(log)
        session.flush()
    return log


def sync_focus_habit(session: Session, day: date):
    habit = find_habit(session, FOCUS_HABIT_CODE)
    if habit is None or habit.status != "ACTIVE":
        return 0, 0, "DISABLED", FOCUS_HABIT_LABEL

    target = habit.minimum_minutes or 0
    minutes = 0

    if habit.skill_id is not None:
        skill = session.get(Skill, habit.skill_id)
        if skill is not None:
            start_utc, end_utc = utc_day_window(day)
            activities = session.scalars(
                select(Activity).where(
                    Activity.primary_skill_id == skill.id,
                    Activity.deleted_at.is_(None),
                    Activity.occurred_at >= start_utc,
                    Activity.occurred_at < end_utc,
                )
            ).all()
            minutes = sum(activity.duration_minutes or 0 for activity in activities)

    log = get_or_create_habit_log(session, habit, day)
    if target > 0 and minutes >= target:
        log.state = "DONE"
        log.finalized_by_close = False
    elif log.state != "PAUSED" and not log.finalized_by_close:
        log.state = "PENDING"
    log.value_int = minutes

    return minutes, target, log.state, habit.name


# Backward-compatible function name used by older code and migrations.
def sync_russian_habit(session: Session, day: date):
    minutes, target, state, _ = sync_focus_habit(session, day)
    return minutes, target, state


def get_or_create_nutrition(session: Session, day: date) -> NutritionDaily | None:
    if not NUTRITION_ENABLED:
        return None
    nutrition = session.scalar(
        select(NutritionDaily).where(NutritionDaily.local_date == day)
    )
    if nutrition is None:
        nutrition = NutritionDaily(
            local_date=day,
            base_target_kcal=NUTRITION_TARGET_KCAL,
            adjusted_target_kcal=NUTRITION_TARGET_KCAL,
            target_reached=None,
        )
        session.add(nutrition)
        session.flush()
    return nutrition


def set_nutrition_status(session: Session, reached: bool, day: date | None = None):
    if not NUTRITION_ENABLED:
        raise ValueError("Nutrition tracking is disabled for this Life RPG.")
    if day is None:
        day = local_today()
    nutrition = get_or_create_nutrition(session, day)
    assert nutrition is not None
    nutrition.target_reached = reached

    habit = find_habit(session, "nutrition_target") or find_habit(session, "nutrition_surplus")
    if habit is None:
        raise RuntimeError("Nutrition habit not configured")
    log = get_or_create_habit_log(session, habit, day)
    log.state = "DONE" if reached else "MISSED"
    log.finalized_by_close = False
    return nutrition, log


def log_weight(session: Session, weight_kg: float):
    if not WEIGHT_TRACKING_ENABLED:
        raise ValueError("Weight tracking is disabled for this Life RPG.")
    if not 30 <= weight_kg <= 300:
        raise ValueError("Weight must be between 30 and 300 kg.")
    day = local_today()
    entry = WeightLog(
        measured_at=datetime.now(timezone.utc),
        local_date=day,
        weight_g=round(weight_kg * 1000),
        valid=True,
        source="TELEGRAM",
    )
    session.add(entry)
    session.flush()
    return entry


def get_today_snapshot(session: Session) -> TodaySnapshot:
    day = local_today()
    focus_minutes, focus_target, focus_state, focus_name = sync_focus_habit(session, day)

    nutrition_state = "DISABLED"
    nutrition_target = 0
    nutrition = get_or_create_nutrition(session, day)
    if nutrition is not None:
        nutrition_target = nutrition.adjusted_target_kcal or nutrition.base_target_kcal
        habit = find_habit(session, "nutrition_target") or find_habit(session, "nutrition_surplus")
        if habit is not None:
            log = get_or_create_habit_log(session, habit, day)
            if nutrition.target_reached is True:
                log.state = "DONE"
                log.finalized_by_close = False
            elif nutrition.target_reached is False:
                log.state = "MISSED"
            elif log.state != "PAUSED" and not log.finalized_by_close:
                log.state = "PENDING"
            nutrition_state = log.state
        else:
            nutrition_state = "PENDING" if nutrition.target_reached is None else ("DONE" if nutrition.target_reached else "MISSED")

    latest_weight = None
    if WEIGHT_TRACKING_ENABLED:
        latest_weight = session.scalar(
            select(WeightLog)
            .where(WeightLog.valid.is_(True))
            .order_by(WeightLog.measured_at.desc())
            .limit(1)
        )

    if latest_weight is None:
        latest_weight_kg = None
        latest_weight_date = None
        weight_due = WEIGHT_TRACKING_ENABLED
    else:
        latest_weight_kg = latest_weight.weight_g / 1000
        latest_weight_date = latest_weight.local_date
        weight_due = (day - latest_weight.local_date).days >= 3

    return TodaySnapshot(
        local_date=day,
        focus_code=FOCUS_HABIT_CODE or None,
        focus_name=focus_name,
        focus_minutes=focus_minutes,
        focus_target=focus_target,
        focus_state=focus_state,
        nutrition_state=nutrition_state,
        nutrition_target_kcal=nutrition_target,
        latest_weight_kg=latest_weight_kg,
        latest_weight_date=latest_weight_date,
        weight_due=weight_due,
    )
