# Existing installation layout

A default installed Life RPG host uses:

```text
/srv/liferpg/
├── app/                         application repository/runtime source
│   ├── backend/                 API, game engine, Telegram bot, scheduler
│   ├── frontend/                React/Vite dashboard + Caddy config
│   ├── installer/               onboarding/provisioning tools
│   ├── config/                  generated founding/install configuration
│   ├── scripts/                 backup/restore/audit helpers
│   ├── systemd/                 timer templates
│   ├── compose.yaml             Docker Compose stack
│   └── .env                     local secrets, mode 0600
└── backups/
    ├── daily/                   PostgreSQL dumps
    ├── weekly/                  full application + DB archives
    ├── monthly/                 portable JSON exports
    ├── yearly/                  permanent annual archives
    └── pre_restore/             safety snapshots made before restores
```

Docker stores PostgreSQL and optional Ollama data in Docker-managed volumes, not directly inside `app/`.

Normal daily use is through Telegram and the read-only dashboard. The shell is only needed for administration, updates, backup recovery, troubleshooting or development.
