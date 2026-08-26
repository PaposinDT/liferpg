#!/usr/bin/env bash
set -Eeuo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP"
VERSION="$(cat VERSION)"
OUT="$APP/release"

for forbidden in .env config/founding.json config/install.json config/FOUNDING_STATE.md; do
  if [[ -e "$forbidden" ]]; then
    echo "Refusing to package: deployment-specific file exists: $forbidden"
    echo "Move/remove it from this source checkout first."
    exit 1
  fi
done

python3 -m compileall -q backend/app backend/tests installer
bash -n bootstrap.sh install.sh update.sh uninstall.sh scripts/*.sh
python3 installer/validate_config.py config/founding.example.json config/install.example.json >/dev/null

rm -rf "$OUT"
mkdir -p "$OUT"

export LIFERPG_PACKAGE_ROOT="$APP"
export LIFERPG_PACKAGE_OUT="$OUT"
export LIFERPG_PACKAGE_VERSION="$VERSION"
python3 - <<'PY'
from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path

root = Path(os.environ["LIFERPG_PACKAGE_ROOT"])
out = Path(os.environ["LIFERPG_PACKAGE_OUT"])
version = os.environ["LIFERPG_PACKAGE_VERSION"]
name = f"liferpg-v{version}"

skip_dirs = {
    ".git", "release", "node_modules", "dist", "__pycache__", ".pytest_cache", ".venv", "venv"
}
skip_files = {
    ".env", "config/founding.json", "config/install.json", "config/FOUNDING_STATE.md"
}


def files():
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if rel.as_posix() in skip_files:
            continue
        if path.is_file() and not path.name.endswith((".pyc", ".bak")) and ".bak." not in path.name:
            yield path, rel

zip_path = out / f"{name}.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for path, rel in files():
        zf.write(path, Path(name) / rel)

tar_path = out / f"{name}.tar.gz"
with tarfile.open(tar_path, "w:gz") as tf:
    for path, rel in files():
        tf.add(path, arcname=str(Path(name) / rel), recursive=False)

print(zip_path)
print(tar_path)
PY

# Guard against accidentally shipping common credential formats outside the allowed examples.
if grep -RIE --exclude-dir=.git --exclude-dir=release --exclude-dir=node_modules \
  --exclude='answers.example.json' --exclude='.env.example' \
  'tskey-(auth|client)-[A-Za-z0-9_-]{8,}|[0-9]{6,12}:[A-Za-z0-9_-]{30,}' . >/tmp/liferpg-package-secret-scan.txt; then
  echo "Refusing to package: possible credential material detected:"
  cat /tmp/liferpg-package-secret-scan.txt
  exit 1
fi

# Verify that archives do not contain deployment-only files.
python3 - <<'PYVERIFY'
from pathlib import Path
import tarfile, zipfile
root = Path("release")
for path in root.glob("liferpg-v*.zip"):
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        bad = [n for n in names if n.endswith('/.env') or '/config/founding.json' in n or '/config/install.json' in n or '/config/FOUNDING_STATE.md' in n]
        if bad:
            raise SystemExit(f"Forbidden paths in {path}: {bad}")
for path in root.glob("liferpg-v*.tar.gz"):
    with tarfile.open(path) as tf:
        names = tf.getnames()
        bad = [n for n in names if n.endswith('/.env') or '/config/founding.json' in n or '/config/install.json' in n or '/config/FOUNDING_STATE.md' in n]
        if bad:
            raise SystemExit(f"Forbidden paths in {path}: {bad}")
print("Archive privacy guard: PASS")
PYVERIFY

( cd "$OUT" && sha256sum liferpg-v*.zip liferpg-v*.tar.gz > SHA256SUMS )
echo "Release package checksums:"
cat "$OUT/SHA256SUMS"
