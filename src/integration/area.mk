# Integration area targets. Included by the root Makefile.
.PHONY: integration-pull integration-build

# Raw pull of the ID link tables from WRDS into data/raw/integration. Needs login and Duo.
integration-pull:
	$(PY) -m src.integration.pull_links

# Offline: build the ID crosswalk as of a date. Override with: make integration-build AS_OF=2020-01-02
AS_OF ?= 2024-06-28
integration-build:
	$(PY) -m src.integration.crosswalk --as-of $(AS_OF)

AREA_ALL += integration-build
