# A one-month starting example, not the final agreed coverage. Override explicitly.
STOCKS_START ?= 2024-06-01
STOCKS_END ?= 2024-06-30

.PHONY: stocks-pull stocks-build stocks-test
stocks-pull:
	$(PY) -m src.stocks.pull --start $(STOCKS_START) --end $(STOCKS_END)

stocks-build:
	$(PY) -m src.stocks.build --start $(STOCKS_START) --end $(STOCKS_END)

stocks-test:
	$(PY) -m pytest -q tests/stocks

AREA_ALL += stocks-build

# Explicit audit stage: reads an existing pull/build; never invokes either stage.
# Pass --data-root through STOCKS_DATA_ROOT (environment) or STOCKS_AUDIT_ROOT.
STOCKS_AUDIT_ROOT ?= $(STOCKS_DATA_ROOT)
STOCKS_AUDIT_ARGS ?=
.PHONY: stocks-history-check stocks-history-audit
stocks-history-check:
	$(PY) -m src.stocks.history_audit --data-root "$(STOCKS_AUDIT_ROOT)" --start $(STOCKS_START) --end $(STOCKS_END) --check-only

stocks-history-audit:
	$(PY) -m src.stocks.history_audit --data-root "$(STOCKS_AUDIT_ROOT)" --start $(STOCKS_START) --end $(STOCKS_END) $(STOCKS_AUDIT_ARGS)
