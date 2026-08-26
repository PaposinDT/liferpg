from __future__ import annotations

from sqlalchemy.orm import Session

from app.quest_service import get_weekly_operations, priority_operations
from app.settings import NUTRITION_ENABLED, WEIGHT_TRACKING_ENABLED
from app.today_service import get_today_snapshot


def build_gm_state(session: Session):
    today = get_today_snapshot(session)
    weekly = get_weekly_operations(session)
    priority = priority_operations(session=session, limit=3)

    return {
        "date": today.local_date.isoformat(),
        "weekly": [
            {
                "skill": op.skill_name,
                "skill_code": op.skill_code,
                "current": op.current,
                "minimum": op.minimum,
                "stretch": op.stretch,
                "minimum_met": op.minimum_met,
            }
            for op in weekly
        ],
        "priority": [
            {
                "skill": op.skill_name,
                "skill_code": op.skill_code,
                "current": op.current,
                "minimum": op.minimum,
            }
            for op in priority
        ],
        "focus": {
            "name": today.focus_name,
            "minutes": today.focus_minutes,
            "target": today.focus_target,
            "state": today.focus_state,
        },
        "nutrition": {
            "enabled": NUTRITION_ENABLED,
            "state": today.nutrition_state,
            "target_kcal": today.nutrition_target_kcal,
        },
        "weight": {
            "enabled": WEIGHT_TRACKING_ENABLED,
            "latest_kg": today.latest_weight_kg,
            "due": today.weight_due,
        },
    }


def deterministic_order(state):
    if state["priority"]:
        op = state["priority"][0]
        return {
            "order": op["skill"],
            "reason": f"Weekly minimum is {op['current']}/{op['minimum']}.",
        }

    focus = state["focus"]
    if focus["state"] not in {"DONE", "DISABLED"}:
        return {
            "order": focus["name"],
            "reason": f"Daily progress is {focus['minutes']}/{focus['target']} minutes.",
        }

    nutrition = state["nutrition"]
    if nutrition["enabled"] and nutrition["state"] != "DONE":
        return {
            "order": "Nutrition",
            "reason": "Daily nutrition objective is not complete.",
        }

    weight = state["weight"]
    if weight["enabled"] and weight["due"]:
        return {
            "order": "Weight Check",
            "reason": "A bodyweight measurement is currently due.",
        }

    return {
        "order": "Optional Progress",
        "reason": "All mandatory objectives currently tracked are secured.",
    }


def generate_gm_brief(session: Session):
    state = build_gm_state(session)
    decision = deterministic_order(state)
    return {
        "state": state,
        "decision": decision,
        "text": render_gm_brief(state, decision),
    }


def render_gm_brief(state, decision):
    lines = [
        "🤖 <b>GAME MASTER</b>",
        "",
        "<b>PRIMARY ORDER</b>",
        f"<b>{decision['order']}</b>",
        "",
    ]

    if state["priority"]:
        op = state["priority"][0]
        remaining = max(0, op["minimum"] - op["current"])
        lines.extend([
            f"Weekly progress · <b>{op['current']}/{op['minimum']}</b>",
            f"Remaining · <b>{remaining}</b> session{'' if remaining == 1 else 's'}",
        ])

    lines.extend(["", "<b>STATUS</b>"])

    focus = state["focus"]
    if focus["state"] != "DISABLED":
        lines.append(
            f"{focus['name']} · {focus['minutes']}/{focus['target']} min · {focus['state']}"
        )

    if state["nutrition"]["enabled"]:
        lines.append(f"Nutrition · {state['nutrition']['state']}")

    if state["weight"]["enabled"] and state["weight"]["latest_kg"] is not None:
        weight = f"{state['weight']['latest_kg']:.1f} kg"
        if state["weight"]["due"]:
            weight += " · CHECK DUE"
        lines.append(f"Weight · {weight}")

    lines.extend(["", "<b>ORDER</b>", decision["reason"]])
    return "\n".join(lines)
