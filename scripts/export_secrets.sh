#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  echo "Usage: $0 /secure/destination/liferpg.env"
  echo "Copies the local .env with mode 0600. The destination must not be public/shared."
  exit 1
}

[[ $# -eq 1 ]] || usage
[[ -f "$APP/.env" ]] || { echo "Missing $APP/.env"; exit 1; }

DEST="$1"
mkdir -p "$(dirname "$DEST")"
install -m 600 "$APP/.env" "$DEST"

echo "Secrets copied to: $DEST"
echo "Protect this file. It contains credentials and is intentionally excluded from normal backups."
