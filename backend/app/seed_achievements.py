from __future__ import annotations

import re

from sqlalchemy import func, select

from app.achievement_service import add_timeline, refresh_achievements
from app.db import SessionLocal
from app.founding_config import load_founding_config
from app.models import Achievement


BASE = [
    ("char10", "First Deployment", "CHARACTER", "COMMON", "CHARACTER_LEVEL", None, 10),
    ("char20", "Operator Status", "CHARACTER", "UNCOMMON", "CHARACTER_LEVEL", None, 20),
    ("char35", "Field Operator", "CHARACTER", "RARE", "CHARACTER_LEVEL", None, 35),
    ("char50", "Veteran Operator", "CHARACTER", "EPIC", "CHARACTER_LEVEL", None, 50),
    ("char65", "Elite Operator", "CHARACTER", "EPIC", "CHARACTER_LEVEL", None, 65),
    ("char80", "Senior Operator", "CHARACTER", "LEGENDARY", "CHARACTER_LEVEL", None, 80),
    ("char90", "Master Operator", "CHARACTER", "LEGENDARY", "CHARACTER_LEVEL", None, 90),
    ("char100", "Ascendant", "CHARACTER", "LEGENDARY", "CHARACTER_LEVEL", None, 100),
    ("skill25", "Foundation Built", "PROGRESSION", "COMMON", "ANY_SKILL_LEVEL", None, 25),
    ("skill50", "Competent Operator", "PROGRESSION", "UNCOMMON", "ANY_SKILL_LEVEL", None, 50),
    ("skill75", "Advanced Discipline", "PROGRESSION", "RARE", "ANY_SKILL_LEVEL", None, 75),
    ("skill100", "Triple Digits", "PROGRESSION", "EPIC", "ANY_SKILL_LEVEL", None, 100),
    ("skill120", "Mastery Track", "PROGRESSION", "LEGENDARY", "ANY_SKILL_LEVEL", None, 120),
    ("skill150", "Perfected Discipline", "PROGRESSION", "LEGENDARY", "ANY_SKILL_LEVEL", None, 150),
    ("act1", "First Entry", "CONSISTENCY", "COMMON", "ACTIVITY_COUNT", None, 1),
    ("act10", "Operational Rhythm", "CONSISTENCY", "COMMON", "ACTIVITY_COUNT", None, 10),
    ("act50", "Field Routine", "CONSISTENCY", "UNCOMMON", "ACTIVITY_COUNT", None, 50),
    ("act100", "Century Log", "CONSISTENCY", "RARE", "ACTIVITY_COUNT", None, 100),
    ("act250", "Long Campaign", "CONSISTENCY", "EPIC", "ACTIVITY_COUNT", None, 250),
    ("cp1", "First Gate", "PROGRESSION", "COMMON", "CHECKPOINT_COUNT", None, 1),
    ("cp5", "Gate Runner", "PROGRESSION", "UNCOMMON", "CHECKPOINT_COUNT", None, 5),
    ("cp10", "Proven Progress", "PROGRESSION", "RARE", "CHECKPOINT_COUNT", None, 10),
    ("cp20", "Established Operator", "PROGRESSION", "EPIC", "CHECKPOINT_COUNT", None, 20),
]

SKILL_MILESTONES = [
    (30, "Foundation", "COMMON"),
    (60, "Competent", "UNCOMMON"),
    (90, "Advanced", "RARE"),
    (120, "Mastery Track", "EPIC"),
    (150, "Mastery", "LEGENDARY"),
]


def safe_code(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value[:48] or "skill"


def definitions():
    config = load_founding_config()
    data = list(BASE)

    for skill in config["skills"]:
        code = str(skill["code"])
        name = str(skill.get("name") or code.replace("_", " ").title())
        category = str(skill.get("category", "PROGRESSION")).upper()
        short = safe_code(code)
        for level, label, rarity in SKILL_MILESTONES:
            data.append(
                (
                    f"s_{short}_{level}",
                    f"{name}: {label}",
                    category,
                    rarity,
                    "SKILL_LEVEL",
                    code,
                    level,
                )
            )

    body = config.get("body", {})
    start_kg = body.get("starting_weight_kg")
    target_kg = body.get("target_weight_kg")
    if start_kg is not None and target_kg is not None and target_kg > start_kg:
        steps = [0.25, 0.5, 0.75, 1.0]
        rarities = ["COMMON", "UNCOMMON", "RARE", "LEGENDARY"]
        for fraction, rarity in zip(steps, rarities):
            kg = round(float(start_kg) + (float(target_kg) - float(start_kg)) * fraction, 1)
            data.append(
                (
                    f"weight_{int(kg * 10)}",
                    f"Bodyweight {kg:.1f} kg",
                    "BODY",
                    rarity,
                    "WEIGHT_G",
                    None,
                    int(round(kg * 1000)),
                )
            )

    return data


def main():
    data = definitions()
    with SessionLocal() as session:
        active_codes = set()
        for code, name, category, rarity, criteria, skill_code, threshold in data:
            active_codes.add(code)
            row = session.scalar(select(Achievement).where(Achievement.code == code))
            if row is None:
                row = Achievement(code=code)
                session.add(row)
            row.name = name
            row.description = name
            row.category = category
            row.rarity = rarity
            row.secret = False
            row.criteria_type = criteria
            row.criteria_skill_code = skill_code
            row.threshold_value = threshold
            row.cxp_reward = 0
            row.active = True

        # Do not delete historical definitions; merely deactivate definitions no longer configured.
        existing = session.scalars(select(Achievement)).all()
        for row in existing:
            if row.code not in active_codes:
                row.active = False

        session.flush()
        add_timeline(
            session,
            key="founding_snapshot",
            event_type="FOUNDING",
            title="Founding Snapshot",
            description="Initial Life RPG progression state established.",
            significance=5,
        )
        new = refresh_achievements(session, source_type="FOUNDING_RECALC")
        session.commit()

        total = session.scalar(select(func.count(Achievement.id)).where(Achievement.active.is_(True)))
        print("Definitions:", total)
        print("Founding unlocks:", len(new))


if __name__ == "__main__":
    main()
