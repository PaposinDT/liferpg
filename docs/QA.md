# Quality Assurance

The v1.0.0 source tree includes automated checks intended to run both before packaging and on GitHub.

## Local release checks

The release packaging workflow verifies:

- Python source compilation
- shell-script syntax
- example configuration validation
- generated onboarding configuration and `.env` permission behavior
- JSON/YAML parseability
- TSX syntax parsing
- absence of deployment-specific `.env`/founding/install files from release archives
- common credential-pattern guard outside explicit fake examples
- archive structure and SHA-256 checksums

## GitHub CI

`.github/workflows/ci.yml` additionally performs on GitHub-hosted runners:

- frontend dependency install and Vite production build
- Docker Compose configuration validation
- backend/bot/scheduler/dashboard image builds
- PostgreSQL startup
- Alembic upgrade to head
- demo founding bootstrap
- game-engine integration tests against PostgreSQL
- API health smoke test

## Release CI

Pushing a `v*` Git tag triggers `.github/workflows/release.yml`, which reruns static/frontend checks, creates ZIP/tar.gz assets, writes `SHA256SUMS`, and publishes the GitHub Release.

## Fresh-host acceptance test

Before calling a specific hardware/OS combination production-certified, perform one clean install on that platform and verify:

```bash
sudo ./install.sh
sudo /srv/liferpg/app/scripts/system_check.sh
```

The installer itself also creates and non-destructively verifies a founding full backup before reporting successful completion.
