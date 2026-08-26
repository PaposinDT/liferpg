#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$APP")/backups"
if [[ -f "$APP/.env" ]]; then
  configured="$(grep -E '^LIFERPG_BACKUP_ROOT=' "$APP/.env" | tail -1 | cut -d= -f2- || true)"
  [[ -n "$configured" ]] && ROOT="$configured"
fi
SAFETY="$ROOT/pre_restore"

usage() {
  echo "Usage:"
  echo "  $0 --verify backup.tar.gz"
  echo "  $0 --restore backup.tar.gz"
  exit 1
}

[[ $# -eq 2 ]] || usage
MODE="$1"
[[ "$MODE" == "--verify" || "$MODE" == "--restore" ]] || usage
ARCHIVE="$(realpath "$2")"
[[ -f "$ARCHIVE" ]] || { echo "Backup not found: $ARCHIVE"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=== VERIFY FULL BACKUP ==="
tar -xzf "$ARCHIVE" -C "$TMP"
DB="$TMP/database.dump"
SOURCE="$TMP/source.tar.gz"
META="$TMP/metadata.json"
[[ -s "$DB" ]] || { echo "database.dump missing"; exit 1; }
[[ -s "$SOURCE" ]] || { echo "source.tar.gz missing"; exit 1; }

cd "$APP"
docker compose exec -T postgres pg_restore -l < "$DB" >/dev/null
tar -tzf "$SOURCE" >/dev/null

CONTENTS="$(tar -tzf "$SOURCE")"
for required in \
  "backend/" "frontend/" "scripts/" "installer/" "config/" \
  "scripts/backup.sh" "scripts/restore_db.sh" "scripts/restore_full.sh" \
  "compose.yaml" "install.sh" "README.md" "VERSION" ".env.example"; do
  grep -qxF "$required" <<< "$CONTENTS" || {
    echo "Missing component: $required"
    exit 1
  }
done

echo "Database archive valid."
echo "Source archive valid."
[[ -f "$META" ]] && { echo "Metadata:"; cat "$META"; }
echo "Required components present."

if [[ "$MODE" == "--verify" ]]; then
  echo
  echo "FULL BACKUP VERIFY: PASS"
  exit 0
fi

[[ -f "$APP/.env" ]] || {
  echo "Refusing full restore because $APP/.env is missing."
  echo "Full backups intentionally do not contain secrets. Recreate .env first."
  exit 1
}

mkdir -p "$SAFETY"
STAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_DB="$SAFETY/full-pre-restore-$STAMP.dump"
SAFE_SRC="$SAFETY/full-pre-restore-$STAMP.tar.gz"

echo
echo "=== SAFETY SNAPSHOT ==="
docker compose exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$SAFE_DB"
test -s "$SAFE_DB"

tar -czf "$SAFE_SRC" \
  --exclude='.env' --exclude='.git' --exclude='frontend/node_modules' --exclude='frontend/dist' \
  backend frontend scripts installer systemd config docs .github \
  compose.yaml install.sh update.sh uninstall.sh README.md CHANGELOG.md \
  CONTRIBUTING.md SECURITY.md LICENSE .gitignore .gitattributes .editorconfig Makefile VERSION .env.example

echo "Safety DB: $SAFE_DB"
echo "Safety source: $SAFE_SRC"

echo
echo "=== STOP APPLICATION ==="
docker compose stop bot scheduler api dashboard

echo
echo "=== RESTORE SOURCE ==="
STAGE="$TMP/source"
mkdir -p "$STAGE"
tar -xzf "$SOURCE" -C "$STAGE"

# Preserve runtime secrets. Everything else returns to the archived source state.
for dir in backend frontend scripts installer systemd config docs .github; do
  rm -rf "$APP/$dir"
  [[ -e "$STAGE/$dir" ]] && cp -a "$STAGE/$dir" "$APP/"
done
for file in compose.yaml install.sh update.sh uninstall.sh README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md LICENSE .gitignore .gitattributes .editorconfig Makefile VERSION .env.example; do
  [[ -e "$STAGE/$file" ]] && cp -a "$STAGE/$file" "$APP/$file"
done

cd "$APP"
docker compose config >/dev/null

echo
echo "=== RESTORE DATABASE ==="
docker compose exec -T postgres \
  sh -lc 'pg_restore --exit-on-error --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$DB"

echo
echo "=== REBUILD APPLICATION ==="
docker compose up -d --build

AI_ENABLED="$(grep -E '^LIFERPG_OLLAMA_ENABLED=' .env | tail -1 | cut -d= -f2- || echo false)"
if [[ "$AI_ENABLED" == "true" ]]; then
  MODEL="$(grep -E '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2-)"
  MODEL="${MODEL#\"}"; MODEL="${MODEL%\"}"
  echo
  echo "=== RESTORE LOCAL AI ==="
  docker compose up -d ollama
  for _ in {1..30}; do
    docker compose exec -T ollama ollama list >/dev/null 2>&1 && break
    sleep 2
  done
  docker compose exec -T ollama ollama pull "$MODEL"
fi

ready=0
for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" -eq 1 ]] || { docker compose logs --tail=100 api bot scheduler; exit 1; }
curl -fsS http://127.0.0.1:8000/health/ready
echo
curl -fsS http://127.0.0.1:8080/api/dashboard/overview >/dev/null

# Keep the five newest full-restore safety pairs of each type.
for pattern in 'full-pre-restore-*.dump' 'full-pre-restore-*.tar.gz'; do
  find "$SAFETY" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' \
    | sort -rn | tail -n +6 | cut -d' ' -f2- | xargs -r rm -f
done

echo
echo "FULL RESTORE COMPLETE"
echo "Safety DB: $SAFE_DB"
echo "Safety source: $SAFE_SRC"
