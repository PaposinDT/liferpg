from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Activity, Character


def ensure_safe(force: bool) -> None:
    with SessionLocal() as session:
        characters = session.scalar(select(func.count(Character.id))) or 0
        activities = session.scalar(
            select(func.count(Activity.id)).where(Activity.deleted_at.is_(None))
        ) or 0

    if characters and activities and not force:
        raise SystemExit(
            "Refusing to reseed a live Life RPG with activity history. "
            "Use --force only if you intentionally want to recalibrate founding data."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Life RPG founding dataset")
    parser.add_argument("--force", action="store_true", help="allow founding recalibration")
    args = parser.parse_args()

    ensure_safe(args.force)

    from app.seed_foundation import main as seed_foundation
    from app.seed_progression import main as seed_progression
    from app.seed_activity_templates import main as seed_templates
    from app.seed_quests_habits import main as seed_quests_habits
    from app.seed_weekly_ops import main as seed_weekly_ops
    from app.seed_scheduler import main as seed_scheduler
    from app.seed_achievements import main as seed_achievements

    seed_foundation()
    seed_progression()
    seed_templates()
    seed_quests_habits()
    seed_weekly_ops()
    seed_scheduler()
    seed_achievements()

    print("Life RPG founding bootstrap complete.")


if __name__ == "__main__":
    main()
