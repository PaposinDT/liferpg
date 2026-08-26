from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.character_service import require_character
from app.models import (
    Activity,
    ActivityTemplate,
    AuditLog,
    Character,
    Checkpoint,
    Skill,
    SkillLevelThreshold,
    SkillProgressionVersion,
    XPTransaction,
)


@dataclass
class ActivityResult:
    skill: str
    template: str
    base_xp: int

    applied_xp: int
    banked_xp: int

    old_level: int
    new_level: int

    checkpoint_locked: bool
    checkpoint_level: int | None
    checkpoint_name: str | None

    activity_id: int
    correlation_id: str


def get_active_progression(session: Session, skill_id: int):
    return session.scalar(
        select(SkillProgressionVersion)
        .where(
            SkillProgressionVersion.skill_id == skill_id,
            SkillProgressionVersion.active.is_(True),
        )
        .order_by(SkillProgressionVersion.version.desc())
        .limit(1)
    )


def get_thresholds(session: Session, progression_id: int):
    rows = session.scalars(
        select(SkillLevelThreshold)
        .where(
            SkillLevelThreshold.progression_version_id
            == progression_id
        )
        .order_by(SkillLevelThreshold.level)
    ).all()

    return {
        row.level: row.cumulative_xp_required
        for row in rows
    }


def calculate_level(total_xp: int, thresholds: dict[int, int]) -> int:
    level = 1

    for candidate in range(1, 151):
        if total_xp >= thresholds[candidate]:
            level = candidate
        else:
            break

    return level


def get_next_locked_checkpoint(
    session: Session,
    skill: Skill,
):
    return session.scalar(
        select(Checkpoint)
        .where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.status != "CLEARED",
            Checkpoint.level > skill.current_level,
        )
        .order_by(Checkpoint.level)
        .limit(1)
    )


def log_activity(
    session: Session,
    template_code: str,
    duration_minutes: int | None = None,
    notes: str | None = None,
    raw_user_input: str | None = None,
    source: str = "TEST",
) -> ActivityResult:

    template = session.scalar(
        select(ActivityTemplate).where(
            ActivityTemplate.code == template_code,
            ActivityTemplate.enabled.is_(True),
        )
    )

    if template is None:
        raise ValueError(f"Unknown activity template: {template_code}")

    skill = session.get(Skill, template.skill_id)

    if skill is None:
        raise RuntimeError("Template references missing skill")

    if skill.status != "ACTIVE":
        raise ValueError(
            f"Skill {skill.name} is not ACTIVE "
            f"(status={skill.status})"
        )

    progression = get_active_progression(session, skill.id)

    if progression is None:
        raise RuntimeError(
            f"No active progression for {skill.name}"
        )

    thresholds = get_thresholds(session, progression.id)

    old_level = skill.current_level
    incoming_xp = template.base_xp

    correlation_id = str(uuid4())

    activity = Activity(
        primary_skill_id=skill.id,
        template_code=template.code,
        occurred_at=datetime.now(timezone.utc),
        duration_minutes=(
            duration_minutes
            if duration_minutes is not None
            else template.default_duration_minutes
        ),
        notes=notes,
        raw_user_input=raw_user_input,
        source=source,
    )

    session.add(activity)
    session.flush()

    next_checkpoint = get_next_locked_checkpoint(
        session,
        skill,
    )

    applied_xp = incoming_xp
    newly_banked = 0

    # Hard gate:
    # visible XP stops exactly one XP before the checkpoint threshold.
    if next_checkpoint is not None:
        gate_threshold = thresholds[next_checkpoint.level]
        maximum_visible_xp = gate_threshold - 1

        available_before_gate = max(
            0,
            maximum_visible_xp - skill.total_xp,
        )

        applied_xp = min(
            incoming_xp,
            available_before_gate,
        )

        newly_banked = incoming_xp - applied_xp

    if applied_xp > 0:
        session.add(
            XPTransaction(
                target_type="SKILL",
                skill_id=skill.id,
                amount=applied_xp,
                transaction_type="ACTIVITY",
                source_type="ACTIVITY",
                source_id=activity.id,
                base_amount=applied_xp,
                streak_bonus=0,
                spillover=0,
                banked=False,
                correlation_id=correlation_id,
                reversed=False,
            )
        )

        skill.total_xp += applied_xp

    if newly_banked > 0:
        session.add(
            XPTransaction(
                target_type="SKILL",
                skill_id=skill.id,
                amount=newly_banked,
                transaction_type="ACTIVITY",
                source_type="ACTIVITY",
                source_id=activity.id,
                base_amount=newly_banked,
                streak_bonus=0,
                spillover=0,
                banked=True,
                correlation_id=correlation_id,
                reversed=False,
            )
        )

        skill.banked_xp += newly_banked

    skill.current_level = calculate_level(
        skill.total_xp,
        thresholds,
    )

    gained_skill_levels = max(
        0,
        skill.current_level - old_level,
    )

    if gained_skill_levels > 0:
        grant_character_xp(
            session=session,
            amount=12 * gained_skill_levels,
            transaction_type="SKILL_LEVEL_CXP",
            source_type="ACTIVITY",
            source_id=activity.id,
            correlation_id=correlation_id,
            skill_id=skill.id,
        )

    checkpoint_locked = False

    if next_checkpoint is not None:
        gate_threshold = thresholds[next_checkpoint.level]

        if (
            skill.total_xp >= gate_threshold - 1
            and skill.banked_xp > 0
        ):
            checkpoint_locked = True

            if next_checkpoint.status == "LOCKED":
                next_checkpoint.status = "REACHED"
                next_checkpoint.reached_at = datetime.now(timezone.utc)

    session.flush()

    return ActivityResult(
        skill=skill.name,
        template=template.name,
        base_xp=incoming_xp,
        applied_xp=applied_xp,
        banked_xp=newly_banked,
        old_level=old_level,
        new_level=skill.current_level,
        checkpoint_locked=checkpoint_locked,
        checkpoint_level=(
            next_checkpoint.level
            if checkpoint_locked
            else None
        ),
        checkpoint_name=(
            next_checkpoint.name
            if checkpoint_locked
            else None
        ),
        activity_id=activity.id,
        correlation_id=correlation_id,
    )


@dataclass
class CheckpointClearResult:
    skill: str
    checkpoint_level: int
    checkpoint_name: str

    old_level: int
    new_level: int

    released_xp: int
    remaining_banked_xp: int

    next_checkpoint_level: int | None
    next_checkpoint_name: str | None
    next_checkpoint_reached: bool

    correlation_id: str


def clear_checkpoint(
    session: Session,
    skill_code: str,
    checkpoint_level: int,
    user_note: str | None = None,
) -> CheckpointClearResult:

    skill = session.scalar(
        select(Skill).where(Skill.code == skill_code)
    )

    if skill is None:
        raise ValueError(f"Unknown skill: {skill_code}")

    checkpoint = session.scalar(
        select(Checkpoint).where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.level == checkpoint_level,
        )
    )

    if checkpoint is None:
        raise ValueError(
            f"No checkpoint at LVL {checkpoint_level} "
            f"for {skill.name}"
        )

    if checkpoint.status == "CLEARED":
        raise ValueError(
            f"Checkpoint LVL {checkpoint_level} is already CLEARED"
        )

    if checkpoint.status != "REACHED":
        raise ValueError(
            f"Checkpoint LVL {checkpoint_level} cannot be cleared "
            f"because status={checkpoint.status}"
        )

    progression = get_active_progression(session, skill.id)

    if progression is None:
        raise RuntimeError(
            f"No active progression for {skill.name}"
        )

    thresholds = get_thresholds(
        session,
        progression.id,
    )

    old_level = skill.current_level
    correlation_id = str(uuid4())

    # User is the only authority allowed to clear a checkpoint.
    checkpoint.status = "CLEARED"
    checkpoint.cleared_at = datetime.now(timezone.utc)

    if user_note:
        checkpoint.user_note = user_note

    # Find the next uncleared checkpoint AFTER the one just cleared.
    next_checkpoint = session.scalar(
        select(Checkpoint)
        .where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.status != "CLEARED",
            Checkpoint.level > checkpoint.level,
        )
        .order_by(Checkpoint.level)
        .limit(1)
    )

    available_banked = skill.banked_xp

    if next_checkpoint is not None:
        next_gate_threshold = thresholds[next_checkpoint.level]

        # Again stop exactly 1 XP before the next uncleared gate.
        maximum_visible_xp = next_gate_threshold - 1

        release_capacity = max(
            0,
            maximum_visible_xp - skill.total_xp,
        )

        released_xp = min(
            available_banked,
            release_capacity,
        )

    else:
        # No more gates: everything can become visible.
        released_xp = available_banked

    if released_xp > 0:
        # Debit from the banked bucket.
        session.add(
            XPTransaction(
                target_type="SKILL",
                skill_id=skill.id,
                amount=-released_xp,
                transaction_type="BANK_RELEASE_DEBIT",
                source_type="CHECKPOINT",
                source_id=checkpoint.id,
                base_amount=-released_xp,
                streak_bonus=0,
                spillover=0,
                banked=True,
                correlation_id=correlation_id,
                reversed=False,
            )
        )

        # Credit into visible progression.
        session.add(
            XPTransaction(
                target_type="SKILL",
                skill_id=skill.id,
                amount=released_xp,
                transaction_type="BANK_RELEASE_CREDIT",
                source_type="CHECKPOINT",
                source_id=checkpoint.id,
                base_amount=released_xp,
                streak_bonus=0,
                spillover=0,
                banked=False,
                correlation_id=correlation_id,
                reversed=False,
            )
        )

        skill.banked_xp -= released_xp
        skill.total_xp += released_xp

    skill.current_level = calculate_level(
        skill.total_xp,
        thresholds,
    )

    gained_skill_levels = max(
        0,
        skill.current_level - old_level,
    )

    if gained_skill_levels > 0:
        grant_character_xp(
            session=session,
            amount=12 * gained_skill_levels,
            transaction_type="SKILL_LEVEL_CXP",
            source_type="CHECKPOINT",
            source_id=checkpoint.id,
            correlation_id=correlation_id,
            skill_id=skill.id,
        )

    checkpoint_bonus = checkpoint_cxp_bonus(
        checkpoint.level
    )

    if checkpoint_bonus > 0:
        grant_character_xp(
            session=session,
            amount=checkpoint_bonus,
            transaction_type="CHECKPOINT_CXP",
            source_type="CHECKPOINT",
            source_id=checkpoint.id,
            correlation_id=correlation_id,
            skill_id=skill.id,
        )

    next_checkpoint_reached = False

    # If a large bank remains and we have filled progress right up to
    # the next gate, that next checkpoint becomes REACHED.
    if next_checkpoint is not None:
        next_gate_threshold = thresholds[next_checkpoint.level]

        if (
            skill.total_xp >= next_gate_threshold - 1
            and skill.banked_xp > 0
        ):
            if next_checkpoint.status == "LOCKED":
                next_checkpoint.status = "REACHED"
                next_checkpoint.reached_at = datetime.now(timezone.utc)

            next_checkpoint_reached = True

    session.add(
        AuditLog(
            actor="USER",
            action="CHECKPOINT_CLEARED",
            entity_type="CHECKPOINT",
            entity_id=checkpoint.id,
            reason=user_note,
            correlation_id=correlation_id,
        )
    )

    session.flush()

    return CheckpointClearResult(
        skill=skill.name,
        checkpoint_level=checkpoint.level,
        checkpoint_name=checkpoint.name,
        old_level=old_level,
        new_level=skill.current_level,
        released_xp=released_xp,
        remaining_banked_xp=skill.banked_xp,
        next_checkpoint_level=(
            next_checkpoint.level
            if next_checkpoint is not None
            else None
        ),
        next_checkpoint_name=(
            next_checkpoint.name
            if next_checkpoint is not None
            else None
        ),
        next_checkpoint_reached=next_checkpoint_reached,
        correlation_id=correlation_id,
    )



# === CHARACTER XP ENGINE ===

def calculate_character_level(character_xp: int) -> int:
    level = 1
    cumulative = 0

    while level < 100:
        cost_to_next = 100 + 15 * (level - 1)

        if character_xp < cumulative + cost_to_next:
            break

        cumulative += cost_to_next
        level += 1

    return level


def grant_character_xp(
    session: Session,
    amount: int,
    transaction_type: str,
    source_type: str,
    source_id: int | None,
    correlation_id: str,
    skill_id: int | None = None,
):
    if amount <= 0:
        return

    character = require_character(session)

    session.add(
        XPTransaction(
            target_type="CHARACTER",
            skill_id=skill_id,
            amount=amount,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            base_amount=amount,
            streak_bonus=0,
            spillover=0,
            banked=False,
            correlation_id=correlation_id,
            reversed=False,
        )
    )

    character.character_xp += amount

    calculated_level = calculate_character_level(
        character.character_xp
    )

    # Character Level is historical and never decreases.
    character.character_level = max(
        character.character_level,
        calculated_level,
    )


def checkpoint_cxp_bonus(level: int) -> int:
    if level == 150:
        return 750
    if 130 <= level <= 149:
        return 350
    if 110 <= level <= 129:
        return 225
    if 90 <= level <= 109:
        return 150
    if 70 <= level <= 89:
        return 100
    if 46 <= level <= 69:
        return 75
    if 20 <= level <= 45:
        return 50

    return 0



# === ACTIVITY UNDO ENGINE ===

@dataclass
class UndoActivityResult:
    activity_id: int
    skill: str

    removed_visible_xp: int
    removed_banked_xp: int
    removed_character_xp: int

    old_level: int
    new_level: int

    correlation_id: str


def undo_activity(
    session: Session,
    activity_id: int,
) -> UndoActivityResult:

    activity = session.get(Activity, activity_id)

    if activity is None:
        raise ValueError("Activity not found")

    if activity.deleted_at is not None:
        raise ValueError("Activity already undone")

    latest_activity = session.scalar(
        select(Activity)
        .where(Activity.deleted_at.is_(None))
        .order_by(Activity.id.desc())
        .limit(1)
    )

    if (
        latest_activity is None
        or latest_activity.id != activity.id
    ):
        raise ValueError(
            "Only the latest activity can be undone safely"
        )

    if activity.primary_skill_id is None:
        raise ValueError(
            "Activity has no primary skill"
        )

    skill = session.get(
        Skill,
        activity.primary_skill_id,
    )

    if skill is None:
        raise RuntimeError(
            "Activity references missing skill"
        )

    # If a checkpoint on this skill has been cleared after this
    # activity, the banked XP may already have been released.
    # Do not perform an unsafe partial rewind.
    later_checkpoint_transaction = session.scalar(
        select(XPTransaction)
        .where(
            XPTransaction.skill_id == skill.id,
            XPTransaction.source_type == "CHECKPOINT",
            XPTransaction.created_at > activity.created_at,
            XPTransaction.reversed.is_(False),
        )
        .limit(1)
    )

    if later_checkpoint_transaction is not None:
        raise ValueError(
            "Cannot undo this activity because a checkpoint "
            "was cleared afterwards"
        )

    transactions = session.scalars(
        select(XPTransaction).where(
            XPTransaction.source_type == "ACTIVITY",
            XPTransaction.source_id == activity.id,
            XPTransaction.reversed.is_(False),
        )
    ).all()

    visible_xp = sum(
        tx.amount
        for tx in transactions
        if tx.target_type == "SKILL"
        and not tx.banked
    )

    banked_xp = sum(
        tx.amount
        for tx in transactions
        if tx.target_type == "SKILL"
        and tx.banked
    )

    character_xp = sum(
        tx.amount
        for tx in transactions
        if tx.target_type == "CHARACTER"
    )

    old_level = skill.current_level

    for tx in transactions:
        tx.reversed = True

    skill.total_xp = max(
        0,
        skill.total_xp - visible_xp,
    )

    skill.banked_xp = max(
        0,
        skill.banked_xp - banked_xp,
    )

    progression = get_active_progression(
        session,
        skill.id,
    )

    if progression is None:
        raise RuntimeError(
            f"No active progression for {skill.name}"
        )

    thresholds = get_thresholds(
        session,
        progression.id,
    )

    skill.current_level = calculate_level(
        skill.total_xp,
        thresholds,
    )

    # A REACHED checkpoint may have been reached only because
    # of the activity that is now being undone.
    reached_checkpoints = session.scalars(
        select(Checkpoint).where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.status == "REACHED",
        )
    ).all()

    for checkpoint in reached_checkpoints:
        gate_xp = thresholds[checkpoint.level]

        if (
            skill.total_xp < gate_xp - 1
            or skill.banked_xp <= 0
        ):
            checkpoint.status = "LOCKED"
            checkpoint.reached_at = None

    character = require_character(session)

    character.character_xp = max(
        0,
        character.character_xp - character_xp,
    )

    # Character Level intentionally never decreases.

    activity.deleted_at = datetime.now(timezone.utc)

    correlation_id = str(uuid4())

    session.add(
        AuditLog(
            actor="USER",
            action="ACTIVITY_UNDONE",
            entity_type="ACTIVITY",
            entity_id=activity.id,
            reason="User undo",
            correlation_id=correlation_id,
        )
    )

    session.flush()

    return UndoActivityResult(
        activity_id=activity.id,
        skill=skill.name,
        removed_visible_xp=visible_xp,
        removed_banked_xp=banked_xp,
        removed_character_xp=character_xp,
        old_level=old_level,
        new_level=skill.current_level,
        correlation_id=correlation_id,
    )
