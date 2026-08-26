# Publishing to GitHub

This source tree is designed to be committed as-is. Generated deployment files and secrets are already excluded by `.gitignore`.

## Create a new repository

Create an empty GitHub repository without adding a README/license from the GitHub UI, then from the extracted Life RPG source directory:

```bash
git init
git branch -M main
git add .
git commit -m "Life RPG v1.0.0"
git remote add origin https://github.com/YOUR-USER/liferpg.git
git push -u origin main
git tag -a v1.0.0 -m "Life RPG v1.0.0"
git push origin v1.0.0
```

Before `git add`, verify that `.env` does not exist in the repository root:

```bash
test ! -f .env && echo "No local secrets present"
git status --short
```

## Recommended GitHub settings

- Enable branch protection for `main` once CI passes.
- Require the CI workflow before merging pull requests.
- Enable private vulnerability reporting if available.
- Do not upload real database dumps, `.env`, founding configs containing private information, Tailscale keys or Telegram tokens to issues/releases.

## Release asset

Use the packaging helper from a clean source tree:

```bash
./scripts/package_release.sh
```

It creates ZIP and tar.gz source archives under `release/` and performs a secret/scratch-file guard before packaging.
