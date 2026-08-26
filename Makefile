SHELL := /usr/bin/env bash

.PHONY: help check python-check shell-check test frontend-build clean

help:
	@printf '%s\n' \
	  'make check          Run all available repository checks' \
	  'make python-check   Compile Python sources' \
	  'make shell-check    Check shell script syntax' \
	  'make test           Run backend pytest suite' \
	  'make frontend-build Install frontend dependencies and build' \
	  'make clean          Remove generated caches/build output'

python-check:
	python3 -m compileall -q backend/app backend/tests installer

shell-check:
	bash -n install.sh update.sh uninstall.sh scripts/*.sh

# Integration tests need a configured database. Unit tests can be invoked in a
# provisioned development environment with `make test`.
test:
	cd backend && pytest -q

frontend-build:
	cd frontend && npm install && npm run build

check: python-check shell-check
	@if command -v npm >/dev/null 2>&1; then \
	  cd frontend && npm install --no-audit --no-fund && npm run build; \
	else \
	  echo 'npm not installed: skipping frontend build'; \
	fi

clean:
	find backend installer -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache frontend/node_modules frontend/dist
