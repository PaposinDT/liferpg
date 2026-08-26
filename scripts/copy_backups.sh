#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$APP")/backups"
if [[ -f "$APP/.env" ]]; then
  configured="$(grep -E '^LIFERPG_BACKUP_ROOT=' "$APP/.env" | tail -1 | cut -d= -f2- || true)"
  configured="${configured#\"}"; configured="${configured%\"}"
  [[ -n "$configured" ]] && ROOT="$configured"
fi

usage() {
  echo "Usage: $0 /mounted/off-device/destination"
  echo "Copies the backup tree only; .env/secrets are not included."
  exit 1
}

[[ $# -eq 1 ]] || usage
DEST="$1"
[[ -d "$ROOT" ]] || { echo "Backup root not found: $ROOT"; exit 1; }
mkdir -p "$DEST"
rsync -a "$ROOT/" "$DEST/"
echo "Backup mirror complete: $ROOT -> $DEST"
