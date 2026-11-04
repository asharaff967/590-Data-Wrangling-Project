# Earnings area targets. Included by the root Makefile.
.PHONY: earnings-pull earnings-build earnings-edgar earnings-releases

# Raw pull from WRDS (Compustat and I/B/E/S) into data/raw/earnings. Needs login and Duo.
earnings-pull:
	$(PY) -m src.earnings.pull

# Offline: compare Compustat and I/B/E/S dates, write data/processed/earnings.
earnings-build:
	$(PY) -m src.earnings.compare

# EDGAR earnings 8K filings with acceptance times. Free, cached in data/raw/earnings/edgar.
earnings-edgar:
	$(PY) -m src.earnings.edgar

# Press release text (Exhibit 99.1) for each earnings 8K. Free, cached in data/raw/earnings/edgar.
earnings-releases: earnings-edgar
	$(PY) -m src.earnings.releases

AREA_ALL += earnings-build earnings-edgar earnings-releases
