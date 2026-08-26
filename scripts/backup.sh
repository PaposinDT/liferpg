#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_ROOT="$(dirname "$APP")/backups"
ROOT="${LIFERPG_BACKUP_ROOT:-}"
if [[ -z "$ROOT" && -f "$APP/.env" ]]; then
  ROOT="$(grep -E '^LIFERPG_BACKUP_ROOT=' "$APP/.env" | tail -1 | cut -d= -f2- || true)"
fi
ROOT="${ROOT:-$DEFAULT_ROOT}"

DAILY="$ROOT/daily"
WEEKLY="$ROOT/weekly"
MONTHLY="$ROOT/monthly"
YEARLY="$ROOT/yearly"
FORCE_FULL=0

if [[ "${1:-}" == "--full" ]]; then
  FORCE_FULL=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--full]"
  exit 1
fi

mkdir -p "$DAILY" "$WEEKLY" "$MONTHLY" "$YEARLY"
cd "$APP"

STAMP="$(date +%Y%m%d_%H%M%S)"
DOW="$(date +%u)"
DOM="$(date +%d)"
MONTH="$(date +%m)"
DUMP="$DAILY/liferpg-$STAMP.dump"

echo "=== DAILY DATABASE ==="
docker compose exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$DUMP"
test -s "$DUMP"
docker compose exec -T postgres pg_restore -l < "$DUMP" >/dev/null
echo "Created: $DUMP"

make_full_backup() {
  local dest="$1"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  cp "$DUMP" "$tmp/database.dump"

  cat > "$tmp/metadata.json" <<EOF
{
  "created_at": "$(date --iso-8601=seconds)",
  "format": 2,
  "git_commit": "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)",
  "includes_secrets": false
}
EOF

  tar -czf "$tmp/source.tar.gz" \
    --exclude='.env' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.bak' \
    --exclude='*.bak.*' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/dist' \
    backend frontend scripts installer systemd config docs .github \
    compose.yaml install.sh update.sh uninstall.sh \
    README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md LICENSE \
    .gitignore .gitattributes .editorconfig Makefile VERSION .env.example

  tar -czf "$dest" -C "$tmp" database.dump source.tar.gz metadata.json
  rm -rf "$tmp"
  trap - RETURN
  echo "Created: $dest"
}

if [[ "$DOW" == "7" || "$FORCE_FULL" -eq 1 ]]; then
  echo
  echo "=== FULL WEEKLY BACKUP ==="
  make_full_backup "$WEEKLY/liferpg-weekly-$STAMP.tar.gz"
else
  echo
  echo "Weekly backup not due."
fi

if [[ "$DOM" == "01" ]]; then
  echo
  echo "=== MONTHLY JSON ==="
  docker compose run --rm api python -m app.export_json > "$MONTHLY/liferpg-$STAMP.json"
  test -s "$MONTHLY/liferpg-$STAMP.json"
  python3 -m json.tool "$MONTHLY/liferpg-$STAMP.json" >/dev/null
else
  echo
  echo "Monthly export not due."
fi

if [[ "$DOM" == "01" && "$MONTH" == "01" ]]; then
  echo
  echo "=== YEARLY SNAPSHOT ==="
  make_full_backup "$YEARLY/liferpg-yearly-$STAMP.tar.gz"
else
  echo
  echo "Yearly snapshot not due."
fi

prune_keep() {
  local dir="$1" pattern="$2" keep="$3"
  find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' \
    | sort -rn \
    | tail -n "+$((keep + 1))" \
    | cut -d' ' -f2- \
    | xargs -r rm -f
}

prune_keep "$DAILY" '*.dump' 14
prune_keep "$WEEKLY" '*.tar.gz' 8
prune_keep "$MONTHLY" '*.json' 12

APP_OWNER="$(stat -c '%U:%G' "$APP" 2>/dev/null || echo root:root)"
chown -R "$APP_OWNER" "$ROOT" 2>/dev/null || true

echo
echo "BACKUP COMPLETE"
du -sh "$ROOT"
