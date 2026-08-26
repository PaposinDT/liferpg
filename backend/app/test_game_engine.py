from sqlalchemy import select

from app.character_service import require_character
from app.db import SessionLocal
from app.game_engine import clear_checkpoint, log_activity
from app.models import Character, Checkpoint, Skill


def get_skill(session):
    return session.scalar(
        select(Skill).where(Skill.code == "shooting")
    )


def get_character(session):
    return require_character(session)


def show(session):
    skill = get_skill(session)
    character = get_character(session)

    cp60 = session.scalar(
        select(Checkpoint).where(
            Checkpoint.skill_id == skill.id,
            Checkpoint.level == 60,
        )
    )

    print(
        f"Shooting: "
        f"LVL={skill.current_level}, "
        f"XP={skill.total_xp}, "
        f"BANKED={skill.banked_xp}, "
        f"GATE60={cp60.status}"
    )

    print(
        f"{character.name}: "
        f"LVL={character.character_level}, "
        f"CXP={character.character_xp}"
    )


def main():
    session = SessionLocal()

    try:
        print("=== INITIAL ===")
        show(session)

        print("\n=== ACTIVITY +40 ===")

        result = log_activity(
            session,
            template_code="shooting_qualification",
            raw_user_input="TEST qualification",
            source="ENGINE_TEST",
        )

        print(result)
        show(session)

        print("\n=== CLEAR CHECKPOINT 60 ===")

        result = clear_checkpoint(
            session,
            skill_code="shooting",
            checkpoint_level=60,
            user_note="ENGINE TEST ONLY",
        )

        print(result)
        show(session)

        print("\n=== ROLLBACK ===")

        session.rollback()
        show(session)

    finally:
        session.close()


if __name__ == "__main__":
    main()
