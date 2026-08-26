#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP"

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run with sudo/root."; exit 1; }
[[ -f .env ]] || { echo "No installed .env found."; exit 1; }

echo "=== PRE-UPDATE BACKUP ==="
./scripts/backup.sh --full
LATEST="$(ls -1t "$(dirname "$APP")/backups/weekly"/liferpg-weekly-*.tar.gz 2>/dev/null | head -1 || true)"
if [[ -n "$LATEST" ]]; then
  ./scripts/restore_full.sh --verify "$LATEST"
fi

if [[ -d .git ]]; then
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Tracked files have local changes. Commit/stash them before updating."
    exit 1
  fi
  echo "=== GIT UPDATE ==="
  git fetch --tags --prune
  git pull --ff-only
else
  echo "This installation is not a Git checkout. Replace source files from a release, then rerun update.sh."
  exit 1
fi

echo "=== BUILD ==="
docker compose build

echo "=== MIGRATIONS ==="
docker compose up -d postgres
docker compose run --rm api alembic -c /app/alembic.ini upgrade head

echo "=== RESTART ==="
docker compose up -d

AI_ENABLED="$(grep -E '^LIFERPG_OLLAMA_ENABLED=' .env | tail -1 | cut -d= -f2- || echo false)"
if [[ "$AI_ENABLED" == "true" ]]; then
  MODEL="$(grep -E '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2-)"
  MODEL="${MODEL#\"}"; MODEL="${MODEL%\"}"
  docker compose up -d ollama
  docker compose exec -T ollama ollama pull "$MODEL"
fi

for _ in {1..30}; do
  curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1 && break
  sleep 2
done
./scripts/system_check.sh

echo "UPDATE COMPLETE"
