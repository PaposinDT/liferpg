# Changelog

All notable changes to Life RPG are documented here.

## [1.0.1] - 2026-08-26

### Added
- One-line `bootstrap.sh` installer bound to the official `PaposinDT/liferpg` repository.
- Repository-specific CI/release badges and Quick Start links.

### Changed
- Installation documentation now includes both one-line and inspect-first workflows.
- Release workflow safely updates an existing GitHub Release if the tag was created from the browser.

## [1.0.0] - 2026-08-25

### Added
- Deterministic skill/character XP engine with hard checkpoints, banking and safe undo.
- PostgreSQL schema and Alembic migrations.
- Telegram operational interface with natural-language activity parser.
- Dynamic founding configuration and guided onboarding wizard.
- Dynamic skill, quest, habit, weekly operation and achievement seeding.
- Local Ollama integration as an optional Docker Compose profile.
- Deterministic Game Master brief.
- Daily snapshots, streaks, bodyweight and nutrition tracking.
- Persistent scheduler and daily check-in/close jobs.
- React/Vite/Caddy read-only dashboard.
- Tailscale private dashboard access support.
- Daily/weekly/monthly/yearly backup policy and restore verification tooling.
- Automated Debian/Ubuntu/Raspberry Pi OS installer.
- Safe updater, uninstaller and system audit scripts.
- GitHub CI, documentation and contribution/security templates.
