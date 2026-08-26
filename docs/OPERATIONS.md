# Daily Operations

After installation, normal use does not require an open shell.

## Telegram

The Telegram bot is the primary write interface. It exposes Today, Add, Quests, Character, Progress and Game Master flows.

Natural-language activity logging follows this authority chain:

```text
user text -> deterministic hints -> optional local AI -> validation -> preview -> user confirmation -> game engine
```

The game engine creates the activity and XP transactions only after confirmation.

## Dashboard

The web dashboard is read-only and is intended for overview/analysis rather than data entry. Its sections include Command, Character, Achievements, Skills, Quests, Timeline and Reports.

## Scheduler

Default seeded jobs are:

```text
00:05 generate_today
03:00 close_previous_day
21:00 daily_checkin
```

Times are interpreted in the configured Life RPG timezone.

## Manual administration

```bash
cd /srv/liferpg/app
sudo docker compose ps
sudo ./scripts/system_check.sh
sudo ./scripts/backup.sh --full
```

## Service restart

```bash
sudo docker compose restart api bot scheduler dashboard
```

PostgreSQL normally does not need to be restarted for application code changes.
