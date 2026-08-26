# Development

## Backend

Requirements are in `backend/requirements.txt`.

Compile check:

```bash
python3 -m compileall -q backend/app installer
```

Tests:

```bash
cd backend
pytest -q
```

Integration tests expect a configured database/founding state. CI provisions the demo configuration before running them.

## Frontend

```bash
cd frontend
npm install
npm run build
```

## Shell scripts

```bash
bash -n install.sh update.sh uninstall.sh scripts/*.sh
```

## Docker Compose

With a generated local `.env`:

```bash
docker compose config
```

## Database migrations

Create migrations from `backend` configuration and always test upgrade against a copy of real data before release. Production installs apply:

```bash
docker compose run --rm api alembic -c /app/alembic.ini upgrade head
```

## Generic configuration

Do not add a personal character name, timezone, Telegram ID, goal or secret to application code. User-specific state belongs in generated `config/founding.json`, `config/install.json` and `.env`.
