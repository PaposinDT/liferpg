from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.founding_config import load_founding_config
from app.models import Quest, QuestSchedule


def main() -> None:
    config = load_founding_config()
    schedules = config.get("weekly_schedules", [])

    with SessionLocal() as session:
        for data in schedules:
            quest = session.scalar(select(Quest).where(Quest.code == str(data["quest_code"])))
            if quest is None:
                raise RuntimeError(f"Weekly schedule references missing quest: {data['quest_code']}")

            row = session.scalar(
                select(QuestSchedule).where(
                    QuestSchedule.quest_id == quest.id,
                    QuestSchedule.cadence == "WEEKLY",
                )
            )
            if row is None:
                row = QuestSchedule(quest_id=quest.id, cadence="WEEKLY")
                session.add(row)

            row.minimum_required = max(0, int(data.get("minimum", 1)))
            row.stretch_target = max(row.minimum_required, int(data.get("stretch", row.minimum_required)))
            row.active = bool(data.get("active", True))

        session.commit()

    print(f"Weekly operations applied: {len(schedules)}")


if __name__ == "__main__":
    main()
