from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Character,
    Checkpoint,
    Skill,
    SkillLevelThreshold,
    SkillProgressionVersion,
    XPTransaction,
)


# Each tuple:
# (start_level, end_level, total_xp_between_anchors)
#
# The total XP is distributed across every level transition while
# guaranteeing the exact cumulative amount at the upper anchor.

CURVES = {
    "muay_thai": [
        (1, 20, 500),
        (20, 45, 900),
        (45, 70, 1300),
        (70, 90, 1500),
        (90, 105, 1600),
        (105, 120, 2200),
        (120, 135, 2800),
        (135, 150, 3500),
    ],

    "shooting": [
        (1, 20, 400),
        (20, 40, 600),
        (40, 60, 800),
        (60, 80, 1200),
        (80, 100, 1800),
        (100, 120, 2400),
        (120, 135, 2500),
        (135, 150, 3200),
    ],

    "kickboxing": [
        (1, 30, 500),
        (30, 60, 900),
        (60, 85, 1200),
        (85, 105, 1400),
        (105, 125, 1800),
        (125, 150, 2200),
    ],

    "boxing": [
        (1, 20, 400),
        (20, 50, 1000),
        (50, 75, 1200),
        (75, 95, 1400),
        (95, 115, 1800),
        (115, 135, 2200),
        (135, 150, 2200),
    ],

    "no_gi_grappling": [
        (1, 20, 400),
        (20, 50, 1400),
        (50, 75, 1600),
        (75, 90, 1400),
        (90, 115, 2500),
        (115, 135, 2600),
        (135, 150, 2500),
    ],

    "bjj_gi": [
        (1, 30, 500),
        (30, 50, 1000),
        (50, 90, 2200),
        (90, 120, 2600),
        (120, 140, 2200),
        (140, 150, 1600),
    ],

    "wrestling": [
        (1, 20, 400),
        (20, 40, 800),
        (40, 65, 1200),
        (65, 90, 1500),
        (90, 115, 2000),
        (115, 135, 2200),
        (135, 150, 2200),
    ],

    "mma": [
        (1, 25, 500),
        (25, 50, 1000),
        (50, 75, 1200),
        (75, 95, 1400),
        (95, 115, 1800),
        (115, 135, 2200),
        (135, 150, 2200),
    ],

    "strength": [
        (1, 20, 300),
        (20, 45, 600),
        (45, 70, 900),
        (70, 85, 900),
        (85, 105, 1500),
        (105, 125, 2200),
        (125, 140, 2200),
        (140, 150, 2000),
    ],

    "endurance": [
        (1, 25, 400),
        (25, 45, 600),
        (45, 60, 600),
        (60, 80, 1200),
        (80, 100, 1600),
        (100, 120, 2200),
        (120, 135, 2200),
        (135, 150, 3000),
    ],

    "mobility": [
        (1, 20, 200),
        (20, 45, 500),
        (45, 70, 800),
        (70, 95, 1200),
        (95, 115, 1200),
        (115, 135, 1500),
        (135, 150, 1800),
    ],

    "russian": [
        (1, 30, 1200),
        (30, 60, 1800),
        (60, 90, 3000),
        (90, 120, 4200),
        (120, 150, 6000),
    ],

    "german": [
        (1, 30, 1200),
        (30, 60, 1800),
        (60, 90, 3000),
        (90, 120, 4200),
        (120, 150, 6000),
    ],

    "general_knowledge": [
        (1, 30, 500),
        (30, 60, 900),
        (60, 80, 900),
        (80, 100, 1100),
        (100, 120, 1400),
        (120, 140, 1800),
        (140, 150, 2000),
    ],

    "guitar": [
        (1, 20, 300),
        (20, 35, 400),
        (35, 50, 500),
        (50, 70, 700),
        (70, 90, 900),
        (90, 110, 1200),
        (110, 130, 1600),
        (130, 150, 2000),
    ],

    "cooking": [
        (1, 25, 250),
        (25, 45, 400),
        (45, 65, 500),
        (65, 85, 600),
        (85, 105, 800),
        (105, 125, 1000),
        (125, 140, 1100),
        (140, 150, 1000),
    ],

    "life_skills": [
        (1, 25, 300),
        (25, 45, 500),
        (45, 65, 700),
        (65, 85, 900),
        (85, 105, 1100),
        (105, 125, 1300),
        (125, 140, 1300),
        (140, 150, 1200),
    ],

    "personal_finance": [
        (1, 40, 500),
        (40, 65, 500),
        (65, 85, 500),
        (85, 100, 600),
        (100, 120, 900),
        (120, 135, 1000),
        (135, 150, 1200),
    ],

    "investing": [
        (1, 40, 500),
        (40, 65, 600),
        (65, 90, 800),
        (90, 105, 700),
        (105, 120, 900),
        (120, 135, 1100),
        (135, 150, 1300),
    ],
}


CHECKPOINTS = {
    "muay_thai": [
        (20, "Fundamentals"),
        (45, "Technical Fighter"),
        (70, "Competitive Experience"),
        (90, "Advanced Protected Fighter"),
        (105, "Full Contact Ready"),
        (120, "Protected Pro"),
        (135, "Unprotected Pro Ready"),
        (150, "Professional Full Contact Fighter"),
    ],

    "shooting": [
        (20, "Safe Independent Range Foundation"),
        (40, "Competent Multi-Position Shooter"),
        (60, "Mixed-Platform Competency"),
        (80, "Advanced Consistency"),
        (100, "Advanced Shooter"),
        (120, "Advanced Multi-Platform Shooter"),
        (135, "Expert Personal Standard"),
        (150, "Multi-Platform Shooting Mastery"),
    ],

    "kickboxing": [
        (30, "Fundamentals"),
        (60, "Competent Sparring"),
        (85, "Advanced Amateur"),
        (105, "Full-Contact Competition"),
        (125, "Professional Ready"),
        (150, "Professional Kickboxer"),
    ],

    "boxing": [
        (20, "Boxing Basics"),
        (50, "Competent Boxer"),
        (75, "Solid Experienced Sparring"),
        (95, "Amateur Ready"),
        (115, "Competitive Boxer"),
        (135, "Professional Ready"),
        (150, "Professional Boxer"),
    ],

    "no_gi_grappling": [
        (20, "Survival Fundamentals"),
        (50, "Solid Blue-Belt Equivalent"),
        (75, "Complete Intermediate Grappler"),
        (90, "Purple-Belt Equivalent"),
        (115, "Brown-Belt Equivalent"),
        (135, "Black-Belt Equivalent"),
        (150, "High-Level Professional Grappler"),
    ],

    "bjj_gi": [
        (30, "Competent White Belt"),
        (50, "Blue Belt"),
        (90, "Purple Belt"),
        (120, "Brown Belt"),
        (140, "Black Belt"),
        (150, "Advanced Black-Belt Competition"),
    ],

    "wrestling": [
        (20, "Wrestling Fundamentals"),
        (40, "Live Entries"),
        (65, "Chain Wrestling"),
        (90, "Strong Wrestler"),
        (115, "Advanced Wrestler"),
        (135, "Expert Wrestler"),
        (150, "High Competitive Standard"),
    ],

    "mma": [
        (25, "Basic MMA Integration"),
        (50, "MMA Sparring"),
        (75, "Competent MMA Fighter"),
        (95, "Amateur Ready"),
        (115, "Amateur Fighter"),
        (135, "Professional Ready"),
        (150, "Professional MMA Fighter"),
    ],

    "strength": [
        (20, "Strength Foundation"),
        (45, "Strong Base"),
        (70, "Advanced Bodyweight Strength"),
        (85, "Advanced Relative Strength"),
        (105, "Very Advanced Strength"),
        (125, "Exceptional Strength"),
        (140, "Elite Personal Standard"),
        (150, "Relative Strength Mastery"),
    ],

    "endurance": [
        (25, "5K Continuous"),
        (45, "10K Base"),
        (60, "Athletic Cardio"),
        (80, "Strong Conditioning"),
        (100, "Advanced Fight Conditioning"),
        (120, "Elite Conditioning"),
        (135, "12-Round Fight Engine"),
        (150, "Endurance Mastery"),
    ],

    "mobility": [
        (20, "Functional Mobility"),
        (45, "Comfortable Toe Touch"),
        (70, "Deep Forward Fold"),
        (95, "Near Split"),
        (115, "Full Split"),
        (135, "Controlled Full Split"),
        (150, "Mobility Mastery"),
    ],

    "russian": [
        (30, "A1"),
        (60, "A2"),
        (90, "B1"),
        (120, "B2"),
        (150, "C1"),
    ],

    "german": [
        (30, "A1"),
        (60, "A2"),
        (90, "B1"),
        (120, "B2"),
        (150, "C1"),
    ],

    "general_knowledge": [
        (30, "Basic Foundation"),
        (60, "Broad Foundation"),
        (80, "Well Informed"),
        (100, "Strong General Knowledge"),
        (120, "Very Broad Knowledge"),
        (140, "Exceptional Breadth"),
        (150, "Broad Knowledge Mastery"),
    ],

    "guitar": [
        (20, "Open Chords"),
        (35, "Barre and Power Chords"),
        (50, "Complete Song"),
        (70, "Small Repertoire"),
        (90, "Intermediate Guitarist"),
        (110, "Advanced Repertoire"),
        (130, "Highly Competent Guitarist"),
        (150, "Guitar Mastery"),
    ],

    "cooking": [
        (25, "Basic Independence"),
        (45, "Competent Home Cook"),
        (65, "Reliable Home Cook"),
        (85, "Broad Repertoire"),
        (105, "Advanced Home Cook"),
        (125, "Strong Improvisation"),
        (140, "Highly Skilled Home Cook"),
        (150, "Complete Home-Cooking Mastery"),
    ],

    "life_skills": [
        (25, "Basic Independence"),
        (45, "Practical Foundation"),
        (65, "Capable All-Rounder"),
        (85, "Self-Sufficient"),
        (105, "Broad Practical Competence"),
        (125, "Advanced Self-Reliance"),
        (140, "Highly Capable All-Rounder"),
        (150, "Practical Mastery"),
    ],

    "personal_finance": [
        (40, "Organized Finances"),
        (65, "Structured Financial System"),
        (85, "Automated Financial System"),
        (100, "Strong Liquidity"),
        (120, "Home Financing Ready"),
        (135, "High Financial Security"),
        (150, "Personal Financial Freedom"),
    ],

    "investing": [
        (40, "Investment Foundations"),
        (65, "Portfolio Construction"),
        (90, "Advanced Investor"),
        (105, "Documented Investment Process"),
        (120, "Advanced Portfolio Management"),
        (135, "Professional-Style Process"),
        (150, "Personal PM Mastery"),
    ],
}


PROFILE_CURVE_SOURCE = {
    "language": "russian",
    "combat": "boxing",
    "physical": "strength",
    "knowledge": "general_knowledge",
    "practical": "life_skills",
    "finance": "investing",
    "generic": "general_knowledge",
}

GENERIC_CHECKPOINTS = [
    (20, "Foundation"),
    (40, "Developing Competence"),
    (60, "Competent"),
    (80, "Advanced"),
    (100, "Expert Track"),
    (120, "Mastery Track"),
    (135, "Elite Standard"),
    (150, "Mastery"),
]

LANGUAGE_CHECKPOINTS = [
    (30, "A1"),
    (60, "A2"),
    (90, "B1"),
    (120, "B2"),
    (150, "C1"),
]


def build_thresholds(segments):
    thresholds = {1: 0}
    cumulative = 0

    for start, end, segment_xp in segments:
        if start not in thresholds:
            raise ValueError(f"Missing threshold anchor at level {start}")

        cumulative = thresholds[start]
        transitions = end - start
        base = segment_xp // transitions
        remainder = segment_xp % transitions

        for offset, level in enumerate(range(start + 1, end + 1), start=1):
            step_xp = base + (1 if offset <= remainder else 0)
            cumulative += step_xp
            thresholds[level] = cumulative

    if set(thresholds) != set(range(1, 151)):
        missing = sorted(set(range(1, 151)) - set(thresholds))
        raise ValueError(f"Curve incomplete. Missing levels: {missing}")

    return thresholds


def upsert_founder_xp(session, skill, amount):
    correlation_id = f"FOUNDING-SKILL-{skill.code}"
    tx = session.scalar(
        select(XPTransaction).where(
            XPTransaction.correlation_id == correlation_id,
            XPTransaction.transaction_type == "FOUNDING",
        )
    )

    if tx is None:
        tx = XPTransaction(
            target_type="SKILL",
            skill_id=skill.id,
            amount=amount,
            transaction_type="FOUNDING",
            source_type="FOUNDING_ASSESSMENT",
            source_id=None,
            base_amount=amount,
            streak_bonus=0,
            spillover=0,
            banked=False,
            correlation_id=correlation_id,
            reversed=False,
        )
        session.add(tx)
    else:
        tx.amount = amount
        tx.base_amount = amount
        tx.reversed = False


def _profile_for(skill_data):
    profile = str(skill_data.get("progression_profile") or "").lower().strip()
    if profile:
        return profile
    category = str(skill_data.get("category") or "CUSTOM").lower()
    return {
        "combat": "combat",
        "physical": "physical",
        "knowledge": "knowledge",
        "practical": "practical",
        "finance": "finance",
    }.get(category, "generic")


def _curve_for(code, skill_data):
    if code in CURVES:
        return CURVES[code]
    source = PROFILE_CURVE_SOURCE.get(_profile_for(skill_data), "general_knowledge")
    return CURVES[source]


def _checkpoints_for(code, skill_data):
    if code in CHECKPOINTS:
        return CHECKPOINTS[code]
    if _profile_for(skill_data) == "language":
        return LANGUAGE_CHECKPOINTS
    return GENERIC_CHECKPOINTS


def main():
    from app.founding_config import load_founding_config
    from app.character_service import require_character

    config = load_founding_config()
    skill_config = {str(item["code"]): item for item in config["skills"]}

    with SessionLocal() as session:
        skills = {
            skill.code: skill
            for skill in session.scalars(select(Skill)).all()
            if skill.deleted_at is None
        }

        configured_codes = set(skill_config)
        missing = configured_codes - set(skills)
        if missing:
            raise RuntimeError(f"Configured skills missing from database: {sorted(missing)}")

        for code in sorted(configured_codes):
            skill = skills[code]
            data = skill_config[code]
            segments = _curve_for(code, data)

            progression = session.scalar(
                select(SkillProgressionVersion).where(
                    SkillProgressionVersion.skill_id == skill.id,
                    SkillProgressionVersion.version == 1,
                )
            )
            if progression is None:
                progression = SkillProgressionVersion(
                    skill_id=skill.id,
                    version=1,
                    name="Life RPG Founding Curve v1",
                    active=True,
                    reason="Installer-generated founding progression.",
                )
                session.add(progression)
                session.flush()
            else:
                progression.active = True
                progression.name = "Life RPG Founding Curve v1"

            session.execute(
                delete(SkillLevelThreshold).where(
                    SkillLevelThreshold.progression_version_id == progression.id
                )
            )

            thresholds = build_thresholds(segments)
            for level in range(1, 151):
                session.add(
                    SkillLevelThreshold(
                        progression_version_id=progression.id,
                        level=level,
                        cumulative_xp_required=thresholds[level],
                    )
                )

            founding_xp = thresholds[skill.current_level]
            skill.total_xp = founding_xp
            skill.banked_xp = 0
            upsert_founder_xp(session, skill, founding_xp)

            checkpoint_defs = _checkpoints_for(code, data)
            expected_levels = {level for level, _ in checkpoint_defs}
            existing = session.scalars(
                select(Checkpoint).where(Checkpoint.skill_id == skill.id)
            ).all()
            for checkpoint in existing:
                if checkpoint.level not in expected_levels:
                    session.delete(checkpoint)

            for level, name in checkpoint_defs:
                checkpoint = session.scalar(
                    select(Checkpoint).where(
                        Checkpoint.skill_id == skill.id,
                        Checkpoint.level == level,
                    )
                )
                if checkpoint is None:
                    checkpoint = Checkpoint(skill_id=skill.id, level=level, name=name)
                    session.add(checkpoint)
                checkpoint.name = name
                if level <= skill.current_level:
                    checkpoint.status = "CLEARED"
                    checkpoint.user_note = "Founding checkpoint"
                else:
                    checkpoint.status = "LOCKED"
                    checkpoint.user_note = None
                    checkpoint.reached_at = None
                    checkpoint.cleared_at = None

        character = require_character(session)
        correlation_id = f"FOUNDING-CHARACTER-{character.name.upper().replace(' ', '-')[:32]}"
        character_tx = session.scalar(
            select(XPTransaction).where(
                XPTransaction.correlation_id == correlation_id,
                XPTransaction.transaction_type == "FOUNDING",
            )
        )
        if character_tx is None:
            character_tx = XPTransaction(
                target_type="CHARACTER",
                skill_id=None,
                amount=character.character_xp,
                transaction_type="FOUNDING",
                source_type="FOUNDING_ASSESSMENT",
                source_id=None,
                base_amount=character.character_xp,
                streak_bonus=0,
                spillover=0,
                banked=False,
                correlation_id=correlation_id,
                reversed=False,
            )
            session.add(character_tx)
        else:
            character_tx.amount = character.character_xp
            character_tx.base_amount = character.character_xp
            character_tx.reversed = False

        session.commit()
        print("Progression dataset applied successfully.")
        print(f"Skills with curves: {len(configured_codes)}")
        print(f"Total thresholds: {len(configured_codes) * 150}")


if __name__ == "__main__":
    main()
