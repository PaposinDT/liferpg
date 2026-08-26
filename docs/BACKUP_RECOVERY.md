# Backup & Recovery

## Automatic policy

The installer creates a systemd timer using the onboarding-selected local clock time.

The backup script supports:

- daily PostgreSQL custom-format dump
- weekly full archive
- monthly JSON export
- yearly full archive

Default retention is 14 daily, 8 weekly and 12 monthly files. Yearly archives are permanent unless manually removed.

## Full backup contents

A weekly/yearly archive contains:

```text
database.dump
source.tar.gz
metadata.json
```

`source.tar.gz` includes application source, generated non-secret configuration and recovery scripts. It deliberately excludes `.env` and `.git`.

## Create a backup now

```bash
cd /srv/liferpg/app
sudo ./scripts/backup.sh --full
```

## Verify without changing the system

```bash
sudo ./scripts/restore_full.sh --verify /srv/liferpg/backups/weekly/liferpg-weekly-YYYYMMDD_HHMMSS.tar.gz
```

`--verify` exits before any service stop, source replacement or database restore.

## Restore database only

```bash
sudo ./scripts/restore_db.sh /path/to/liferpg-YYYYMMDD_HHMMSS.dump
```

The script first creates a pre-restore safety database dump, stops application writers, restores with `pg_restore --clean --if-exists`, starts services and checks API health.

## Restore a full backup

A full restore requires the existing `.env` because backup archives intentionally omit secrets.

```bash
sudo ./scripts/restore_full.sh --restore /path/to/liferpg-weekly-YYYYMMDD_HHMMSS.tar.gz
```

Before changing the live installation the script creates safety database/source snapshots in `backups/pre_restore`.

## Disaster recovery after total disk loss

You need two things:

1. a full Life RPG backup archive
2. the deployment secrets (`.env`) or the ability to regenerate them

Recommended workflow on a new Linux host:

1. install/clone the matching Life RPG release
2. create/recover `.env`
3. start PostgreSQL
4. place the full archive on the host
5. run full restore
6. run `scripts/system_check.sh`

## Off-device backups

Backups stored only on the same SD card/disk do not protect against disk failure. Regularly copy `/srv/liferpg/backups` to another physical device, NAS or encrypted remote storage. Never put unencrypted `.env` in a public/shared backup location.

## Convenience helpers

Copy only the backup tree to an off-device destination:

```bash
sudo ./scripts/copy_backups.sh /media/usb/liferpg-backups
```

Export `.env` separately to a protected destination:

```bash
sudo ./scripts/export_secrets.sh /media/secure/liferpg.env
```

The second file contains credentials. Treat it as a secret and do not commit or upload it publicly.

## Whole-device images

For Raspberry Pi deployments, an occasional powered-down full microSD image can capture the OS, Docker volumes, secrets and all Life RPG state in one block-level snapshot. This complements rather than replaces the automatic Life RPG backup tiers. See [SD_CARD_IMAGE.md](SD_CARD_IMAGE.md).
