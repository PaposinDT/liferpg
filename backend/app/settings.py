from __future__ import annotations

import os
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


APP_VERSION = os.getenv("LIFERPG_VERSION", "1.0.0")
CHARACTER_NAME = os.getenv("LIFERPG_CHARACTER_NAME", "Operator")
TIMEZONE_NAME = os.getenv("LIFERPG_TIMEZONE", "UTC")
FOCUS_HABIT_CODE = os.getenv("LIFERPG_FOCUS_HABIT_CODE", "").strip()
FOCUS_HABIT_LABEL = os.getenv("LIFERPG_FOCUS_HABIT_LABEL", "Daily Focus").strip() or "Daily Focus"
NUTRITION_ENABLED = _bool("LIFERPG_NUTRITION_ENABLED", True)
NUTRITION_TARGET_KCAL = _int("LIFERPG_NUTRITION_TARGET_KCAL", 2200)
WEIGHT_TRACKING_ENABLED = _bool("LIFERPG_WEIGHT_TRACKING_ENABLED", True)
OLLAMA_ENABLED = _bool("LIFERPG_OLLAMA_ENABLED", True)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://172.18.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:0.8b")
FOUNDING_CONFIG_PATH = Path(os.getenv("LIFERPG_FOUNDING_CONFIG", "/config/founding.json"))
BACKUP_ROOT = Path(os.getenv("LIFERPG_BACKUP_ROOT", "/srv/liferpg/backups"))


def character_rank(level: int) -> str:
    if level >= 100:
        return "Ascendant"
    if level >= 90:
        return "Master Operator"
    if level >= 80:
        return "Senior Operator"
    if level >= 65:
        return "Elite Operator"
    if level >= 50:
        return "Veteran Operator"
    if level >= 35:
        return "Field Operator"
    if level >= 20:
        return "Operator"
    if level >= 10:
        return "Initiate"
    return "Recruit"
