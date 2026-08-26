#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$APP")/backups"
if [[ -f "$APP/.env" ]]; then
  configured="$(grep -E '^LIFERPG_BACKUP_ROOT=' "$APP/.env" | tail -1 | cut -d= -f2- || true)"
  [[ -n "$configured" ]] && ROOT="$configured"
fi
SAFETY="$ROOT/pre_restore"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/backup.dump"
  exit 1
fi

DUMP="$(realpath "$1")"
[[ -f "$DUMP" ]] || { echo "Backup not found: $DUMP"; exit 1; }

cd "$APP"
mkdir -p "$SAFETY"

echo "=== VERIFY ARCHIVE ==="
docker compose exec -T postgres pg_restore -l < "$DUMP" >/dev/null
echo "Archive valid."

STAMP="$(date +%Y%m%d_%H%M%S)"
PRE="$SAFETY/pre-restore-$STAMP.dump"

echo
echo "=== STOP APPLICATION ==="
docker compose stop bot scheduler api dashboard

echo
echo "=== SAFETY BACKUP ==="
docker compose exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$PRE"
test -s "$PRE"
docker compose exec -T postgres pg_restore -l < "$PRE" >/dev/null
echo "Safety backup: $PRE"

echo
echo "=== RESTORE DATABASE ==="
if docker compose exec -T postgres \
  sh -lc 'pg_restore --exit-on-error --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$DUMP"; then
  echo "Database restored."
else
  echo "RESTORE FAILED. Safety backup preserved: $PRE"
  docker compose up -d api bot scheduler dashboard
  exit 1
fi

echo
echo "=== START APPLICATION ==="
docker compose up -d api bot scheduler dashboard

for _ in {1..20}; do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/health/ready
echo

find "$SAFETY" -maxdepth 1 -type f -name 'pre-restore-*.dump' -printf '%T@ %p\n' \
  | sort -rn | tail -n +6 | cut -d' ' -f2- | xargs -r rm -f

echo "RESTORE COMPLETE"
