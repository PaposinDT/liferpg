# Founding & Onboarding

The onboarding wizard turns a new user's self-assessment into the initial Life RPG configuration.

## Character

The user chooses:

- character/callsign
- IANA timezone

The character level and character XP are derived from founding skill levels unless explicitly configured in the founding JSON.

## Skills

The built-in catalog contains Combat, Physical, Knowledge, Practical and Finance skills. Custom skills are supported.

Language skills use a CEFR-oriented initial assessment:

```text
A0 -> LVL 5
A1 -> LVL 30
A2 -> LVL 60
B1 -> LVL 90
B2 -> LVL 120
C1/C2 -> LVL 150
```

Other skills use a 0-10 self-rating mapped to an estimated Life RPG level, with an exact-level override.

This is a personal baseline, not an external certification.

## Priorities

Each skill receives one priority:

- MAIN
- SIDE
- MAINTENANCE
- BACKGROUND

The wizard allows at most three MAIN skills.

## Quests and weekly operations

Each active MAIN skill gets a main progression quest aimed at the next major progression target. MAIN/SIDE skills can also receive a weekly operation with minimum and stretch session counts.

If bodyweight tracking and a target are enabled, a bodyweight Main Quest is created.

## Daily systems

The user can select one active skill as the daily focus habit and choose a daily minute target.

Nutrition tracking and bodyweight tracking are independently optional.

## Telegram

The bot token and Telegram numeric user ID are required for the current single-user installation. Only the configured user ID is accepted by the bot.

## AI

Local AI is optional. If enabled, the installer starts the Ollama Compose profile and pulls the configured model. AI assists activity interpretation but never directly writes XP or bypasses game-engine validation.

## Founding freeze

Once real activity history exists, do not casually rerun the founding bootstrap. `app.bootstrap` refuses to reseed a live installation unless explicitly forced.
