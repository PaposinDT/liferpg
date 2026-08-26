#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP"
PURGE=0
YES=0

for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE=1 ;;
    --yes) YES=1 ;;
    -h|--help)
      echo "Usage: sudo ./uninstall.sh [--purge-data] [--yes]"
      echo "Without --purge-data, PostgreSQL/Ollama volumes and backups are kept."
      exit 0
      ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run with sudo/root."; exit 1; }

if [[ "$YES" -ne 1 ]]; then
  echo "This stops Life RPG and disables its backup timer."
  [[ "$PURGE" -eq 1 ]] && echo "WARNING: --purge-data will delete Docker volumes containing the database/model."
  read -r -p "Type UNINSTALL to continue: " answer
  [[ "$answer" == "UNINSTALL" ]] || exit 0
fi

if [[ -f .env ]]; then
  ./scripts/backup.sh --full || true
fi

systemctl disable --now liferpg-backup.timer 2>/dev/null || true
rm -f /etc/systemd/system/liferpg-backup.timer /etc/systemd/system/liferpg-backup.service
systemctl daemon-reload

if [[ "$PURGE" -eq 1 ]]; then
  docker compose down -v --remove-orphans
else
  docker compose down --remove-orphans
fi

echo "Life RPG services removed."
if [[ "$PURGE" -eq 1 ]]; then
  echo "Docker volumes were deleted. Backup files were intentionally left on disk."
else
  echo "Database/model volumes and backup files were preserved."
fi
