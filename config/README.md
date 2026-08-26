# Configuration directory

Tracked files in this directory are examples/documentation only.

The installer generates these local files:

- `founding.json`
- `install.json`
- `FOUNDING_STATE.md`

They are intentionally ignored by Git because they contain user-specific profile information. Secrets are not stored here; they are stored in the root `.env`, which is also Git-ignored.

Use `installer/validate_config.py` to validate generated configuration:

```bash
python3 installer/validate_config.py config/founding.json config/install.json
```
