from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActivityTemplate, Skill


TEMPLATES = [
    # MUAY THAI
    ("muay_thai", "muay_thai_brief", "Brief Training", 14, 50),
    ("muay_thai", "muay_thai_normal", "Normal Training", 20, 90),
    ("muay_thai", "muay_thai_long", "Long Training", 28, 120),
    ("muay_thai", "muay_thai_sparring", "Sparring-Oriented Session", 24, 90),
    ("muay_thai", "muay_thai_camp", "Intensive Camp Session", 35, 120),
    ("muay_thai", "muay_thai_match", "Significant Match / Interclub", 50, None),

    # RUSSIAN
    ("russian", "russian_15", "Russian 15m", 5, 15),
    ("russian", "russian_30", "Russian 30m", 10, 30),
    ("russian", "russian_60", "Russian 60m", 18, 60),
    ("russian", "russian_listening_15", "Listening 15m", 4, 15),
    ("russian", "russian_listening_30", "Listening 30m", 8, 30),
    ("russian", "russian_conversation_15", "Conversation 15m", 8, 15),
    ("russian", "russian_conversation_30", "Conversation 30m", 15, 30),
    ("russian", "russian_lesson", "Structured Lesson", 18, 50),
    ("russian", "russian_long", "Long Study Session", 30, 120),

    # SHOOTING
    ("shooting", "shooting_static_short", "Short Static Session", 10, None),
    ("shooting", "shooting_static_full", "Full Static Session", 15, None),
    ("shooting", "shooting_dynamic", "Dynamic Session", 20, None),
    ("shooting", "shooting_mixed", "Mixed Handgun / Rifle Session", 25, None),
    ("shooting", "shooting_test", "Structured Test / Training", 30, None),
    ("shooting", "shooting_course_half", "Half-Day Course", 50, None),
    ("shooting", "shooting_course_full", "Full-Day Course", 80, None),
    ("shooting", "shooting_qualification", "Significant Qualification", 40, None),

    # STRENGTH
    ("strength", "strength_short", "Short Strength Session", 8, None),
    ("strength", "strength_normal", "Normal Strength Session", 12, None),
    ("strength", "strength_long", "Long Strength Session", 16, None),
    ("strength", "strength_test", "Strength Test", 10, None),
    ("strength", "strength_pr", "Significant PR", 15, None),
    ("strength", "strength_skill", "Important Calisthenics Skill", 20, None),

    # NO-GI GRAPPLING
    ("no_gi_grappling", "grappling_brief", "Brief Grappling Session", 14, 50),
    ("no_gi_grappling", "grappling_normal", "Normal Grappling Session", 20, 75),
    ("no_gi_grappling", "grappling_long", "Long Grappling Session", 27, 120),
    ("no_gi_grappling", "grappling_sparring", "Intense Open Mat / Sparring", 22, None),
    ("no_gi_grappling", "grappling_competition", "Competition", 40, None),

    # ENDURANCE
    ("endurance", "endurance_short", "20-30m Endurance", 8, 25),
    ("endurance", "endurance_normal", "40-60m Endurance", 14, 50),
    ("endurance", "endurance_long", "Long Run / Endurance", 18, None),
    ("endurance", "endurance_intervals", "Serious Intervals", 16, None),
    ("endurance", "endurance_fight", "Fight Conditioning", 18, None),
    ("endurance", "endurance_test", "Significant Endurance Test", 15, None),

    # MOBILITY
    ("mobility", "mobility_5", "Mobility 5m", 2, 5),
    ("mobility", "mobility_10", "Mobility 10m", 5, 10),
    ("mobility", "mobility_20", "Mobility 20m", 8, 20),
    ("mobility", "mobility_long", "Long Mobility Session", 11, None),
    ("mobility", "mobility_milestone", "Mobility Milestone", 15, None),

    # GERMAN
    ("german", "german_brief", "Meaningful Brief Use", 3, None),
    ("german", "german_conversation", "German Conversation", 8, 30),
    ("german", "german_extended", "Extended German Use", 12, None),
    ("german", "german_study_30", "German Study 30m", 10, 30),
    ("german", "german_lesson", "German Lesson", 18, 60),

    # GENERAL KNOWLEDGE
    ("general_knowledge", "gk_short", "Short Article / Video", 3, 10),
    ("general_knowledge", "gk_serious", "Serious Learning Session", 6, 25),
    ("general_knowledge", "gk_deep", "Deep Learning Session", 10, 60),
    ("general_knowledge", "gk_documentary", "Documentary", 8, None),
    ("general_knowledge", "gk_quiz", "Serious Quiz", 8, None),

    # GUITAR
    ("guitar", "guitar_10", "Guitar 10m", 4, 10),
    ("guitar", "guitar_20", "Guitar 20m", 8, 20),
    ("guitar", "guitar_40", "Guitar 40m", 14, 40),
    ("guitar", "guitar_60", "Guitar 60m", 18, 60),
    ("guitar", "guitar_new_skill", "New Guitar Technique / Riff", 10, None),
    ("guitar", "guitar_song", "Complete Song", 25, None),

    # COOKING
    ("cooking", "cooking_known", "Known Meal / Meal Prep", 2, None),
    ("cooking", "cooking_new_simple", "New Simple Recipe", 6, None),
    ("cooking", "cooking_new_serious", "New Serious Recipe", 10, None),
    ("cooking", "cooking_new_technique", "New Technique", 12, None),
    ("cooking", "cooking_difficult", "Difficult Technique", 20, None),
    ("cooking", "cooking_complex", "Complex Dish Successful", 15, None),

    # LIFE SKILLS
    ("life_skills", "life_small", "Small Practical Problem", 5, None),
    ("life_skills", "life_new_skill", "New Practical Ability", 10, None),
    ("life_skills", "life_important", "Important Practical Skill", 20, None),
    ("life_skills", "life_course", "Practical Course / Training", 30, None),

    # PERSONAL FINANCE
    ("personal_finance", "finance_month", "Monthly Plan Respected", 5, None),
    ("personal_finance", "finance_system", "Financial System Improvement", 10, None),
    ("personal_finance", "finance_emergency", "Emergency Fund Milestone", 20, None),
    ("personal_finance", "finance_house", "House Fund Milestone", 30, None),

    # INVESTING
    ("investing", "investing_review", "Serious Portfolio Review", 5, None),
    ("investing", "investing_concept", "New Investment Concept", 5, None),
    ("investing", "investing_rebalance", "Reasoned Rebalance", 10, None),
    ("investing", "investing_process", "Documented Process Improvement", 15, None),
]


def main():
    from app.founding_config import load_founding_config

    config = load_founding_config()
    configured_codes = {str(item["code"]) for item in config["skills"]}

    with SessionLocal() as session:
        skills = {
            s.code: s
            for s in session.scalars(select(Skill)).all()
            if s.deleted_at is None
        }

        applied = 0
        rich_skill_codes = {row[0] for row in TEMPLATES}

        for skill_code, code, name, xp, duration in TEMPLATES:
            if skill_code not in configured_codes or skill_code not in skills:
                continue
            template = session.scalar(
                select(ActivityTemplate).where(ActivityTemplate.code == code)
            )
            if template is None:
                template = ActivityTemplate(code=code)
                session.add(template)
            template.skill_id = skills[skill_code].id
            template.name = name
            template.base_xp = xp
            template.default_duration_minutes = duration
            template.enabled = True
            applied += 1

        for skill_code in sorted(configured_codes - rich_skill_codes):
            skill = skills.get(skill_code)
            if skill is None:
                continue
            generic = [
                (f"{skill_code}_short", "Short Session", 5, 20),
                (f"{skill_code}_normal", "Normal Session", 10, 45),
                (f"{skill_code}_long", "Long Session", 18, 90),
                (f"{skill_code}_milestone", "Significant Milestone", 25, None),
            ]
            for code, name, xp, duration in generic:
                template = session.scalar(
                    select(ActivityTemplate).where(ActivityTemplate.code == code)
                )
                if template is None:
                    template = ActivityTemplate(code=code)
                    session.add(template)
                template.skill_id = skill.id
                template.name = name
                template.base_xp = xp
                template.default_duration_minutes = duration
                template.enabled = True
                applied += 1

        session.commit()
        print(f"Activity templates applied: {applied}")


if __name__ == "__main__":
    main()
