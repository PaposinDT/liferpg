#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import sys
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).with_name("skill_catalog.json")

RATING_TO_LEVEL = {
    0: 1,
    1: 8,
    2: 15,
    3: 25,
    4: 40,
    5: 55,
    6: 70,
    7: 85,
    8: 100,
    9: 120,
    10: 140,
}

CEFR_TO_LEVEL = {
    "A0": 5,
    "A1": 30,
    "A2": 60,
    "B1": 90,
    "B2": 120,
    "C1": 150,
    "C2": 150,
}

PRIORITIES = ["MAIN", "SIDE", "MAINTENANCE", "BACKGROUND"]


def banner() -> None:
    print("\n" + "=" * 62)
    print(" LIFE RPG // AUTOMATED FOUNDING & INSTALLATION WIZARD")
    print("=" * 62)
    print("Single-user installation. Your answers become the founding state.\n")


def detect_timezone() -> str:
    candidates: list[str] = []
    try:
        value = Path("/etc/timezone").read_text().strip()
        if value:
            candidates.append(value)
    except OSError:
        pass
    try:
        link = Path("/etc/localtime").resolve()
        marker = "/zoneinfo/"
        if marker in str(link):
            candidates.append(str(link).split(marker, 1)[1])
    except OSError:
        pass
    for candidate in candidates:
        try:
            ZoneInfo(candidate)
            return candidate
        except Exception:
            continue
    return "UTC"


def ask(prompt: str, default: str | None = None, *, secret: bool = False) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    full = f"{prompt}{suffix}: "
    while True:
        value = getpass.getpass(full) if secret else input(full)
        value = value.strip()
        if value:
            return value
        if default is not None:
            return default
        print("A value is required.")


def yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "s", "si", "sì"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter y or n.")


def ask_int(prompt: str, default: int, low: int, high: int) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if low <= value <= high:
            return value
        print(f"Enter a value between {low} and {high}.")


def ask_float(prompt: str, default: float | None, low: float, high: float) -> float:
    while True:
        default_text = None if default is None else str(default)
        raw = ask(prompt, default_text).replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("Enter a number.")
            continue
        if low <= value <= high:
            return value
        print(f"Enter a value between {low} and {high}.")


def choice(prompt: str, choices: list[str], default_index: int = 0) -> str:
    print(prompt)
    for i, item in enumerate(choices, start=1):
        marker = " (default)" if i - 1 == default_index else ""
        print(f"  {i}. {item}{marker}")
    while True:
        raw = input(f"Choose 1-{len(choices)} [{default_index + 1}]: ").strip()
        if not raw:
            return choices[default_index]
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(choices):
            return choices[index]
        print("Invalid choice.")




def env_quote(value: Any) -> str:
    """Quote arbitrary values safely for Docker Compose .env files."""
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{text}"'

def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return result[:60] or "custom_skill"


def select_numbers(prompt: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    print(prompt)
    for idx, item in enumerate(items, start=1):
        print(f"  {idx:2d}. {item['name']}")
    print("Enter comma-separated numbers, 'all', or press Enter for none.")
    while True:
        raw = input("> ").strip().lower()
        if not raw:
            return []
        if raw == "all":
            return list(items)
        try:
            indexes = {int(part.strip()) - 1 for part in raw.split(",") if part.strip()}
        except ValueError:
            print("Invalid list.")
            continue
        if indexes and min(indexes) >= 0 and max(indexes) < len(items):
            return [items[i] for i in sorted(indexes)]
        print("One or more selections are outside the list.")


def assess_level(skill: dict[str, Any]) -> int:
    name = skill["name"]
    profile = skill.get("profile", "generic")
    print(f"\nInitial assessment: {name}")
    if profile == "language":
        level = choice(
            "Current practical language level:",
            ["A0 / almost none", "A1", "A2", "B1", "B2", "C1", "C2", "Enter exact Life RPG level"],
            0,
        )
        if level.startswith("Enter exact"):
            return ask_int("Exact Life RPG level", 1, 1, 150)
        cefr = level.split()[0]
        return CEFR_TO_LEVEL[cefr]

    print("Rate current real-world competence from 0 to 10.")
    print("  0 none | 2 beginner | 4 developing | 5 competent | 7 advanced | 8 expert | 10 mastery")
    rating = ask_int("Self-assessment", 3, 0, 10)
    estimated = RATING_TO_LEVEL[rating]
    if yes_no(f"Use estimated LVL {estimated}?", True):
        return estimated
    return ask_int("Exact Life RPG level", estimated, 1, 150)


def next_target(level: int, profile: str) -> int:
    checkpoints = [30, 60, 90, 120, 150] if profile == "language" else [20, 40, 60, 80, 100, 120, 135, 150]
    return next((target for target in checkpoints if target > level), 150)


def interactive_answers(catalog: dict[str, Any]) -> dict[str, Any]:
    banner()

    character_name = ask("Character / callsign", os.getenv("USER", "Operator"))
    detected_tz = detect_timezone()
    while True:
        timezone_name = ask("Timezone (IANA name)", detected_tz)
        try:
            ZoneInfo(timezone_name)
            break
        except Exception:
            print("Invalid timezone, e.g. Europe/Rome, Europe/Zurich, America/New_York.")

    print("\n--- SKILL SELECTION ---")
    chosen: list[dict[str, Any]] = []
    for category in catalog["categories"]:
        if category["code"] == "CUSTOM":
            continue
        items = [s for s in catalog["skills"] if s["category"] == category["code"]]
        selected = select_numbers(f"\n{category['name']} skills to track:", items)
        chosen.extend(selected)

    while yes_no("Add a custom skill?", False):
        name = ask("Custom skill name")
        code = slugify(name)
        existing = {s["code"] for s in chosen}
        base = code
        n = 2
        while code in existing:
            code = f"{base}_{n}"
            n += 1
        category = choice("Category:", ["COMBAT", "PHYSICAL", "KNOWLEDGE", "PRACTICAL", "FINANCE", "CUSTOM"], 5)
        profile = choice("Progression profile:", ["combat", "physical", "language", "knowledge", "practical", "finance", "generic"], 6)
        chosen.append({
            "code": code,
            "name": name,
            "category": category,
            "profile": profile,
            "default_goal": f"Develop mastery in {name}.",
        })

    if not chosen:
        print("At least one skill is required. Adding General Knowledge.")
        chosen = [next(s for s in catalog["skills"] if s["code"] == "general_knowledge")]

    print("\n--- FOUNDING ASSESSMENT ---")
    skills: list[dict[str, Any]] = []
    weekly: list[dict[str, Any]] = []
    main_count = 0

    for base in chosen:
        level = assess_level(base)
        allowed_priorities = PRIORITIES if main_count < 3 else PRIORITIES[1:]
        priority = choice(f"Priority for {base['name']}:", allowed_priorities, 0 if main_count < 3 else 1)
        if priority == "MAIN":
            main_count += 1
        default_goal = base.get("default_goal", "")
        goal = ask(f"Long-term goal for {base['name']}", default_goal)

        status = "ACTIVE"
        state = "ACTIVE"
        if yes_no(f"Start {base['name']} suspended/rusty?", False):
            status = "SUSPENDED"
            state = "RUSTY"

        item = {
            "code": base["code"],
            "name": base["name"],
            "category": base["category"],
            "progression_profile": base.get("profile", "generic"),
            "level": level,
            "priority": priority,
            "status": status,
            "state": state,
            "goal": goal,
        }
        skills.append(item)

        if status == "ACTIVE" and priority in {"MAIN", "SIDE"}:
            default_track = priority == "MAIN"
            if yes_no(f"Create weekly operation for {base['name']}?", default_track):
                default_min = 3 if priority == "MAIN" else 1
                minimum = ask_int("  Minimum sessions/week", default_min, 1, 14)
                stretch = ask_int("  Stretch target/week", max(minimum + 1, default_min + 1), minimum, 21)
                weekly.append({"skill": base["code"], "minimum": minimum, "stretch": stretch})

    active_skills = [s for s in skills if s["status"] == "ACTIVE"]

    print("\n--- DAILY SYSTEMS ---")
    focus_skill: dict[str, Any] | None = None
    if active_skills and yes_no("Configure a daily focus habit tied to one skill?", True):
        labels = [f"{s['name']} (LVL {s['level']})" for s in active_skills] + ["None"]
        selected = choice("Daily focus skill:", labels, 0)
        if selected != "None":
            focus_skill = active_skills[labels.index(selected)]
    focus_minutes = ask_int("Daily focus minutes", 15, 1, 240) if focus_skill else 0

    nutrition_enabled = yes_no("Track a daily calorie target?", True)
    nutrition_kcal = ask_int("Daily calorie target (kcal)", 2200, 1000, 6000) if nutrition_enabled else 0

    weight_tracking = yes_no("Track bodyweight?", True)
    start_weight = None
    target_weight = None
    if weight_tracking:
        start_weight = ask_float("Starting bodyweight kg", 70.0, 30, 300)
        if yes_no("Set a target bodyweight?", True):
            target_weight = ask_float("Target bodyweight kg", start_weight, 30, 300)

    print("\n--- TELEGRAM ---")
    print("Create a bot with @BotFather and get your numeric Telegram user ID before continuing.")
    while True:
        telegram_token = ask("Telegram bot token", secret=True)
        if re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", telegram_token):
            break
        print("That does not look like a Telegram bot token.")
    telegram_user_id = ask_int("Telegram numeric user ID", 1, 1, 9_999_999_999_999)

    print("\n--- LOCAL AI & REMOTE ACCESS ---")
    ai_enabled = yes_no("Install local AI parser (Ollama)?", True)
    ai_model = ask("Ollama model", "qwen3.5:0.8b") if ai_enabled else ""
    tailscale_enabled = yes_no("Install/configure Tailscale private remote access?", True)

    backup_time = ask("Automatic daily backup time (HH:MM)", "03:30")
    if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", backup_time):
        print("Invalid backup time, using 03:30.")
        backup_time = "03:30"

    return {
        "character_name": character_name,
        "timezone": timezone_name,
        "skills": skills,
        "weekly": weekly,
        "focus_skill": focus_skill["code"] if focus_skill else None,
        "focus_minutes": focus_minutes,
        "nutrition_enabled": nutrition_enabled,
        "nutrition_kcal": nutrition_kcal,
        "weight_tracking": weight_tracking,
        "starting_weight_kg": start_weight,
        "target_weight_kg": target_weight,
        "telegram_bot_token": telegram_token,
        "telegram_user_id": telegram_user_id,
        "ai_enabled": ai_enabled,
        "ai_model": ai_model,
        "tailscale_enabled": tailscale_enabled,
        "backup_time": backup_time,
    }


def normalize_answer_file(data: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    required = ["character_name", "timezone", "skills", "telegram_bot_token", "telegram_user_id"]
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"Answers file missing: {', '.join(missing)}")
    ZoneInfo(str(data["timezone"]))
    return data


def build_outputs(answers: dict[str, Any], catalog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    skills = answers["skills"]
    skill_map = {s["code"]: s for s in skills}

    quests: list[dict[str, Any]] = []
    schedules: list[dict[str, Any]] = []

    for skill in skills:
        if skill.get("status", "ACTIVE") != "ACTIVE":
            continue
        if skill.get("priority") == "MAIN":
            target = next_target(int(skill["level"]), str(skill.get("progression_profile", "generic")))
            quests.append({
                "code": f"main_{skill['code']}",
                "title": f"Advance {skill['name']}",
                "type": "MAIN",
                "status": "ACTIVE",
                "skill": skill["code"],
                "description": skill.get("goal") or f"Advance {skill['name']}.",
                "target_value": target,
                "target_unit": "SKILL_LEVEL",
            })

    for item in answers.get("weekly", []):
        skill = skill_map[item["skill"]]
        quest_code = f"weekly_{skill['code']}"
        quests.append({
            "code": quest_code,
            "title": f"{skill['name']} Weekly",
            "type": "WEEKLY",
            "status": "ACTIVE",
            "skill": skill["code"],
            "description": f"Maintain weekly consistency in {skill['name']}.",
            "target_value": None,
            "target_unit": None,
        })
        schedules.append({
            "quest_code": quest_code,
            "minimum": int(item["minimum"]),
            "stretch": int(item["stretch"]),
            "active": True,
        })

    body = {
        "weight_tracking": bool(answers.get("weight_tracking", True)),
        "starting_weight_kg": answers.get("starting_weight_kg"),
        "target_weight_kg": answers.get("target_weight_kg"),
    }
    if body["weight_tracking"] and body["target_weight_kg"] is not None:
        quests.append({
            "code": "bodyweight_target",
            "title": f"Road to {float(body['target_weight_kg']):.1f} kg",
            "type": "MAIN",
            "status": "ACTIVE",
            "skill": None,
            "description": "Reach the configured bodyweight target.",
            "target_value": int(round(float(body["target_weight_kg"]) * 1000)),
            "target_unit": "WEIGHT_G",
        })

    habits: list[dict[str, Any]] = []
    focus_code = ""
    focus_label = "Daily Focus"
    focus_skill_code = answers.get("focus_skill")
    if focus_skill_code:
        focus_skill = skill_map[focus_skill_code]
        focus_code = "daily_focus"
        focus_label = f"{focus_skill['name']} Consistency"
        habits.append({
            "code": focus_code,
            "name": focus_label,
            "skill": focus_skill_code,
            "status": "ACTIVE",
            "minimum_minutes": int(answers.get("focus_minutes", 15)),
            "true_streak": True,
            "affects_disc": True,
            "grants_skill_xp": False,
            "description": f"Complete at least {int(answers.get('focus_minutes', 15))} minutes of {focus_skill['name']} each day.",
        })

    if answers.get("nutrition_enabled", True):
        habits.append({
            "code": "nutrition_target",
            "name": "Nutrition Target",
            "skill": None,
            "status": "ACTIVE",
            "minimum_minutes": None,
            "true_streak": True,
            "affects_disc": True,
            "grants_skill_xp": False,
            "description": "Reach the configured daily calorie target.",
        })

    founding = {
        "schema_version": 1,
        "generated_on": date.today().isoformat(),
        "character": {"name": answers["character_name"]},
        "categories": catalog["categories"],
        "skills": skills,
        "quests": quests,
        "weekly_schedules": schedules,
        "habits": habits,
        "body": body,
    }

    install = {
        "schema_version": 1,
        "timezone": answers["timezone"],
        "tailscale_enabled": bool(answers.get("tailscale_enabled", True)),
        "ai_enabled": bool(answers.get("ai_enabled", True)),
        "ai_model": answers.get("ai_model") or "qwen3.5:0.8b",
        "backup_time": answers.get("backup_time", "03:30"),
    }

    pg_password = secrets.token_hex(24)
    env_lines = [
        "POSTGRES_DB=liferpg",
        "POSTGRES_USER=liferpg",
        f"POSTGRES_PASSWORD={pg_password}",
        f"DATABASE_URL=postgresql://liferpg:{pg_password}@postgres:5432/liferpg",
        "",
        f"TELEGRAM_BOT_TOKEN={answers['telegram_bot_token']}",
        f"TELEGRAM_USER_ID={int(answers['telegram_user_id'])}",
        "",
        "LIFERPG_VERSION=1.0.0",
        f"LIFERPG_CHARACTER_NAME={env_quote(answers['character_name'])}",
        f"LIFERPG_TIMEZONE={env_quote(answers['timezone'])}",
        "LIFERPG_FOUNDING_CONFIG=/config/founding.json",
        f"LIFERPG_FOCUS_HABIT_CODE={env_quote(focus_code)}",
        f"LIFERPG_FOCUS_HABIT_LABEL={env_quote(focus_label)}",
        f"LIFERPG_NUTRITION_ENABLED={'true' if answers.get('nutrition_enabled', True) else 'false'}",
        f"LIFERPG_NUTRITION_TARGET_KCAL={int(answers.get('nutrition_kcal') or 0)}",
        f"LIFERPG_WEIGHT_TRACKING_ENABLED={'true' if answers.get('weight_tracking', True) else 'false'}",
        f"LIFERPG_BACKUP_ROOT={os.getenv('LIFERPG_BACKUP_ROOT', '/srv/liferpg/backups')}",
        "",
        f"LIFERPG_OLLAMA_ENABLED={'true' if answers.get('ai_enabled', True) else 'false'}",
        "OLLAMA_BASE_URL=http://ollama:11434",
        f"OLLAMA_MODEL={env_quote(answers.get('ai_model') or 'qwen3.5:0.8b')}",
        f"COMPOSE_PROFILES={'ai' if answers.get('ai_enabled', True) else ''}",
        "",
        "LIFERPG_API_BIND=127.0.0.1",
        "LIFERPG_DASHBOARD_BIND=127.0.0.1",
        "",
    ]

    founding_md = [
        "# Life RPG Founding State",
        "",
        f"Generated: {date.today().isoformat()}",
        f"Character: {answers['character_name']}",
        f"Timezone: {answers['timezone']}",
        "",
        "## Skills",
    ]
    for skill in skills:
        founding_md.append(
            f"- {skill['name']}: LVL {skill['level']} · {skill['priority']} · {skill['status']}"
        )
    founding_md.extend([
        "",
        "## Rules",
        "- This file records the founding assessment only.",
        "- Once live activity history exists, do not rerun founding bootstrap casually.",
        "- The deterministic game engine remains authoritative for XP, levels and checkpoints.",
        "",
    ])

    return founding, install, "\n".join(env_lines), "\n".join(founding_md)


def write_outputs(output_dir: Path, founding: dict[str, Any], install: dict[str, Any], env_text: str, founding_md: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "founding.json").write_text(json.dumps(founding, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "install.json").write_text(json.dumps(install, indent=2) + "\n", encoding="utf-8")
    (output_dir / "FOUNDING_STATE.md").write_text(founding_md, encoding="utf-8")
    env_path = ROOT / ".env"
    env_path.write_text(env_text, encoding="utf-8")
    os.chmod(env_path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", type=Path, help="non-interactive answers JSON")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "config")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if args.answers:
        data = json.loads(args.answers.read_text(encoding="utf-8"))
        answers = normalize_answer_file(data, catalog)
    else:
        answers = interactive_answers(catalog)

    founding, install, env_text, founding_md = build_outputs(answers, catalog)
    write_outputs(args.output_dir, founding, install, env_text, founding_md)

    print("\nConfiguration generated successfully.")
    print(f"  Founding config: {args.output_dir / 'founding.json'}")
    print(f"  Install config:  {args.output_dir / 'install.json'}")
    print(f"  Secrets:         {ROOT / '.env'} (mode 0600)")


if __name__ == "__main__":
    main()
