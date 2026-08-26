import pytest
from sqlalchemy import select

from app.character_service import require_character
from app.db import SessionLocal
from app.game_engine import clear_checkpoint, log_activity
from app.models import Character, Checkpoint, Skill


@pytest.fixture
def session():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()


def get_skill(session, code):
    return session.scalar(
        select(Skill).where(Skill.code == code)
    )


def get_checkpoint(session, skill, level):
    return session.scalar(
        select(Checkpoint).where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.level == level,
        )
    )


def get_character(session):
    return require_character(session)


def test_russian_activity_adds_xp_without_level_up(session):
    russian = get_skill(session, "russian")

    assert russian.current_level == 6
    assert russian.total_xp == 210
    assert russian.banked_xp == 0

    result = log_activity(
        session,
        template_code="russian_30",
        source="PYTEST",
    )

    assert result.applied_xp == 10
    assert result.banked_xp == 0

    assert russian.current_level == 6
    assert russian.total_xp == 220
    assert russian.banked_xp == 0


def test_shooting_hard_gate_banks_excess_xp(session):
    shooting = get_skill(session, "shooting")
    gate60 = get_checkpoint(session, shooting, 60)

    assert shooting.current_level == 59
    assert shooting.total_xp == 1760
    assert gate60.status == "LOCKED"

    result = log_activity(
        session,
        template_code="shooting_qualification",
        source="PYTEST",
    )

    assert result.base_xp == 40
    assert result.applied_xp == 39
    assert result.banked_xp == 1

    assert shooting.current_level == 59
    assert shooting.total_xp == 1799
    assert shooting.banked_xp == 1

    assert gate60.status == "REACHED"


def test_checkpoint_clear_releases_bank_and_grants_cxp(session):
    shooting = get_skill(session, "shooting")
    character = get_character(session)
    gate60 = get_checkpoint(session, shooting, 60)

    initial_cxp = character.character_xp

    log_activity(
        session,
        template_code="shooting_qualification",
        source="PYTEST",
    )

    result = clear_checkpoint(
        session,
        skill_code="shooting",
        checkpoint_level=60,
        user_note="PYTEST",
    )

    assert result.released_xp == 1
    assert result.remaining_banked_xp == 0

    assert shooting.current_level == 60
    assert shooting.total_xp == 1800
    assert shooting.banked_xp == 0

    assert gate60.status == "CLEARED"

    # +12 for Skill LVL59 -> 60
    # +75 for checkpoint LVL60
    assert character.character_xp == initial_cxp + 87


def test_large_bank_cannot_skip_next_checkpoint(session):
    shooting = get_skill(session, "shooting")

    gate60 = get_checkpoint(session, shooting, 60)
    gate80 = get_checkpoint(session, shooting, 80)

    # 51 x 40 XP = 2040 incoming XP.
    #
    # First activity:
    # +39 visible, +1 banked.
    #
    # Remaining 50:
    # +2000 banked.
    #
    # Total banked = 2001.
    for _ in range(51):
        log_activity(
            session,
            template_code="shooting_qualification",
            source="PYTEST",
        )

    assert shooting.current_level == 59
    assert shooting.total_xp == 1799
    assert shooting.banked_xp == 2001
    assert gate60.status == "REACHED"
    assert gate80.status == "LOCKED"

    result = clear_checkpoint(
        session,
        skill_code="shooting",
        checkpoint_level=60,
        user_note="PYTEST MEGA BANK",
    )

    # Gate 80 requires 3000 XP.
    # Engine must stop at 2999.
    assert shooting.total_xp == 2999
    assert shooting.current_level == 79

    # 2001 banked - 1200 released
    assert shooting.banked_xp == 801

    assert gate60.status == "CLEARED"

    # Most important assertion:
    # one confirmation cannot clear two gates.
    assert gate80.status == "REACHED"
    assert gate80.status != "CLEARED"

    assert result.next_checkpoint_level == 80
    assert result.next_checkpoint_reached is True


def test_locked_checkpoint_cannot_be_cleared(session):
    shooting = get_skill(session, "shooting")
    gate80 = get_checkpoint(session, shooting, 80)

    assert gate80.status == "LOCKED"

    with pytest.raises(
        ValueError,
        match="cannot be cleared",
    ):
        clear_checkpoint(
            session,
            skill_code="shooting",
            checkpoint_level=80,
        )
