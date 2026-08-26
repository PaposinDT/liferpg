# Contributing

Contributions are welcome.

## Development principles

Life RPG deliberately separates interpretation from authority:

- AI may interpret user input.
- Deterministic application code validates it.
- The game engine owns XP, levels, checkpoints and undo.
- Schema changes use Alembic migrations.
- The dashboard remains read-only unless a future design explicitly changes that boundary.
- Existing user history must be preserved; do not solve migration problems by deleting live data.

## Local checks

Before opening a pull request:

```bash
make check
```

At minimum this runs Python compilation, shell syntax checks, pytest and frontend build when the required runtimes are installed.

## Pull requests

Keep changes focused. Include:

- what changed
- why it changed
- database migration implications
- installer/update implications
- tests performed
- screenshots for meaningful dashboard UI changes

Do not commit `.env`, generated `config/founding.json`, `config/install.json`, tokens, passwords or private Tailscale information.
