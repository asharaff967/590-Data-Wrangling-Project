PY  := .venv/bin/python
PIP := .venv/bin/pip

AREA_ALL :=
.DEFAULT_GOAL := all

# Each area folder brings its own targets in src/<area>/area.mk, so teammates never edit the same lines.
# An area adds its offline build targets to AREA_ALL so that make all rebuilds them.
include $(wildcard src/*/area.mk)

.PHONY: all install access test freeze

# Rebuild every processed table from data/raw, then run the checks.
# Raw pulls need a WRDS login with Duo, so run each area's pull target first on a fresh checkout.
all: $(AREA_ALL) test

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# Which WRDS tables can we open, and is EDGAR reachable. Writes docs/access_report.md.
access:
	$(PY) -m src.common.check_access

test:
	$(PY) -m pytest -q

# Writes the exact versions in use so the environment is recoverable.
freeze:
	$(PIP) freeze > requirements.lock
