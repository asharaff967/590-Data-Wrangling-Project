# Reproducible stocks history audits on WRDS

For the current preservation-only review, first follow [the rebuild and retention policy](stocks_rebuild_policy.md). Use --check-only throughout; the live and writing-replay examples below are for a separately authorized later run.

Run from the course repository root. This stage uses the existing immutable raw
pull and existing processed `stock_daily.csv`. It does **not** call the older
build stage (which replaces processed tables). It does not execute Git commands.
All market records and evidence remain on WRDS. Local tests use fictional rows.
The runtime needs the project's existing pandas and, only for live evidence,
wrds packages; no new runtime dependency or internet pip installation is needed.

## 1. Check saved inputs without opening a connection

In a fresh WRDS notebook, set the repository working directory and use its kernel
interpreter. No previous notebook variables are required:

```python
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path.cwd().resolve()  # Start the notebook in the course repository root.
assert (PROJECT / 'src' / 'stocks').is_dir(), 'Select the course repository root first.'
os.chdir(PROJECT)
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
HISTORY_ROOT = PROJECT / 'data' / 'stocks_history_2004_2024'
command = [sys.executable, '-m', 'src.stocks.history_audit',
           '--data-root', str(HISTORY_ROOT),
           '--start', '2004-01-01', '--end', '2024-12-31',
           '--quiet-known-pandas-warning']
subprocess.run(command + ['--check-only'], check=True)
```

Checks: complete raw manifest, raw hashes/counts, source row correspondence,
pilot identifiers/labels, and consistency of processed flags and quality report.
CSV round trips allow only floating differences within rtol/atol 1e-12; the source
files themselves are protected by byte hashes. Any other mismatch stops the run.

## 2. Query and record source evidence on WRDS

Use normal WRDS authentication. The child process reads `WRDS_USERNAME` from the
environment or the existing gitignored .env; a value assigned only to a Python
config module in the parent notebook is not inherited. If credentials require
interactive input, use the current kernel as below rather than a child pipe.
Never store passwords in notebooks or copy them into chat.

```python
from src.common import config
from src.stocks.history_audit import run

if not config.WRDS_USERNAME:
    config.WRDS_USERNAME = input('WRDS username: ').strip()

output, summary = run(HISTORY_ROOT, '2004-01-01', '2024-12-31',
                      run_id='history_script_v1')
print(output)
print(summary)
```

The existing connection helper handles normal WRDS authentication; never supply
a password as a source constant.
For an already configured environment, the CLI equivalent is:

```bash
python -m src.stocks.history_audit --data-root data/stocks_history_2004_2024 --start 2004-01-01 --end 2024-12-31 --run-id history_script_v1
```

Live mode checks `crsp.dsi`/`crsp.dsf` schemas, reads index dates, and queries each
saved pilot permno's source-wide MIN/MAX(date), first RET/RETX, and requested-window
row count. It does not re-download the historical daily dataset. It closes its
connection on success or failure. Missing permissions or columns fail visibly.

## 3. Replay offline

```python
from src.stocks.history_audit import run
first_run = HISTORY_ROOT / 'processed/stocks/2004-01-01_2024-12-31/repro_audits/history_script_v1'
output, summary = run(HISTORY_ROOT, '2004-01-01', '2024-12-31',
                      run_id='history_replay_v1', evidence_dir=first_run)
print(output)
print(summary)
```

Replay verifies the parent completion manifest, source hash/window and saved
evidence hashes. It never connects to WRDS. Analytical tables are reproducible;
timestamps, runtime/code hashes and provenance reflect each new execution.
Omitting run_id generates a UTC timestamp plus random suffix. Reusing a run_id
always fails before a database connection; choose a fresh name, never delete
prior evidence merely to retry. Only a completed scripted run supplies replay
evidence; the older ad hoc notebook audit directories are preserved snapshots.

## Outputs and interpretation

Each run creates `processed/stocks/START_END/repro_audits/RUN_ID/` with:

* `stock_daily_analysis.csv`: all original rows/columns plus quote-only eligibility
  and signed/main/sensitivity spread fields. Input quotes are never repaired.
* `quote_sensitivity.csv`: by-security counts, means, medians and change when
  positive locked quotes are included at zero spread.
* `missing_return_records.csv`: missing/nonfinite or legacy-coded return rows,
  source-first evidence and explicit resolved/review status. No return imputation.
* `trading_calendar.csv`, `calendar_by_year.csv`, `source_coverage.csv`: saved WRDS
  evidence. SQL, parameters and query timestamp are recorded in the manifest.
* `coverage_by_security.csv`, `calendar_exceptions.csv`: missing, unexpected and
  duplicate dates, plus requested-window source-count reconciliation.
* `quality_summary.json`: all core/diagnostic counts, policy and limitations.
* `audit_manifest.json`: written last, marking computational completion with
  input, code, evidence and output hashes. Existing input/audit files are hashed
  before work and checked unchanged before completion.

Errors retain a new partial directory with failure.json and no completion
manifest. A completed computation can still require review: CLI exit code 2
means saved results include unresolved exceptions. Python callers must inspect
summary['quality_status']; computational completion is not a clean-data claim.
No fixed 49,107/753/866/2 counts are hardcoded into the analysis.

Calendar lower bounds come from source MIN(date), not the local first row.
Upper bounds remain the requested end, so trailing gaps cannot be concealed by
shortening the window. If a different universe contains delisted stocks or
trading interruptions, review gaps using appropriate source evidence; the script
does not infer listing status or manufacture daily observations. This calendar
audit is relative to CRSP, not an independent exchange-calendar verification.

Main spreads require finite positive bid < ask; sensitivity also permits positive
bid == ask. Invalid/crossed quotes are excluded from both analytic spreads while
their source rows remain. Quote eligibility is not general row eligibility.
Membership and other flags remain available to downstream analysis. The selected
pilot is not a survivorship-free historical S&P universe; closing quoted spreads
do not prove executable prices or total costs. Missing first-day returns are
consistent with missing prior prices, not independent proof of IPO dates/causes.

## Tests and known WRDS warning

```bash
python -m pytest -q tests/stocks
```

Use the existing offline pytest setup on WRDS if needed. No pip network retry.
The opt-in CLI flag `--quiet-known-pandas-warning` narrowly filters the known
ChainedAssignmentError FutureWarning for pandas 2.2.3/Python 3.14 in the stocks
modules and pandas merge. It does not fix that compatibility issue, suppress
other warnings, or apply to a separate pytest process. Existing notebook warning
filters can remain when using the direct Python API.

Make targets `stocks-history-check` and `stocks-history-audit` wrap the same CLI.
Supply STOCKS_AUDIT_ROOT, STOCKS_START, STOCKS_END and optionally STOCKS_AUDIT_ARGS.
Do not run `make all` for this preservation-only audit: earlier project build
targets have different output semantics and also involve other team areas.

## Later GitHub handoff

This change is local and uncommitted. Team members write/attribute commits under
CLAUDE.md. Later review and submit source modules, fictional tests, Make targets,
contracts, instructions and the AI log to Abhi's course repo through a branch/PR.
Reconcile with the then-current upstream before publishing. Do not upload .env,
credentials, licensed CSVs, audit evidence, raw/processed directories, local test
dependencies or code-transfer ZIPs. Ignore rules cover data/stocks_* roots, which
the original data/raw and data/processed rules did not cover. Inspect staged
file names before committing. No push/PR is performed by this workflow.

## Verified WRDS run and Notebook comparison

On October 23, 2026, the installed script ran in WRDS JupyterHub against the
existing 2004-2024 inputs and fresh CRSP calendar/source-coverage evidence.
The run completed with 49,107 rows, 753 crossed quotes, 866 locked quotes,
two jointly missing return records matching source-first observations, and
zero calendar exceptions. All 12 comparison checks passed; the seven compared
tables had exactly equal values on their corresponding columns. All 56 protected
pre-existing data and audit files retained their SHA-256 hashes.

See [the aggregate validation summary](stocks_validation_2026-10-23.md) for
comparison scope and limitations. The actual manifests, comparison records,
source evidence and market rows remain on WRDS. These counts describe one
verified run; they are not assertions built into the audit algorithm.


## Stocks code cleanup on October 28 2026

The `loki/stocks-pilot-audit` code now separates three responsibilities:

* `src/stocks/raw_inputs.py` validates the raw manifest, file set, checksums and
  row counts for both build and history audit, and attaches annual CSV row provenance.
* `src/stocks/history_checks.py` contains dataframe-only quote, return and calendar
  checks; it performs no file writes or WRDS queries.
* `src/stocks/history_audit.py` keeps input correspondence checks, evidence retrieval,
  replay, non-overwriting run management and the existing CLI.

Existing imports from `history_audit` and all Make/notebook commands remain
available. Pure check function bodies were moved without changing their syntax
trees. The existing quality/membership rules, SQL and pull code are unchanged.
The opt-in known-warning filter includes the new module names so it retains its
previous narrow scope after the move; it is still not a pandas compatibility fix.

Local verification used fictional data only on Python 3.11.9 / pandas 2.2.3 /
NumPy 2.4.6. All 38 original stocks tests pass. Six new tests cover corrupt
manifests reaching both consumers and annual-file CSV line provenance. The full
repository suite passes 61 tests. Twelve build/audit CSVs are byte-identical before
and after the cleanup; quality_summary.json is also identical. The build report
matches after excluding its deliberately changed source-code hashes. New runtime
and code hashes identify new executions; old audit manifests remain snapshots.

No live WRDS pull, real-data build or historical-source revalidation was performed.
No existing data or audit directory was opened or changed. Other team areas and
shared common code are unchanged. At that stage, this was a local, uncommitted cleanup for student review.
See the November 4 release review below for subsequent authorization.


## Read-only saved-audit comparison added on October 28 2026

`--check-only` retains its original input-validation fields and writes no files.
It now also verifies the saved file inventory/hashes are unchanged during the
check. Add `--evidence-dir` for a completed run under this exact window's
`repro_audits` to verify all output hashes and compare eight recomputed CSV tables
and the quality summary in memory. The current calculation is shared with the
writing audit, so there is no duplicate financial/checking implementation.

Without `--check-only`, an evidence-dir replay still writes a NEW audit directory;
it is outside the current read-only scope. Build behavior remains unchanged and
must be used only in a separately prepared rebuild workspace.

Local validation: 67 offline tests pass. Tests forbid filesystem writes, build/run
and query calls during both read-only modes. Altered saved tables fail even when
someone updates their recorded hash. Twelve fictional build/audit CSVs and the
quality summary still match the original branch output. WRDS execution was pending
at packaging time; see the user-run verification below. No historical count is a
hardcoded target.


## User-run WRDS read-only verification on October 28 2026

Loki ran the source-only review package in a separate WRDS code directory and
provided the terminal/JSON outputs in chat. The review archive SHA-256 was
c1966a3a4b6b144a992104458ce612f88f03a71c57a9128f3c2a1356c5101543.
At that verification, local Python sources matched the package. The November 4
provenance guard described below is a later change and is not in that archive.

* Runtime: Python 3.14.5, pandas 2.2.3, NumPy 2.4.6, offline pytest 9.1.1.
* Fictional stocks suite: 50 passed, 578 warnings, exit code 0. Warnings remain
  recorded; their causes have not been independently established or fixed.
* Input-only check: 49,107 rows, 10 securities, 2004-01-01 through 2024-12-31;
  input_check pass, no connection, no writes, saved files unchanged, exit code 0.
* Saved run: history_script_20261023T171337Z_7da30e, beneath that window's
  repro_audits directory. Check-only comparison reported evidence_check pass,
  eight CSV tables compared, calendar_status pass, saved files unchanged and
  exit code 0. The implementation also compares the saved quality summary.
* quality_status remains documented_with_usage_restrictions. Matching saved
  outputs does not remove quote exceptions or independently validate vendor
  records, corporate actions or an exchange trading calendar.

Only aggregate outputs were provided locally. Real input rows, raw quotations
and saved audit evidence remain on WRDS. No live source query, new real-data
build/audit output, PBIX modification, commit, push or merge was performed.
This records human execution of AI-prepared software checks, not an independent
human arithmetic audit. Source/code and analytical consistency are the scope.


## Branch release review on November 4 2026

Loki authorized review and publication of these ten stocks-area files to
loki/stocks-pilot-audit for teammate review. The publication covers the shared
raw validation, extracted checks, read-only comparison, tests and documentation.

The read-only comparison now also checks that the saved audit's raw-manifest
hash matches the current processed report. This prevents accepting an audit
from a different raw snapshot even when its stock CSV and calculated values
agree. A fictional regression case exercises this rejection and verifies that
the saved files remain unchanged.

The October 28 WRDS results above apply to the earlier review package. This
additional provenance guard has local fixture coverage and has not been rerun
against the real WRDS snapshot. The 578 WRDS warnings remain under investigation.

Local release validation passed 68 repository tests (51 stocks tests) on
Python 3.11.9 / pandas 2.2.3 without warning suppression. Twelve fictional
build/audit CSVs and the quality summary match the original branch, and all six
extracted check function bodies retain identical syntax trees.
