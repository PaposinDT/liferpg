from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.founding_config import load_founding_config
from app.models import Habit, Quest, Skill


def main() -> None:
    config = load_founding_config()
    quest_defs = config.get("quests", [])
    habit_defs = config.get("habits", [])

    with SessionLocal() as session:
        skills = {s.code: s for s in session.scalars(select(Skill)).all()}

        for data in quest_defs:
            code = str(data["code"])
            quest = session.scalar(select(Quest).where(Quest.code == code))
            if quest is None:
                quest = Quest(code=code)
                session.add(quest)

            quest.title = str(data.get("title") or code.replace("_", " ").title())
            quest.quest_type = str(data.get("type", "MAIN")).upper()
            quest.status = str(data.get("status", "ACTIVE")).upper()
            quest.description = data.get("description")
            quest.target_value = data.get("target_value")
            quest.target_unit = data.get("target_unit")

            skill_code = data.get("skill")
            if skill_code:
                skill = skills.get(str(skill_code))
                if skill is None:
                    raise RuntimeError(f"Quest {code} references unknown skill {skill_code}")
                quest.skill_id = skill.id
            else:
                quest.skill_id = None

        for data in habit_defs:
            code = str(data["code"])
            habit = session.scalar(select(Habit).where(Habit.code == code))
            if habit is None:
                habit = Habit(code=code)
                session.add(habit)

            habit.name = str(data.get("name") or code.replace("_", " ").title())
            habit.status = str(data.get("status", "ACTIVE")).upper()
            habit.minimum_minutes = data.get("minimum_minutes")
            habit.true_streak = bool(data.get("true_streak", True))
            habit.affects_disc = bool(data.get("affects_disc", True))
            habit.grants_skill_xp = bool(data.get("grants_skill_xp", False))
            habit.description = data.get("description")

            skill_code = data.get("skill")
            if skill_code:
                skill = skills.get(str(skill_code))
                if skill is None:
                    raise RuntimeError(f"Habit {code} references unknown skill {skill_code}")
                habit.skill_id = skill.id
            else:
                habit.skill_id = None

        session.commit()

    print(f"Main quests/habits applied: {len(quest_defs)} quests, {len(habit_defs)} habits")


if __name__ == "__main__":
    main()
