# Updating

The safe updater assumes `/srv/liferpg/app` is a Git working tree.

```bash
cd /srv/liferpg/app
sudo ./update.sh
```

The updater:

1. creates a full pre-update backup
2. verifies the backup
3. refuses to continue with tracked local modifications
4. fetches and fast-forwards Git
5. rebuilds containers
6. applies Alembic migrations
7. restarts the stack
8. ensures the configured Ollama model exists when AI is enabled
9. runs the final system audit

Generated local files (`.env`, founding/install JSON) are Git-ignored and remain in place.

For release archives without `.git`, update by installing a newer release only after taking/verifying a full backup.
