#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP"

echo "================================"
echo " LIFE RPG SYSTEM CHECK"
echo "================================"

echo
echo "=== CONFIG ==="
[[ -f .env ]] || { echo ".env: MISSING"; exit 1; }
[[ -f config/founding.json ]] || { echo "config/founding.json: MISSING"; exit 1; }
MODE="$(stat -c '%a' .env)"
echo ".env permissions: $MODE"
[[ "$MODE" == "600" ]] || echo "WARNING: recommended .env permissions are 600"
python3 -m json.tool config/founding.json >/dev/null
echo "Founding JSON: OK"

echo
echo "=== DOCKER ==="
docker compose ps

REQUIRED_SERVICES=(postgres api bot scheduler dashboard)
for service in "${REQUIRED_SERVICES[@]}"; do
  if ! docker compose ps --status running --services | grep -qx "$service"; then
    echo "Required service is not running: $service"
    docker compose logs --tail=80 "$service" || true
    exit 1
  fi
done
echo "Required services: OK"

echo
echo "=== API ==="
curl -fsS http://127.0.0.1:8000/health/ready
echo

echo
echo "=== DASHBOARD ==="
curl -fsS http://127.0.0.1:8080/ >/dev/null
echo "Dashboard: OK"

echo
echo "=== DASHBOARD API ==="
for route in overview character skills quests achievements timeline reports; do
  curl -fsS "http://127.0.0.1:8080/api/dashboard/$route" >/dev/null
  echo "$route: OK"
done

echo
echo "=== DATABASE STATE ==="
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "
    SELECT '\''Character: '\'' || name || '\'' | LVL '\'' || character_level || '\'' | CXP '\'' || character_xp FROM characters;
    SELECT '\''Skills: '\'' || COUNT(*) FROM skills WHERE deleted_at IS NULL;
    SELECT '\''Active quests: '\'' || COUNT(*) FROM quests WHERE status = '\''ACTIVE'\'' AND deleted_at IS NULL;
    SELECT '\''Active habits: '\'' || COUNT(*) FROM habits WHERE status = '\''ACTIVE'\'';
    SELECT '\''Achievements: '\'' || COUNT(*) FROM achievements WHERE active = true;
    SELECT '\''Unlocked: '\'' || COUNT(*) FROM achievement_unlocks;
    SELECT '\''Activities: '\'' || COUNT(*) FROM activities WHERE deleted_at IS NULL;
    SELECT '\''Timeline events: '\'' || COUNT(*) FROM timeline_events;
    SELECT '\''Alembic: '\'' || version_num FROM alembic_version;
  "'

echo
echo "=== SCHEDULER JOBS ==="
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "
    SELECT code || '\'' | '\'' || CASE WHEN enabled THEN '\''ENABLED'\'' ELSE '\''DISABLED'\'' END || '\'' | '\'' || lpad(local_hour::text,2,'\''0'\'') || '\'':'\'' || lpad(local_minute::text,2,'\''0'\'') FROM scheduled_jobs ORDER BY local_hour, local_minute;
  "'

echo
echo "=== BACKUP TIMER ==="
if systemctl list-unit-files liferpg-backup.timer >/dev/null 2>&1; then
  systemctl is-active liferpg-backup.timer
  systemctl is-enabled liferpg-backup.timer
  systemctl list-timers liferpg-backup.timer --no-pager
else
  echo "Backup timer not installed (development checkout)."
fi

BACKUP_ROOT="$(grep -E '^LIFERPG_BACKUP_ROOT=' .env | tail -1 | cut -d= -f2- || true)"
BACKUP_ROOT="${BACKUP_ROOT:-$(dirname "$APP")/backups}"
echo
echo "=== LATEST BACKUPS ==="
for dir in daily weekly; do
  echo "$dir:"
  if [[ -d "$BACKUP_ROOT/$dir" ]]; then
    find "$BACKUP_ROOT/$dir" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %kKB %f\n' | sort | tail -n 4
  else
    echo "  none"
  fi
done

echo
echo "=== LOCAL AI ==="
AI_ENABLED="$(grep -E '^LIFERPG_OLLAMA_ENABLED=' .env | tail -1 | cut -d= -f2- || echo false)"
if [[ "$AI_ENABLED" == "true" ]]; then
  docker compose ps --status running --services | grep -qx ollama || { echo "Ollama service is not running"; exit 1; }
  MODEL="$(grep -E '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2-)"
  MODEL="${MODEL#\"}"
  MODEL="${MODEL%\"}"
  docker compose exec -T ollama ollama list
  docker compose exec -T ollama ollama list | grep -F "$MODEL" >/dev/null
  echo "Required model: OK ($MODEL)"
else
  echo "Local AI: disabled by configuration"
fi

echo
echo "=== TAILSCALE ==="
if command -v tailscale >/dev/null 2>&1 && tailscale status >/dev/null 2>&1; then
  tailscale status | head -n 8
  echo
  tailscale serve status || true
else
  echo "Tailscale: not connected / disabled"
fi

echo
echo "=== STORAGE ==="
df -h "$APP"

echo
echo "=== LOG HEALTH ==="
if docker compose logs --since=10m api bot scheduler 2>&1 | grep -E 'Traceback|CRITICAL|Unhandled exception' >/tmp/liferpg-log-errors.txt; then
  cat /tmp/liferpg-log-errors.txt
  echo "WARNING: recent application errors detected"
else
  echo "No recent traceback/critical patterns detected."
fi

echo
echo "================================"
echo " SYSTEM CHECK COMPLETE"
echo "================================"
