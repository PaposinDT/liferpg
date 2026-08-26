from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    character_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    character_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    current_title: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    skills: Mapped[list["Skill"]] = relationship(back_populates="category")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)

    current_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    banked_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    level_cap: Mapped[int] = mapped_column(Integer, default=150, nullable=False)

    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    current_state: Mapped[str] = mapped_column(
        String(30),
        default="ACTIVE",
        nullable=False,
    )

    end_goal: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    category: Mapped["Category"] = relationship(back_populates="skills")
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (
        UniqueConstraint("skill_id", "level", name="uq_checkpoint_skill_level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id"),
        nullable=False,
    )

    level: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    requirements: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20),
        default="LOCKED",
        nullable=False,
    )

    reached_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user_note: Mapped[Optional[str]] = mapped_column(Text)

    skill: Mapped["Skill"] = relationship(back_populates="checkpoints")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    primary_skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id")
    )

    template_code: Mapped[Optional[str]] = mapped_column(String(100))

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    raw_user_input: Mapped[Optional[str]] = mapped_column(Text)

    source: Mapped[str] = mapped_column(
        String(30),
        default="TELEGRAM",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    target_type: Mapped[str] = mapped_column(String(20), nullable=False)

    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id")
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)

    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    base_amount: Mapped[Optional[int]] = mapped_column(Integer)
    streak_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spillover: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    banked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)

    reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    reason: Mapped[Optional[str]] = mapped_column(Text)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SkillProgressionVersion(Base):
    __tablename__ = "skill_progression_versions"
    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "version",
            name="uq_skill_progression_version",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id"),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SkillLevelThreshold(Base):
    __tablename__ = "skill_level_thresholds"
    __table_args__ = (
        UniqueConstraint(
            "progression_version_id",
            "level",
            name="uq_progression_level",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    progression_version_id: Mapped[int] = mapped_column(
        ForeignKey("skill_progression_versions.id"),
        nullable=False,
    )

    level: Mapped[int] = mapped_column(Integer, nullable=False)

    cumulative_xp_required: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )


class ActivityTemplate(Base):
    __tablename__ = "activity_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    base_xp: Mapped[int] = mapped_column(Integer, nullable=False)

    default_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    quest_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
    )

    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id")
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    target_value: Mapped[Optional[int]] = mapped_column(Integer)
    target_unit: Mapped[Optional[str]] = mapped_column(String(30))

    start_date: Mapped[Optional[date]] = mapped_column(Date)
    target_date: Mapped[Optional[date]] = mapped_column(Date)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )


class QuestSchedule(Base):
    __tablename__ = "quest_schedules"
    __table_args__ = (
        UniqueConstraint(
            "quest_id",
            "cadence",
            name="uq_quest_schedule_cadence",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    quest_id: Mapped[int] = mapped_column(
        ForeignKey("quests.id"),
        nullable=False,
    )

    cadence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    minimum_required: Mapped[Optional[int]] = mapped_column(Integer)
    stretch_target: Mapped[Optional[int]] = mapped_column(Integer)

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


class QuestInstance(Base):
    __tablename__ = "quest_instances"
    __table_args__ = (
        UniqueConstraint(
            "quest_id",
            "local_date",
            name="uq_quest_instance_day",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    quest_id: Mapped[int] = mapped_column(
        ForeignKey("quests.id"),
        nullable=False,
    )

    local_date: Mapped[date] = mapped_column(Date, nullable=False)

    state: Mapped[str] = mapped_column(
        String(30),
        default="PLANNED",
        nullable=False,
    )

    load: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    progress_current: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    progress_target: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    skipped_reason_primary: Mapped[Optional[str]] = mapped_column(
        String(50)
    )

    skipped_reason_secondary: Mapped[Optional[str]] = mapped_column(
        String(50)
    )

    notes: Mapped[Optional[str]] = mapped_column(Text)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id")
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
    )

    minimum_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    true_streak: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    affects_disc: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    grants_skill_xp: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class HabitLog(Base):
    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint(
            "habit_id",
            "local_date",
            name="uq_habit_log_day",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id"),
        nullable=False,
    )

    local_date: Mapped[date] = mapped_column(Date, nullable=False)

    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    value_int: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    finalized_by_close: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    local_date: Mapped[date] = mapped_column(Date, nullable=False)

    weight_g: Mapped[int] = mapped_column(Integer, nullable=False)

    valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        default="TELEGRAM",
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text)


class NutritionDaily(Base):
    __tablename__ = "nutrition_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    local_date: Mapped[date] = mapped_column(
        Date,
        unique=True,
        nullable=False,
    )

    base_target_kcal: Mapped[int] = mapped_column(
        Integer,
        default=2200,
        nullable=False,
    )

    adjusted_target_kcal: Mapped[Optional[int]] = mapped_column(Integer)

    target_reached: Mapped[Optional[bool]] = mapped_column(Boolean)

    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )



class StreakState(Base):
    __tablename__ = "streak_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id"),
        unique=True,
        nullable=False,
    )

    current_streak: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    best_streak: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    rate_7_bp: Mapped[Optional[int]] = mapped_column(Integer)
    rate_30_bp: Mapped[Optional[int]] = mapped_column(Integer)
    rate_90_bp: Mapped[Optional[int]] = mapped_column(Integer)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    local_date: Mapped[date] = mapped_column(
        Date,
        unique=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="OPEN",
        nullable=False,
    )

    russian_state: Mapped[Optional[str]] = mapped_column(String(20))
    nutrition_state: Mapped[Optional[str]] = mapped_column(String(20))

    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    closed_manually: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    disc_ranked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    disc_score: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    local_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    local_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        UniqueConstraint(
            "job_code",
            "run_key",
            name="uq_job_run_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    job_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    run_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    target_local_date: Mapped[Optional[date]] = mapped_column(Date)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    message: Mapped[Optional[str]] = mapped_column(Text)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )



class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    rarity: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    secret: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    criteria_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    criteria_skill_code: Mapped[Optional[str]] = mapped_column(
        String(100)
    )

    threshold_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    threshold_unit: Mapped[Optional[str]] = mapped_column(
        String(50)
    )

    cxp_reward: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AchievementUnlock(Base):
    __tablename__ = "achievement_unlocks"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id"),
        unique=True,
        nullable=False,
    )

    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        default="SYSTEM",
        nullable=False,
    )


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    event_key: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    local_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(Text)

    significance: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )


class Report(Base):
    __tablename__ = "reports"

    __table_args__ = (
        UniqueConstraint(
            "report_type",
            "period_start",
            "period_end",
            "version",
            name="uq_report_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    report_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="FROZEN",
        nullable=False,
    )

    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
