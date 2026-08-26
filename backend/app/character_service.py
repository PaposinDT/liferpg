from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Character
from app.settings import CHARACTER_NAME


def get_character(session: Session) -> Character | None:
    """Return the configured single-user character, falling back to the first row."""
    character = session.scalar(
        select(Character).where(Character.name == CHARACTER_NAME).limit(1)
    )
    if character is not None:
        return character
    return session.scalar(select(Character).order_by(Character.id).limit(1))


def require_character(session: Session) -> Character:
    character = get_character(session)
    if character is None:
        raise RuntimeError("Life RPG character not found. Run the bootstrap step first.")
    return character
