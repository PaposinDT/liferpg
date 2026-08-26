# Installation Guide

## Prerequisites

Use a systemd-based Debian/Ubuntu/Raspberry Pi OS host on `arm64/aarch64` or `amd64/x86_64`.

Minimum free disk checked by the installer: 4 GB. 8 GB or more is recommended when local AI is enabled.

Before starting, create a Telegram bot with BotFather and know your numeric Telegram user ID.

## Interactive installation

### One-line bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/PaposinDT/liferpg/main/bootstrap.sh | sudo bash
```

The bootstrap clones `https://github.com/PaposinDT/liferpg.git` and starts the normal guided installer. It explicitly attaches the wizard to `/dev/tty`, so interactive onboarding still works when the bootstrap is piped through `curl`.

For security-sensitive environments, inspect the source first instead of piping it directly to root.

### Clone and inspect first

```bash
git clone https://github.com/PaposinDT/liferpg.git
cd liferpg
sudo ./install.sh
```

The installer writes a log to:

```text
/var/log/liferpg-install.log
```

Default install path:

```text
/srv/liferpg/app
```

Default backup root:

```text
/srv/liferpg/backups
```

## Non-interactive installation

Copy and edit `installer/answers.example.json`, then run:

```bash
sudo ./install.sh --answers /absolute/path/to/answers.json
```

The answers file should not contain a real bot token if it will be committed to source control.

## Reinstall / source refresh

The installer refuses to overwrite an existing installation by default. To intentionally refresh application source:

```bash
sudo ./install.sh --reinstall
```

Reinstall mode creates a full backup when the existing backup helper is available, preserves `.env` and generated founding configuration, applies migrations, and skips founding reseeding. `--answers` cannot be combined with `--reinstall`.

## Generated local files

Onboarding creates:

```text
.env                         secrets/runtime environment
config/founding.json         founding character/skills/quests/habits
config/install.json          non-secret installation options
config/FOUNDING_STATE.md     human-readable founding record
```

These files are machine/user specific and are Git-ignored.

## Installation completion checks

A successful install ends only after:

- API health returns ready
- containers are running
- founding data has been seeded
- backup timer is enabled
- a full founding backup is created
- that backup passes non-destructive verification
- `scripts/system_check.sh` completes

## Ports

Default host binds:

```text
127.0.0.1:8000  FastAPI
127.0.0.1:8080  dashboard/Caddy
```

There is no host PostgreSQL port.

## Tailscale

If selected, the installer installs Tailscale and configures:

```text
https://<host>.<tailnet>.ts.net -> http://127.0.0.1:8080
```

Tailscale authentication is the only step that can require external user authorization unless `TAILSCALE_AUTHKEY` is supplied to the installer environment.

Example for automated provisioning:

```bash
sudo -E env TAILSCALE_AUTHKEY='tskey-auth-...' ./install.sh --answers /path/to/answers.json
```

Treat auth keys as secrets and follow Tailscale's expiration/reusability guidance.
