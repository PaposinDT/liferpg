from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.settings import FOUNDING_CONFIG_PATH


class FoundingConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_founding_config(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else FOUNDING_CONFIG_PATH
    if not target.exists():
        raise FoundingConfigError(
            f"Founding config not found: {target}. Run the installer/onboarding first."
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundingConfigError(f"Unable to read founding config: {target}") from exc

    if not isinstance(data, dict):
        raise FoundingConfigError("Founding config root must be a JSON object")
    if not data.get("character", {}).get("name"):
        raise FoundingConfigError("Founding config is missing character.name")
    if not isinstance(data.get("skills"), list) or not data["skills"]:
        raise FoundingConfigError("Founding config must contain at least one skill")
    return data


def clear_cache() -> None:
    load_founding_config.cache_clear()
