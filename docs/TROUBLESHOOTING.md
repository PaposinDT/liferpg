# Troubleshooting

Run the audit first:

```bash
cd /srv/liferpg/app
sudo ./scripts/system_check.sh
```

## Container state

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 api bot scheduler dashboard postgres
```

## API health

```bash
curl -fsS http://127.0.0.1:8000/health/ready
```

Expected:

```json
{"status":"ready","database":"ok"}
```

## Dashboard blank page

Verify the dashboard API first:

```bash
curl -s http://127.0.0.1:8080/api/dashboard/character | python3 -m json.tool
```

Then rebuild/recreate the frontend container:

```bash
sudo docker compose build dashboard
sudo docker compose up -d --force-recreate dashboard
```

Hard-refresh the browser (`Ctrl+F5`).

## Telegram bot not responding

```bash
sudo docker compose logs bot --tail=100
```

Check that `TELEGRAM_BOT_TOKEN` is current and `TELEGRAM_USER_ID` is the correct numeric ID. If a token was leaked, rotate it with BotFather.

## Ollama unavailable

If AI is enabled:

```bash
sudo docker compose ps ollama
sudo docker compose exec -T ollama ollama list
```

Pull the configured model again if needed:

```bash
MODEL=$(grep '^OLLAMA_MODEL=' .env | cut -d= -f2- | tr -d '"')
sudo docker compose exec -T ollama ollama pull "$MODEL"
```

The deterministic activity parser continues to provide fallback behavior when local AI is unavailable.

## Backup timer

```bash
systemctl status liferpg-backup.timer --no-pager
systemctl list-timers liferpg-backup.timer --no-pager
journalctl -u liferpg-backup.service -n 100 --no-pager
```

## Tailscale

```bash
tailscale status
tailscale serve status
```

If not authenticated:

```bash
sudo tailscale up
```
