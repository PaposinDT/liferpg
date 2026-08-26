# Life RPG

[![CI](https://github.com/PaposinDT/liferpg/actions/workflows/ci.yml/badge.svg)](https://github.com/PaposinDT/liferpg/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/PaposinDT/liferpg)](https://github.com/PaposinDT/liferpg/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Life RPG is a self-hosted, single-user personal progression system that turns real activity into a persistent RPG character.

It combines a deterministic game engine, PostgreSQL, a Telegram operational interface, a read-only web dashboard, scheduled daily logic, local AI-assisted activity parsing, private remote access through Tailscale, and tested backup/recovery tooling.

The repository includes a guided installer. On a fresh Debian/Ubuntu/Raspberry Pi OS machine, the installer asks the user about their character, current skills, priorities, goals, weekly commitments, daily habits, nutrition/bodyweight tracking, Telegram, local AI, remote access, and backup schedule. It then builds the installation automatically.

> **Status:** v1.0.1. The application is intentionally single-user per installation.

## What it does

- Tracks a character, character XP, titles and RPG-style progression.
- Tracks skills from level 1 to 150 with versioned XP curves.
- Uses hard checkpoint gates: excess XP is banked until the user clears the real-world checkpoint.
- Logs activities from Telegram buttons or natural-language messages.
- Keeps the deterministic game engine authoritative; AI never writes XP directly.
- Tracks Main/Weekly quests, daily habits, nutrition and bodyweight.
- Produces achievements, timeline events and reports.
- Runs a persistent scheduler for daily generation, closing and check-ins.
- Serves a read-only React dashboard through Caddy.
- Optionally runs Ollama locally for activity parsing.
- Optionally configures Tailscale Serve for private dashboard access from anywhere.
- Creates automatic PostgreSQL/full/JSON/yearly backups and includes verify/restore tooling.

## Architecture

```text
Telegram ───────────────┐
                       │
Tailscale / browser ───┼──> Raspberry Pi / Linux host
                       │
                       ├── Docker Compose
                       │   ├── PostgreSQL
                       │   ├── FastAPI
                       │   ├── Telegram bot
                       │   ├── scheduler
                       │   ├── React + Caddy dashboard
                       │   └── Ollama (optional profile)
                       │
                       └── systemd backup timer
```

The API and dashboard bind to `127.0.0.1` by default. Tailscale Serve exposes the dashboard only to the user's tailnet. PostgreSQL is not published to the host network.

## Supported hosts

The automated installer targets:

- Raspberry Pi OS / Debian / Ubuntu with `apt`
- `arm64` / `aarch64` and `amd64` / `x86_64`
- systemd-based Linux
- at least 4 GB free disk space

Recommended:

- 4 GB RAM when using local AI
- 8+ GB free disk space for comfortable Docker/model growth
- stable internet for first installation

Life RPG can run without local AI on smaller systems.

## Quick start

### 1. Prepare Telegram

Create a bot with `@BotFather` and obtain:

- the bot token
- your numeric Telegram user ID

The installer validates and stores them only in the local `.env` file.

### 2. Install

**Fastest option, one command:**

```bash
curl -fsSL https://raw.githubusercontent.com/PaposinDT/liferpg/main/bootstrap.sh | sudo bash
```

The bootstrap downloads the current repository and reconnects the guided installer to your terminal, so the onboarding wizard remains interactive even though the bootstrap itself is piped through `curl`.

**Inspect-first / traditional option:**

```bash
git clone https://github.com/PaposinDT/liferpg.git
cd liferpg
sudo ./install.sh
```

Running remote shell code as root is security-sensitive. If you do not want to pipe a script directly into `sudo bash`, use the clone/install method above and inspect `bootstrap.sh` / `install.sh` first.

The wizard handles the rest.

For unattended/test installs, use an answers file:

```bash
sudo ./install.sh --answers installer/answers.example.json
```

Do not use the example Telegram credentials for a real deployment.

### 3. Use Life RPG

- **Telegram:** use the bot from anywhere the host has internet access.
- **Dashboard:** if Tailscale was enabled, open the `https://<machine>.<tailnet>.ts.net` address shown by the installer.
- **SSH administration:** connect to the host's Tailscale IP/DNS name with normal SSH.

## Installer workflow

The installer performs, in order:

1. Linux/system/resource preflight.
2. Required OS package installation.
3. Docker Engine + Compose installation if needed.
4. SSH service setup for administration.
5. Interactive founding assessment or answers-file import.
6. Secret/config generation.
7. PostgreSQL startup.
8. Alembic migrations.
9. Founding dataset generation.
10. Optional local Ollama startup/model pull.
11. API, bot, scheduler and dashboard startup.
12. Automatic systemd backup timer setup.
13. Optional Tailscale setup and private Serve configuration.
14. Founding full backup creation and non-destructive verification.
15. Full system audit.

See [docs/INSTALL.md](docs/INSTALL.md), [docs/ONBOARDING.md](docs/ONBOARDING.md), and [docs/OPERATIONS.md](docs/OPERATIONS.md). Existing deployments are described in [docs/EXISTING_INSTALL.md](docs/EXISTING_INSTALL.md).

## Security model

- `.env` is generated with mode `0600` and is ignored by Git.
- Telegram access is restricted to the configured numeric user ID.
- PostgreSQL is internal to Docker Compose.
- API/dashboard default to loopback only.
- Tailscale Serve is tailnet-only; the installer does not enable public Funnel.
- Local AI is isolated inside the Compose network and is not an authority over XP/state.
- Backups deliberately exclude `.env`; secrets must be stored separately for disaster recovery.

If a Telegram token is ever exposed, revoke/regenerate it with BotFather immediately.

See [SECURITY.md](SECURITY.md).

## Backup policy

Default policy:

| Tier | Content | Retention |
| --- | --- | ---: |
| Daily | PostgreSQL custom-format dump | 14 |
| Weekly | DB + application/config source archive | 8 |
| Monthly | portable JSON export | 12 |
| Yearly | full snapshot | permanent |

The installer creates a systemd timer at the time selected during onboarding.

Useful commands:

```bash
sudo /srv/liferpg/app/scripts/backup.sh --full
sudo /srv/liferpg/app/scripts/system_check.sh
sudo /srv/liferpg/app/scripts/restore_full.sh --verify /path/to/backup.tar.gz
```

Full restore and database restore procedures are documented in [docs/BACKUP_RECOVERY.md](docs/BACKUP_RECOVERY.md). For whole-device disaster recovery, see [docs/SD_CARD_IMAGE.md](docs/SD_CARD_IMAGE.md).

## Updating

If installed from a Git clone:

```bash
cd /srv/liferpg/app
sudo ./update.sh
```

The updater creates and verifies a full pre-update backup, fast-forwards Git, applies migrations, rebuilds services, and runs the system audit.

See [docs/UPDATING.md](docs/UPDATING.md).

## Repository layout

```text
backend/                 FastAPI, bot, scheduler, game engine, migrations
frontend/                React/Vite dashboard served by Caddy
installer/               onboarding wizard, catalog, system probe
config/                  generated founding/install state (ignored) + examples
scripts/                 backup, restore and health/audit utilities
systemd/                 backup service/timer templates
docs/                    operator/developer documentation
.github/                 CI and contribution templates
compose.yaml              production Compose stack
install.sh                full guided installer
update.sh                 safe updater
uninstall.sh              controlled uninstall helper
```

## Development and QA

```bash
make check
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and [docs/QA.md](docs/QA.md). GitHub CI includes PostgreSQL bootstrap/game-engine integration and frontend build checks.

## Important design boundaries

- One installation = one user/character.
- Character/skill state is server-side and persistent.
- The game engine, not AI, owns XP, checkpoint and undo logic.
- Dashboard endpoints are read-only.
- Initial skill levels are self-assessment inputs, not objective certifications.
- The current database retains legacy column names such as `russian_state` for schema compatibility; runtime behavior is generic and can use any configured daily focus skill.

## Support Life RPG

Life RPG is free and open source.

If you enjoy the project and want to support its development, you can contribute here:

[Support Life RPG on Revolut](https://revolut.me/paposindt)

Support is completely optional. Life RPG will remain free and open source.

## License

MIT. See [LICENSE](LICENSE).
