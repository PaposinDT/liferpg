#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
BACKUP_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
PRIORITIES = {"MAIN", "SIDE", "MAINTENANCE", "BACKGROUND"}
STATUSES = {"ACTIVE", "SUSPENDED", "ARCHIVED"}
STATES = {"ACTIVE", "RUSTY", "PAUSED"}
QUEST_TYPES = {"MAIN", "WEEKLY", "SIDE", "GOAL", "HABIT"}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Unable to parse {path}: {exc}") from exc
    require(isinstance(data, dict), f"{path}: root must be a JSON object")
    return data


def validate_founding(data: dict[str, Any]) -> None:
    require(data.get("schema_version") == 1, "founding.schema_version must be 1")
    character = data.get("character")
    require(isinstance(character, dict), "founding.character must be an object")
    require(bool(str(character.get("name", "")).strip()), "founding.character.name is required")

    categories = data.get("categories", [])
    require(isinstance(categories, list) and categories, "founding.categories must be a non-empty list")
    category_codes: set[str] = set()
    for i, category in enumerate(categories):
        require(isinstance(category, dict), f"categories[{i}] must be an object")
        code = str(category.get("code", "")).upper()
        require(bool(code), f"categories[{i}].code is required")
        require(code not in category_codes, f"duplicate category code: {code}")
        category_codes.add(code)

    skills = data.get("skills")
    require(isinstance(skills, list) and skills, "founding.skills must contain at least one skill")
    skill_codes: set[str] = set()
    main_count = 0
    for i, skill in enumerate(skills):
        require(isinstance(skill, dict), f"skills[{i}] must be an object")
        code = str(skill.get("code", ""))
        require(bool(CODE_RE.fullmatch(code)), f"invalid skill code: {code!r}")
        require(code not in skill_codes, f"duplicate skill code: {code}")
        skill_codes.add(code)
        require(bool(str(skill.get("name", "")).strip()), f"skills[{i}].name is required")
        category = str(skill.get("category", "CUSTOM")).upper()
        require(category in category_codes, f"skill {code} references unknown category {category}")
        level = int(skill.get("level", 1))
        require(1 <= level <= 150, f"skill {code} level must be 1..150")
        priority = str(skill.get("priority", "BACKGROUND")).upper()
        require(priority in PRIORITIES, f"skill {code} invalid priority: {priority}")
        if priority == "MAIN" and str(skill.get("status", "ACTIVE")).upper() == "ACTIVE":
            main_count += 1
        status = str(skill.get("status", "ACTIVE")).upper()
        require(status in STATUSES, f"skill {code} invalid status: {status}")
        state = str(skill.get("state", "ACTIVE")).upper()
        require(state in STATES, f"skill {code} invalid state: {state}")
    require(main_count <= 3, "at most three ACTIVE MAIN skills are allowed")

    quest_codes: set[str] = set()
    quests = data.get("quests", [])
    require(isinstance(quests, list), "founding.quests must be a list")
    for i, quest in enumerate(quests):
        require(isinstance(quest, dict), f"quests[{i}] must be an object")
        code = str(quest.get("code", ""))
        require(bool(CODE_RE.fullmatch(code)), f"invalid quest code: {code!r}")
        require(code not in quest_codes, f"duplicate quest code: {code}")
        quest_codes.add(code)
        qtype = str(quest.get("type", "MAIN")).upper()
        require(qtype in QUEST_TYPES, f"quest {code} invalid type: {qtype}")
        skill_code = quest.get("skill")
        if skill_code is not None:
            require(str(skill_code) in skill_codes, f"quest {code} references unknown skill {skill_code}")
        target_value = quest.get("target_value")
        if target_value is not None:
            require(isinstance(target_value, (int, float)), f"quest {code} target_value must be numeric/null")

    schedules = data.get("weekly_schedules", [])
    require(isinstance(schedules, list), "founding.weekly_schedules must be a list")
    for i, row in enumerate(schedules):
        require(isinstance(row, dict), f"weekly_schedules[{i}] must be an object")
        qcode = str(row.get("quest_code", ""))
        require(qcode in quest_codes, f"weekly schedule references unknown quest: {qcode}")
        minimum = int(row.get("minimum", 0))
        stretch = int(row.get("stretch", minimum))
        require(minimum >= 0, f"weekly schedule {qcode}: minimum must be >= 0")
        require(stretch >= minimum, f"weekly schedule {qcode}: stretch must be >= minimum")

    habit_codes: set[str] = set()
    habits = data.get("habits", [])
    require(isinstance(habits, list), "founding.habits must be a list")
    for i, habit in enumerate(habits):
        require(isinstance(habit, dict), f"habits[{i}] must be an object")
        code = str(habit.get("code", ""))
        require(bool(CODE_RE.fullmatch(code)), f"invalid habit code: {code!r}")
        require(code not in habit_codes, f"duplicate habit code: {code}")
        habit_codes.add(code)
        skill_code = habit.get("skill")
        if skill_code is not None:
            require(str(skill_code) in skill_codes, f"habit {code} references unknown skill {skill_code}")
        minutes = habit.get("minimum_minutes")
        if minutes is not None:
            require(int(minutes) >= 0, f"habit {code}: minimum_minutes must be >= 0")

    body = data.get("body", {})
    require(isinstance(body, dict), "founding.body must be an object")
    for key in ("starting_weight_kg", "target_weight_kg"):
        value = body.get(key)
        if value is not None:
            require(isinstance(value, (int, float)) and 20 <= float(value) <= 500, f"body.{key} outside supported range")


def validate_install(data: dict[str, Any]) -> None:
    require(data.get("schema_version") == 1, "install.schema_version must be 1")
    tz = str(data.get("timezone", ""))
    try:
        ZoneInfo(tz)
    except Exception as exc:
        raise ValidationError(f"invalid install timezone: {tz!r}") from exc
    require(isinstance(data.get("tailscale_enabled"), bool), "install.tailscale_enabled must be boolean")
    require(isinstance(data.get("ai_enabled"), bool), "install.ai_enabled must be boolean")
    require(bool(str(data.get("ai_model", "")).strip()), "install.ai_model is required")
    backup_time = str(data.get("backup_time", ""))
    require(bool(BACKUP_TIME_RE.fullmatch(backup_time)), "install.backup_time must be HH:MM")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated Life RPG configuration")
    parser.add_argument("founding", type=Path, nargs="?", default=Path("config/founding.json"))
    parser.add_argument("install", type=Path, nargs="?", default=Path("config/install.json"))
    args = parser.parse_args()

    try:
        validate_founding(load_json(args.founding))
        validate_install(load_json(args.install))
    except ValidationError as exc:
        raise SystemExit(f"CONFIG INVALID: {exc}")

    print("CONFIG VALID")


if __name__ == "__main__":
    main()
