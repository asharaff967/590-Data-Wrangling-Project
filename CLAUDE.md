# CLAUDE.md

Project: FINTECH 590 group project, Group 2. A backtest ready historical options dataset for S&P 500 stocks (2004 onward). We join OptionMetrics option data with point in time S&P 500 membership, verified earnings announcement timing, and realistic trading cost inputs. See README.md for the full idea and course requirements.

## How to behave

* Keep changes small and explain them in plain language. The students must be able to defend every line.
* Work only inside the area you were asked about. Do not edit another person's area folder, and keep shared code in src/common small and stable.
* Never invent table names, column names or data values. If unsure, say so and add a check that fails loudly.
* If a WRDS query or an EDGAR call fails, report the real error. Do not paper over it.
* Log where AI helped, failed or extended us in docs/ai_log.md (the three questions).

## Layout and ownership

* src/common: shared config, file helpers, WRDS connection, time of day helpers, access check
* src/earnings: Compustat and I/B/E/S dates, EDGAR filings, LLM press release extraction
* src/integration: ID crosswalk and database build
* Each area has its own src/<area>/area.mk with its make targets, tests in tests/<area>, raw data in data/raw/<area> and processed tables in data/processed/<area>.
* Areas hand data to each other only through processed tables described in docs/contracts/<area>.md.

## Conventions

* Raw data in data/raw is immutable and never committed. Processed data is rebuilt by make, never edited by hand. The final dataset goes to the course Box folder.
* Every stage runs from the Makefile. `make all` must rebuild processed tables from raw on a clean checkout.
* Secrets (WRDS username, SEC user agent) live in .env, which is gitignored. Never print or commit them.
* Join on dated link tables, never on ticker alone. Tickers get reused and renamed. CRSP permno is the hub, see src/integration/crosswalk.py.
* Be explicit about time. Dates are ISO (YYYY-MM-DD). Times of day are US Eastern. Never use information that was not public at the as of date (no look ahead).
* Missing values can carry meaning. Keep a missing flag or status column instead of silently dropping or filling rows.
* Pin dependencies: `make freeze` writes requirements.lock.
* Commits are written and attributed by the team members themselves.

## LLM enrichment step (required by the course)

Read each earnings press release (EDGAR Exhibit 99.1) and extract the announcement date and whether it came before the open or after the close. Then hand validate a random sample. Record sample size, agreement rate with the extraction, and the errors caught in docs/ai_log.md. Record API cost for every paid call.
