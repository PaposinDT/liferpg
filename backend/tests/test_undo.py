from sqlalchemy import select

from app.character_service import require_character
from app.db import SessionLocal
from app.game_engine import log_activity, undo_activity
from app.models import Activity, Character, Skill


def test_activity_undo():
    session = SessionLocal()

    try:
        russian = session.scalar(
            select(Skill).where(
                Skill.code == "russian"
            )
        )

        character = require_character(session)

        initial_xp = russian.total_xp
        initial_banked = russian.banked_xp
        initial_level = russian.current_level
        initial_cxp = character.character_xp

        added = log_activity(
            session=session,
            template_code="russian_15",
            source="PYTEST",
        )

        assert russian.total_xp == initial_xp + 5

        undone = undo_activity(
            session=session,
            activity_id=added.activity_id,
        )

        assert undone.removed_visible_xp == 5

        assert russian.total_xp == initial_xp
        assert russian.banked_xp == initial_banked
        assert russian.current_level == initial_level
        assert character.character_xp == initial_cxp

        activity = session.get(
            Activity,
            added.activity_id,
        )

        assert activity.deleted_at is not None

    finally:
        session.rollback()
        session.close()
