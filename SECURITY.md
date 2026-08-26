# Security Policy

## Supported version

The current `1.x` release line receives security fixes.

## Reporting

Do not open a public issue containing credentials, tokens, personal exports or database dumps. Report a vulnerability privately to the repository maintainer using GitHub's private security reporting feature when enabled.

## Secret handling

Life RPG stores deployment secrets in `.env`:

- PostgreSQL password
- Telegram bot token
- Telegram numeric user ID

`.env` is Git-ignored and created with filesystem mode `0600` by the onboarding wizard.

If a Telegram token is exposed, rotate it immediately through BotFather and update `.env` before restarting the bot.

## Network exposure

Production defaults are intentionally conservative:

- PostgreSQL: Docker-internal only
- FastAPI: `127.0.0.1:8000`
- dashboard: `127.0.0.1:8080`
- Ollama: Docker-internal only
- Tailscale Serve: private tailnet exposure only

Do not publish PostgreSQL or Ollama directly to the internet. Do not use Tailscale Funnel unless you deliberately redesign authentication for public exposure.

## Backup caveat

Application backups exclude `.env` by design. A full disaster recovery therefore requires a separately protected copy of secrets or the ability to regenerate them. Store those secrets in a password manager or encrypted offline medium.
