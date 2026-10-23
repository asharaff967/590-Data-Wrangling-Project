# Loki stocks pilot: local review and WRDS execution

Owner: Loki. This guide covers the stocks area and its ten-stock pilot.
Team members write and attribute their own commits under CLAUDE.md.
See the [verified WRDS results](stocks_validation_2026-10-23.md) and
[history audit workflow](stocks_history_repro.md) for the completed 2004-2024 run.

Pilot labels in Abhi's `config/universe.csv`: **AAPL, MSFT, JPM, XOM, JNJ, PG, KO,
WMT, TSLA, META**. The file was introduced in Abhi's commit `d5a3292` on Oct 6,
2026. The code reads that file rather than maintaining a second list.

## What is implemented

Adaptation of the input-preserving audit approach in
[Loki's checker](https://github.com/Lengwinex9xLok/market-data-quality-demo/blob/main/demo.py).
This is a daily CRSP implementation, not an unchanged copy of the broker checker.
It checks keys/prices/quotes/analytics, records raw line numbers, and matches
historical ticker and S&P membership by permno and date. No raw rows are deleted.
See [the complete data contract](contracts/stocks.md).

The live schema is checked with `LIMIT 0` for `crsp.stocknames`, `crsp.dsp500list`
and `crsp.dsf`. Names first resolve the pilot label to one common-stock permno active at
`universe_asof` (default: the requested end date; CLI override `--universe-asof`);
then full name history is pulled by permno, so a label such as META can recover
its earlier FB name. Reused tickers with several permnos active on the anchor date stop for human
review. Expired candidates are excluded by their documented name intervals.
For a historical window before a rename, explicitly select a later anchor date
where the pilot label exists; the following history pull is still by permno.
Daily data is selected server-side by permno/window and partitioned by year.
Raw output uses an immutable run folder and checksum manifest. Incomplete pulls
and altered raw files cannot be passed off as successful builds.

The module does not require local market-data downloads. Pull and build can both
run within WRDS. Local tests use only fictional records, with a fake WRDS query
interface. No live account, licensed source sample or credentials are bundled.

## Start on WRDS JupyterHub

[WRDS's Jupyter guide](https://wrds-www.wharton.upenn.edu/pages/classroom/using-jupyter-at-wrds-notebook/)
supports browser-based Python work inside WRDS. The October 23 pilot verified
access to the required CRSP tables for the executing account. Each teammate
must still verify their own permissions. Existing repo scripts target legacy
CRSP. Incompatible live schemas fail loudly instead of guessing a CIZ translation.

1. Put the reviewed course source checkout in an approved WRDS working directory.
   Confirm that `src/stocks/history_audit.py` exists in that checkout. Before this
   change is merged, use the reviewed branch or a source-only handoff; public
   main does not yet contain the module. Keep data, secrets, environments and
   executed notebooks out of source transfers.
2. Open `notebooks/stocks_pilot_wrds.ipynb` in the extracted project. The notebook
   checks preinstalled runtime packages without pip installation, asks for your
   WRDS username, and invokes the same pull/build modules. The observed WRDS
   Python 3.14 session cannot reach PyPI; do not retry internet installation.
   python-dotenv is optional. If pytest is missing, cloud tests have not run;
   obtain offline setup instructions before continuing.
   Authenticate with WRDS normally; never paste a password into a notebook cell.
3. Start with the example month (June 2024). Change the window in the notebook
   after the first real source/schema/quality check. The course's broad target
   is 2004 onward; the example is not a claim of that coverage.
4. Inspect `quality_report.json`, `coverage.csv` and flagged rows before using the
   data. Keep licensed rows on WRDS; extract only permitted summary deliverables.

## Terminal alternative on WRDS (Linux)

Run from the extracted project root. With a Python 3.10+ interpreter, first
check the existing environment. The environment creation/install commands below
are for a network-enabled setup only; do not use them in the observed isolated
WRDS kernel:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/stocks
```

Set `WRDS_USERNAME` through your environment or the existing gitignored `.env`.
Set a persistent storage root appropriate to your account and available quota.
The default data folder stays in the project; an external root is optional:

```bash
export STOCKS_DATA_ROOT=/your/approved/persistent/stocks-data
make stocks-pull STOCKS_START=2024-06-01 STOCKS_END=2024-06-30
make stocks-build STOCKS_START=2024-06-01 STOCKS_END=2024-06-30
```

Replace the example path before running. The equivalent Python commands, also
usable with Jupyter's current interpreter, are:

```bash
python -m src.stocks.pull --start 2024-06-01 --end 2024-06-30
python -m src.stocks.build --start 2024-06-01 --end 2024-06-30
```

The pull needs authentication. The build is offline and uses the saved manifest
and CSVs. A second pull for an existing run is rejected without overwriting data.
Inspect a partial failure and preserve it; select a different approved data root
for a new attempt. Errors are not hidden. This bounded pilot has no automatic
resume or retry loop. Do not run root `make all` just to test stocks: the existing
earnings/EDGAR/integration targets need their own data and configuration.

On local Windows the existing Makefile defaults to Unix `.venv/bin/python`.
Use `.venv\Scripts\python.exe -m src.stocks...` or override `PY` in make. No shared
Makefile change is needed. `STOCKS_DATA_ROOT` works identically on either system.

## Larger cloud jobs and storage

Per [WRDS system policies](https://wrds-www.wharton.upenn.edu/pages/about/system-policies/),
CPU/RAM-heavy SSH jobs must run on compute nodes through Grid Engine (`qsub`,
`qsas` or `qrsh`), not directly on a login/head node. Configure the job for your
account and currently installed Python environment; do not infer scheduler
resources from this local Windows test. JupyterHub is suitable for the bounded
interactive pilot; move large scale jobs to the documented scheduled workflow.

WRDS currently documents 10 GB persistent home storage and 500 GB temporary
scratch shared across an institution, with scratch files deleted after 7 days.
Check the account's actual quota before scaling; scratch is not a permanent data
archive. Ten stocks of daily CRSP data is a bounded task. Full option chains are
a separate, potentially much larger query and are outside this module.

## Validation and remaining work

The bundled tests cover signed prices, source missing codes, duplicate rows,
historical renames, inclusive membership dates, interval ambiguity, source-row
traceability, checksum validation, absent securities, incomplete queries and
schema failures. Tests also cover the original earnings/integration code when
running the repository suite. Exact local results are in the handoff report.
Dependency versions for the small stocks runtime are in
`src/stocks/requirements-tested.txt`; install that after root requirements when
reproducing this tested Python 3.11.9 version set in a separate environment.
Do not force these pins into the preinstalled WRDS Python 3.14 kernel; that
runtime was separately exercised with the preinstalled packages, as recorded
in the validation summary. Other team areas remain unpinned as upstream.

The complete scripted history audit was run on WRDS on October 23, 2026 and
compared against the saved Notebook audits. All 12 comparison checks passed;
seven corresponding tables matched exactly, and all 56 protected files were
unchanged. Follow [the history workflow](stocks_history_repro.md) to create a
new audit directory without rebuilding or replacing existing processed tables.
Team integration and corporate-action/delisting/broker additions remain pending.
A selected pilot with membership labels is not a survivorship-free historical
market universe.

## Oct 23 seed-resolution correction

The live pilot exposed ticker reuse in JPM and META. Requiring a single permno
over all historical name rows was too strict. The corrected resolver selects
active common-stock name intervals at an explicit reference date and still
rejects simultaneous ambiguity or malformed intervals. Do not overwrite the
old incomplete run. Retry with a separate root such as
`data/stocks_seed_asof_v2`, then use that same root for the offline build.
The corrected resolver was used for the successful June pilot and historical
pull. The later WRDS validation passed all 35 stocks tests, including the seed
resolution cases and 11 history-audit tests. Earlier intermediate test counts
are superseded by the validation summary.
