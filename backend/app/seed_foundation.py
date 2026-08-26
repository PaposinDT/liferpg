from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionLocal
from app.founding_config import load_founding_config
from app.models import Category, Character, Skill, WeightLog
from app.settings import TIMEZONE_NAME, character_rank


DEFAULT_CATEGORIES = [
    {"code": "COMBAT", "name": "Combat", "sort_order": 10},
    {"code": "PHYSICAL", "name": "Physical", "sort_order": 20},
    {"code": "KNOWLEDGE", "name": "Knowledge", "sort_order": 30},
    {"code": "PRACTICAL", "name": "Practical", "sort_order": 40},
    {"code": "FINANCE", "name": "Finance", "sort_order": 50},
    {"code": "CUSTOM", "name": "Custom", "sort_order": 90},
]


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


def main() -> None:
    config = load_founding_config()
    character_data = config["character"]
    skill_defs = config["skills"]
    category_defs = config.get("categories") or DEFAULT_CATEGORIES

    founding_cxp = character_data.get("character_xp")
    if founding_cxp is None:
        founding_cxp = sum(max(1, int(s.get("level", 1))) for s in skill_defs) * 12

    founding_level = character_data.get("level")
    if founding_level is None:
        founding_level = calculate_character_level(int(founding_cxp))

    founding_title = character_data.get("title") or character_rank(int(founding_level))

    with SessionLocal() as session:
        character = session.scalar(
            select(Character).where(Character.name == character_data["name"])
        )
        if character is None:
            character = Character(name=character_data["name"])
            session.add(character)

        character.character_level = int(founding_level)
        character.character_xp = int(founding_cxp)
        character.current_title = str(founding_title)

        category_map: dict[str, Category] = {}
        for item in category_defs:
            code = str(item["code"]).upper()
            category = session.scalar(select(Category).where(Category.code == code))
            if category is None:
                category = Category(code=code)
                session.add(category)
                session.flush()
            category.name = str(item.get("name") or code.title())
            category.sort_order = int(item.get("sort_order", 90))
            category_map[code] = category

        for data in skill_defs:
            code = str(data["code"])
            category_code = str(data.get("category", "CUSTOM")).upper()
            if category_code not in category_map:
                category = Category(
                    code=category_code,
                    name=category_code.title(),
                    sort_order=90,
                )
                session.add(category)
                session.flush()
                category_map[category_code] = category

            skill = session.scalar(select(Skill).where(Skill.code == code))
            if skill is None:
                skill = Skill(code=code)
                session.add(skill)

            level = max(1, min(150, int(data.get("level", 1))))
            skill.category_id = category_map[category_code].id
            skill.name = str(data.get("name") or code.replace("_", " ").title())
            skill.description = data.get("description")
            skill.current_level = level
            skill.total_xp = 0
            skill.banked_xp = 0
            skill.level_cap = 150
            skill.priority = str(data.get("priority", "BACKGROUND")).upper()
            skill.status = str(data.get("status", "ACTIVE")).upper()
            skill.current_state = str(data.get("state", "ACTIVE")).upper()
            skill.end_goal = data.get("goal")

        body = config.get("body", {})
        starting_weight = body.get("starting_weight_kg")
        if body.get("weight_tracking") and starting_weight is not None:
            existing_weight = session.scalar(
                select(WeightLog).order_by(WeightLog.id).limit(1)
            )
            if existing_weight is None:
                now_utc = datetime.now(timezone.utc)
                local_day = now_utc.astimezone(ZoneInfo(TIMEZONE_NAME)).date()
                session.add(
                    WeightLog(
                        measured_at=now_utc,
                        local_date=local_day,
                        weight_g=int(round(float(starting_weight) * 1000)),
                        valid=True,
                        source="FOUNDING",
                        notes="Founding assessment",
                    )
                )

        session.commit()

    print("Founding dataset applied successfully.")
    print(f"Character: {character_data['name']} · LVL {founding_level} · CXP {founding_cxp}")
    print(f"Skills: {len(skill_defs)}")


if __name__ == "__main__":
    main()
