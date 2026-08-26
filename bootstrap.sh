#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${LIFERPG_REPO_URL:-https://github.com/PaposinDT/liferpg.git}"
REF="${LIFERPG_REF:-main}"

log() { printf '\n\033[1;32m[LifeRPG Bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[LifeRPG Bootstrap WARNING]\033[0m %s\n' "$*" >&2; }
die() { printf '\n\033[1;31m[LifeRPG Bootstrap ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run with sudo/root. Example: curl -fsSL https://raw.githubusercontent.com/PaposinDT/liferpg/main/bootstrap.sh | sudo bash"

if ! command -v apt-get >/dev/null 2>&1; then
  die "The one-line bootstrap currently supports Debian, Ubuntu and Raspberry Pi OS hosts with apt."
fi

if [[ ! -r /dev/tty ]]; then
  die "No interactive terminal is available. Download bootstrap.sh first and run: sudo bash bootstrap.sh"
fi

export DEBIAN_FRONTEND=noninteractive

if ! command -v git >/dev/null 2>&1; then
  log "Installing Git"
  apt-get update -y
  apt-get install -y ca-certificates git
fi

TMP="$(mktemp -d /tmp/liferpg-bootstrap.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

log "Downloading Life RPG from $REPO_URL ($REF)"
if ! git clone --depth 1 --branch "$REF" "$REPO_URL" "$TMP/repo"; then
  die "Could not clone $REPO_URL at ref '$REF'. Check internet access and that the repository/ref exists."
fi

[[ -f "$TMP/repo/install.sh" ]] || die "install.sh is missing from the downloaded repository."
[[ -f "$TMP/repo/compose.yaml" ]] || die "compose.yaml is missing from the downloaded repository."
[[ -d "$TMP/repo/backend" ]] || die "backend/ is missing from the downloaded repository."
[[ -d "$TMP/repo/installer" ]] || die "installer/ is missing from the downloaded repository."

chmod +x "$TMP/repo/install.sh"

log "Starting guided Life RPG installation"
warn "The installer will ask for your Telegram bot token, user ID, character setup, goals and optional Tailscale/AI settings."

# curl | sudo bash consumes stdin, so explicitly reconnect the guided installer to the user's terminal.
"$TMP/repo/install.sh" "$@" </dev/tty

log "Bootstrap complete"
