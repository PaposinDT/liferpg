import json
import re
import unicodedata
import urllib.request

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import OLLAMA_BASE_URL, OLLAMA_ENABLED, OLLAMA_MODEL
from app.models import (
    ActivityTemplate,
    Skill,
)



@dataclass
class ActivityCandidate:
    skill_code: str
    template_code: str
    duration_minutes: int | None
    confidence: str
    source: str
    original_text: str


def normalize(text: str) -> str:
    text = text.lower()

    text = (
        unicodedata.normalize(
            "NFKD",
            text,
        )
        .encode("ascii", "ignore")
        .decode()
    )

    return " ".join(
        text.split()
    )


def deterministic_duration(
    text: str,
) -> int | None:
    raw = normalize(text)

    if re.search(
        r"\b(mezz'?ora|mezza ora)\b",
        raw,
    ):
        return 30

    if re.search(
        r"\b(un'?ora|1\s*ora)\s+e\s+mezza\b",
        raw,
    ):
        return 90

    match = re.search(
        r"\b(\d+)\s*h\s*(\d{1,2})\b",
        raw,
    )

    if match:
        return (
            int(match.group(1)) * 60
            + int(match.group(2))
        )

    match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*"
        r"(?:ora|ore|hour|hours)"
        r"(?:\s+e\s+(\d{1,2}))?",
        raw,
    )

    if match:
        hours = float(
            match.group(1).replace(
                ",",
                ".",
            )
        )

        minutes = (
            int(match.group(2))
            if match.group(2)
            else 0
        )

        return round(
            hours * 60 + minutes
        )

    match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*h\b",
        raw,
    )

    if match:
        return round(
            float(
                match.group(1)
                .replace(",", ".")
            )
            * 60
        )

    match = re.search(
        r"\b(\d+)\s*"
        r"(?:m|min|mins|minuto|minuti|minutes?)\b",
        raw,
    )

    if match:
        return int(
            match.group(1)
        )

    return None


def deterministic_skill(
    text: str,
    skills: list[Skill],
):
    raw = normalize(text)

    aliases = {
        "muay thai": "muay_thai",
        "thai boxe": "muay_thai",
        "russo": "russian",
        "russian": "russian",
        "tedesco": "german",
        "german": "german",
        "forza": "strength",
        "strength": "strength",
        "resistenza": "endurance",
        "endurance": "endurance",
        "mobilita": "mobility",
        "mobility": "mobility",
        "tiro": "shooting",
        "shooting": "shooting",
        "cucina": "cooking",
        "cooking": "cooking",
        "chitarra": "guitar",
        "guitar": "guitar",
    }

    by_code = {
        skill.code: skill
        for skill in skills
    }

    for phrase, code in aliases.items():
        if (
            phrase in raw
            and code in by_code
        ):
            return by_code[code]

    for skill in skills:
        if normalize(skill.name) in raw:
            return skill

    return None


def ollama_candidate(text, allowed):
    catalog = "\n".join(
        f"{s}|{t}|{n}|{d}"
        for s, t, n, d in allowed
    )

    prompt = f"""Parse this Life RPG activity.
USER: {text}
ALLOWED:
{catalog}
Return ONLY JSON: skill_code, template_code, duration_minutes, confidence.
Never invent codes. Preserve explicit duration exactly."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": "15m",
        "options": {
            "temperature": 0.0,
            "num_ctx": 2048,
            "num_predict": 90,
        },
    }

    req = urllib.request.Request(
        OLLAMA_BASE_URL + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(
        req,
        timeout=180,
    ) as response:
        result = json.load(response)

    return json.loads(result["response"])


def choose_template(templates, duration):
    usable = [
        t for t in templates
        if t.default_duration_minutes is not None
    ]

    if not usable or duration is None:
        return None

    return min(
        usable,
        key=lambda t: abs(
            t.default_duration_minutes - duration
        ),
    )


def parse_activity(session: Session, text: str):
    skills = session.scalars(
        select(Skill).where(Skill.status == "ACTIVE")
    ).all()
    templates = session.scalars(
        select(ActivityTemplate).where(ActivityTemplate.enabled.is_(True))
    ).all()

    by_id = {skill.id: skill for skill in skills}
    allowed = []
    by_skill = {}
    for template in templates:
        skill = by_id.get(template.skill_id)
        if skill is None:
            continue
        by_skill.setdefault(skill.id, []).append(template)
        allowed.append((
            skill.code,
            template.code,
            template.name,
            template.default_duration_minutes,
        ))

    duration = deterministic_duration(text)
    known_skill = deterministic_skill(text, skills)
    ai = {}

    if OLLAMA_ENABLED:
        allowed_for_ai = allowed
        if known_skill is not None:
            allowed_for_ai = [item for item in allowed if item[0] == known_skill.code]
        try:
            ai = ollama_candidate(text, allowed_for_ai)
        except Exception:
            # The operational system remains usable if the local model is offline.
            ai = {}

    valid_pairs = {(s, template) for s, template, _, _ in allowed}
    ai_pair = (ai.get("skill_code"), ai.get("template_code"))

    if known_skill is not None:
        skill = known_skill
    elif ai_pair in valid_pairs:
        skill = next(s for s in skills if s.code == ai_pair[0])
    else:
        raise ValueError("Could not identify a valid skill. Use the Add menu or name the skill explicitly.")

    skill_templates = by_skill.get(skill.id, [])
    template = next(
        (t for t in skill_templates if (skill.code, t.code) == ai_pair),
        None,
    )

    if template is None:
        template = choose_template(skill_templates, duration)

    if template is None and skill_templates:
        # Prefer a normal/default session for deterministic fallback.
        template = next(
            (t for t in skill_templates if "normal" in t.code or "normal" in t.name.lower()),
            skill_templates[0],
        )

    if template is None:
        raise ValueError("Could not identify a valid activity template.")

    final_duration = duration if duration is not None else ai.get("duration_minutes")
    if not isinstance(final_duration, int):
        final_duration = template.default_duration_minutes
    if final_duration is None:
        final_duration = 45
    if not 1 <= final_duration <= 1440:
        raise ValueError("Invalid duration.")

    confidence = "HIGH" if duration is not None and known_skill is not None else (
        "MEDIUM" if known_skill is not None else "AI_VERIFIED"
    )
    source = "HYBRID_VERIFIED" if OLLAMA_ENABLED and ai else "DETERMINISTIC"

    return ActivityCandidate(
        skill_code=skill.code,
        template_code=template.code,
        duration_minutes=final_duration,
        confidence=confidence,
        source=source,
        original_text=text,
    )

