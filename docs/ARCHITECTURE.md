# Architecture

## Components

### PostgreSQL
Persistent source of truth for character, skills, progression, XP transactions, activities, quests, habits, snapshots, streaks, scheduler state, achievements, timeline and reports.

### FastAPI
Provides health endpoints and read-only dashboard endpoints. The application service layer reads/writes PostgreSQL through SQLAlchemy.

### Game engine
`backend/app/game_engine.py` is authoritative for activity XP, visible skill progression, checkpoint banking, character XP and safe undo behavior.

### Telegram bot
The operational interface. Users log activity, inspect Today/Quests/Character/Progress, use the deterministic GM and manage day-state actions.

### AI parser
`backend/app/ai_service.py` performs deterministic parsing first and optionally asks Ollama for structured interpretation. The result is validated against actual configured skills/activity templates before the user confirms it.

### Scheduler
The scheduler stores job definitions/runs in PostgreSQL and performs daily generation, previous-day close and check-in behavior in the configured timezone.

### Dashboard
React + TypeScript + Vite built into a Caddy runtime container. Caddy proxies `/api/*` to FastAPI and serves the SPA. The dashboard is read-only.

### Tailscale
Optional private overlay network. Tailscale Serve maps the machine's private HTTPS tailnet URL to `127.0.0.1:8080`. Public Funnel is not configured.

## Trust boundaries

```text
Human input
   |
Telegram UI / natural language
   |
parser / local AI
   |
validation + confirmation
   |
DETERMINISTIC GAME ENGINE
   |
PostgreSQL
```

AI is deliberately outside the authority boundary.

## Data compatibility

The v1 schema evolved from the original founding deployment. A few column names remain legacy-specific for migration compatibility, notably the daily snapshot `russian_state` column. Generic runtime services treat it as the configured focus-habit state. Renaming the physical column is unnecessary for v1 behavior and would add migration risk without user benefit.

## Network model

```text
Host
├── 127.0.0.1:8000 -> API
├── 127.0.0.1:8080 -> dashboard
├── sshd            -> administration
└── Tailscale       -> private remote access

Docker network
├── postgres:5432
├── api:8000
├── bot
├── scheduler
├── dashboard:80
└── ollama:11434 (optional)
```
