#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="1.0.1"
DEFAULT_APP_DIR="/srv/liferpg/app"
DEFAULT_ROOT="/srv/liferpg"
ANSWERS_FILE=""
REINSTALL=0

log() { printf '\n\033[1;32m[LifeRPG]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[LifeRPG WARNING]\033[0m %s\n' "$*" >&2; }
die() { printf '\n\033[1;31m[LifeRPG ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

on_error() {
  local line="$1"
  printf '\n\033[1;31mLife RPG installation failed at line %s.\033[0m\n' "$line" >&2
  printf 'Review /var/log/liferpg-install.log if available.\n' >&2
}
trap 'on_error $LINENO' ERR

usage() {
  cat <<EOF
Usage: sudo ./install.sh [options]

Options:
  --install-dir PATH       installation directory (default: $DEFAULT_APP_DIR)
  --answers FILE           non-interactive onboarding answers JSON
  --reinstall              allow replacing application source on an existing install
  -h, --help               show this help
EOF
}

APP_DIR="$DEFAULT_APP_DIR"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) APP_DIR="$2"; shift 2 ;;
    --answers) ANSWERS_FILE="$(realpath "$2")"; shift 2 ;;
    --reinstall) REINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "$APP_DIR" = /* ]] || die "--install-dir must be an absolute path."
[[ "$APP_DIR" != *[[:space:]]* ]] || die "--install-dir cannot contain whitespace."
case "$APP_DIR" in
  /|/srv|/opt|/home|/usr|/var) die "Refusing unsafe installation directory: $APP_DIR" ;;
esac

[[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run this installer with sudo/root."

mkdir -p /var/log
exec > >(tee -a /var/log/liferpg-install.log) 2>&1

INSTALL_USER="${SUDO_USER:-root}"
INSTALL_GROUP="$(id -gn "$INSTALL_USER" 2>/dev/null || echo root)"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
TEMP_CLONE=""

cleanup() {
  if [[ -n "$TEMP_CLONE" && -d "$TEMP_CLONE" ]]; then
    rm -rf "$TEMP_CLONE"
  fi
}
trap cleanup EXIT

log "Life RPG Installer v$VERSION"
log "Running preflight checks"

export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl git jq python3 rsync tar gzip sudo openssh-server
else
  die "Automated dependency installation currently supports Debian/Ubuntu/Raspberry Pi OS (apt)."
fi

# Locate project source. This also permits: curl install.sh | sudo bash, once LIFERPG_REPO_URL is set.
if [[ ! -f "$SOURCE_DIR/compose.yaml" || ! -d "$SOURCE_DIR/backend" ]]; then
  REPO_URL="${LIFERPG_REPO_URL:-}"
  if [[ -z "$REPO_URL" && -t 0 ]]; then
    read -r -p "Git repository URL containing Life RPG: " REPO_URL
  fi
  [[ -n "$REPO_URL" ]] || die "Project source not found. Clone the repository first or set LIFERPG_REPO_URL."
  TEMP_CLONE="$(mktemp -d)"
  git clone --depth 1 "$REPO_URL" "$TEMP_CLONE/repo"
  SOURCE_DIR="$TEMP_CLONE/repo"
fi

python3 "$SOURCE_DIR/installer/system_probe.py"

log "Installing Docker Engine if required"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  tmp_docker="$(mktemp)"
  curl -fsSL https://get.docker.com -o "$tmp_docker"
  sh "$tmp_docker"
  rm -f "$tmp_docker"
fi
systemctl enable --now docker

# Keep standard SSH available for administration over the private Tailscale IP.
if systemctl list-unit-files ssh.service >/dev/null 2>&1; then
  systemctl enable --now ssh || true
fi

groupadd -f docker
if [[ "$INSTALL_USER" != "root" ]]; then
  usermod -aG docker "$INSTALL_USER" || true
fi

ROOT_DIR="$(dirname "$APP_DIR")"
BACKUP_ROOT="$ROOT_DIR/backups"
mkdir -p "$BACKUP_ROOT" "$APP_DIR"

EXISTING_INSTALL=0
if [[ -f "$APP_DIR/.env" ]]; then
  EXISTING_INSTALL=1
  if [[ "$REINSTALL" -ne 1 ]]; then
    die "An existing Life RPG installation was found at $APP_DIR. Use --reinstall to refresh source without replacing its founding state/secrets."
  fi
  if [[ -n "$ANSWERS_FILE" ]]; then
    die "--answers cannot be combined with --reinstall. Existing founding configuration is preserved during reinstall."
  fi
  log "Existing installation detected; creating a pre-reinstall full backup"
  if [[ -x "$APP_DIR/scripts/backup.sh" ]]; then
    (cd "$APP_DIR" && ./scripts/backup.sh --full)
  else
    warn "Existing backup helper not found; source refresh will continue without an automatic pre-reinstall backup."
  fi
fi

log "Installing application source to $APP_DIR"
if [[ "$(realpath "$SOURCE_DIR")" != "$(realpath "$APP_DIR")" ]]; then
  rsync -a --delete \
    --exclude '.env' \
    --exclude 'config/founding.json' \
    --exclude 'config/install.json' \
    --exclude 'config/FOUNDING_STATE.md' \
    --exclude 'frontend/node_modules' \
    --exclude 'frontend/dist' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "$SOURCE_DIR/" "$APP_DIR/"
fi

mkdir -p "$APP_DIR/config" "$BACKUP_ROOT"/{daily,weekly,monthly,yearly,pre_restore}
chown -R "$INSTALL_USER:$INSTALL_GROUP" "$APP_DIR" "$BACKUP_ROOT"

cd "$APP_DIR"
if [[ "$EXISTING_INSTALL" -eq 0 ]]; then
  log "Running founding assessment and configuration"
  if [[ -n "$ANSWERS_FILE" ]]; then
    sudo -u "$INSTALL_USER" env LIFERPG_BACKUP_ROOT="$BACKUP_ROOT" python3 installer/onboarding.py --answers "$ANSWERS_FILE"
  else
    sudo -u "$INSTALL_USER" env LIFERPG_BACKUP_ROOT="$BACKUP_ROOT" python3 installer/onboarding.py
  fi
else
  log "Preserving existing .env and founding configuration"
  [[ -f config/founding.json && -f config/install.json && -f config/FOUNDING_STATE.md ]] || \
    die "Existing installation is missing generated config files; restore them before reinstalling."
fi
chmod 600 .env
chown "$INSTALL_USER:$INSTALL_GROUP" .env config/founding.json config/install.json config/FOUNDING_STATE.md

log "Validating generated founding/install configuration"
python3 installer/validate_config.py config/founding.json config/install.json

log "Validating Telegram bot token"
BOT_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | tail -1 | cut -d= -f2-)"
if ! curl -fsS --max-time 15 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | jq -e '.ok == true' >/dev/null; then
  die "Telegram bot token validation failed. Regenerate/check the token with BotFather and rerun the installer."
fi

AI_ENABLED="$(jq -r '.ai_enabled' config/install.json)"
AI_MODEL="$(jq -r '.ai_model' config/install.json)"
TAILSCALE_ENABLED="$(jq -r '.tailscale_enabled' config/install.json)"
BACKUP_TIME="$(jq -r '.backup_time' config/install.json)"
APP_TIMEZONE="$(jq -r '.timezone' config/install.json)"

log "Building Life RPG containers"
docker compose config >/dev/null
docker compose build

log "Starting PostgreSQL"
docker compose up -d postgres

for _ in {1..30}; do
  if docker compose exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker compose exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null

log "Applying database migrations"
docker compose run --rm api alembic -c /app/alembic.ini upgrade head

if [[ "$EXISTING_INSTALL" -eq 0 ]]; then
  log "Creating founding dataset"
  docker compose run --rm api python -m app.bootstrap
else
  log "Existing database preserved; founding bootstrap skipped"
fi

if [[ "$AI_ENABLED" == "true" ]]; then
  log "Starting local Ollama AI and downloading model: $AI_MODEL"
  docker compose up -d ollama
  for _ in {1..30}; do
    if docker compose exec -T ollama ollama list >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker compose exec -T ollama ollama pull "$AI_MODEL"
fi

log "Starting API, Telegram bot, scheduler and dashboard"
docker compose up -d api bot scheduler dashboard

log "Waiting for application health"
ready=0
for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" -eq 1 ]] || { docker compose ps; docker compose logs --tail=100 api bot scheduler; die "Application did not become healthy."; }

log "Installing automatic backup timer at $BACKUP_TIME"
sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  systemd/liferpg-backup.service.template \
  > /etc/systemd/system/liferpg-backup.service
sed \
  -e "s|__BACKUP_TIME__|$BACKUP_TIME|g" \
  -e "s|__TIMEZONE__|$APP_TIMEZONE|g" \
  systemd/liferpg-backup.timer.template \
  > /etc/systemd/system/liferpg-backup.timer
systemctl daemon-reload
systemctl enable --now liferpg-backup.timer

if [[ "$TAILSCALE_ENABLED" == "true" ]]; then
  log "Installing/configuring Tailscale private access"
  if ! command -v tailscale >/dev/null 2>&1; then
    tmp_ts="$(mktemp)"
    curl -fsSL https://tailscale.com/install.sh -o "$tmp_ts"
    sh "$tmp_ts"
    rm -f "$tmp_ts"
  fi
  systemctl enable --now tailscaled

  if ! tailscale status >/dev/null 2>&1; then
    if [[ -n "${TAILSCALE_AUTHKEY:-}" ]]; then
      tailscale up --auth-key "$TAILSCALE_AUTHKEY"
    else
      warn "Tailscale requires one external account authorization. Follow the login URL printed below."
      tailscale up
    fi
  fi

  if ! tailscale serve --bg http://127.0.0.1:8080; then
    warn "Could not configure Tailscale Serve automatically. The application is still healthy locally."
  fi
fi

log "Creating and verifying founding backup"
./scripts/backup.sh --full
LATEST_FULL="$(ls -1t "$BACKUP_ROOT/weekly"/liferpg-weekly-*.tar.gz | head -1)"
./scripts/restore_full.sh --verify "$LATEST_FULL"

log "Running final system audit"
./scripts/system_check.sh

DASHBOARD="http://127.0.0.1:8080"
if [[ "$TAILSCALE_ENABLED" == "true" ]] && command -v tailscale >/dev/null 2>&1; then
  DNS_NAME="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//')"
  if [[ -n "$DNS_NAME" ]]; then
    DASHBOARD="https://$DNS_NAME"
  fi
fi

cat <<EOF

==============================================================
 LIFE RPG INSTALLATION COMPLETE
==============================================================

Install directory : $APP_DIR
Dashboard         : $DASHBOARD
Telegram          : configured and running
Scheduler         : running
Backups           : enabled at $BACKUP_TIME
Local AI          : $AI_ENABLED
Tailscale         : $TAILSCALE_ENABLED

Founding state    : $APP_DIR/config/FOUNDING_STATE.md
System audit      : sudo $APP_DIR/scripts/system_check.sh
Manual backup     : sudo $APP_DIR/scripts/backup.sh --full

If your login user was newly added to the docker group, log out/in
before running Docker commands without sudo.
==============================================================
EOF
