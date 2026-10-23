# Stocks pilot: verified WRDS results, October 23, 2026

The scripted audit reproduced the saved Notebook results for ten selected stocks
over January 1, 2004 through December 31, 2024. It read the existing raw and
processed files, queried fresh CRSP evidence on WRDS, and wrote a separate run
directory. It did not re-pull daily history or call the build stage.

This document contains aggregate findings only. Raw and processed market rows,
SQL result tables, audit manifests, comparison records, credentials and executed
Notebook outputs remain on WRDS and are excluded from the GitHub handoff.

## Run and scope

* Run ID: `history_script_20261023T171337Z_7da30e`.
* Universe anchor: June 30, 2024. Labels: AAPL, JNJ, JPM, KO, META, MSFT, PG,
  TSLA, WMT, XOM, as selected from `config/universe.csv`.
* History follows the resolved `permno`, including earlier ticker names.
* CRSP calendar/source evidence: `crsp.dsi` and `crsp.dsf`.
* Runtime: WRDS JupyterHub, Python 3.14.5, pandas 2.2.3, numpy 2.4.6, wrds 3.5.0.
* Computational status: `complete`. Quality status:
  `documented_with_usage_restrictions`.

## Findings and treatment

| Check | Result | Treatment |
| --- | ---: | --- |
| Daily rows / securities | 49,107 / 10 | Preserve every source record |
| Normal quotes | 47,488 | Eligible under the main quote rule |
| Locked quotes | 866 | Exclude from main spread; include at zero in sensitivity |
| Crossed quotes | 753 | Retain rows; exclude from both analytical spread measures |
| Missing RET / RETX | 2 / 2, on the same two rows | Retain missing values; no zero imputation |
| Unresolved missing-return cases | 0 | Both cases match source-first observations |
| CRSP calendar dates | 5,285 | Reference calendar for the requested window |
| Missing / unexpected / duplicate security dates | 0 / 0 / 0 | No exceptions within the documented coverage windows |
| Outside S&P 500 membership | 3,040 rows | Preserve dated membership flag for downstream selection |

Eight securities have 5,285 observations each. META has 3,175 and TSLA has 3,652;
their expected windows start at the earliest dates available for their permnos
in CRSP, rather than manufacturing pre-history rows. The missing RET and RETX
records are the first source observations for META and TSLA. This is consistent
with no preceding price observation; the exact missing-value reason and IPO
dates were not independently established.

Main spreads use finite positive `bid < ask` pairs. The sensitivity variant also
includes positive locked quotes, giving 48,354 quote-eligible rows. These are
quote eligibility rules, not a general decision to discard or accept whole rows.
Neither rule applies an S&P membership filter automatically.

## Comparison with saved Notebook audits

All 12 comparison checks passed. Seven corresponding CSV tables were read back
and compared on their original columns: 49,107 analysis rows, ten security-level
sensitivity rows, two missing-return records, 5,285 calendar dates, 21 annual
calendar counts, ten security-coverage rows, and the empty exceptions table.
The analysis comparison retained row order; keyed summaries were aligned by
their documented keys. Values matched exactly after CSV parsing, including
missing values and source-file/row provenance. This does not claim byte-identical
CSV formatting or identical schemas where the script adds evidence columns.

The remaining checks covered source-first dates and returns, summary counts and
usage status, fresh source counts for all ten securities, new output hashes, and
preservation of existing files. First prices were not fetched by the new query
and were not part of the fresh source comparison.

All 56 protected pre-existing data/audit files retained their SHA-256 digests.
The run's manifest was preserved when the separate comparison record was saved
under `notebook_comparison/`. The old quote policy's pending-check text remains
as historical context; subsequent return/calendar records and this comparison
document completion without rewriting that policy.

## Validation and limits

The installed WRDS stocks suite passed **35 tests**, using fictional inputs.
It reported 413 warnings; the known pandas 2.2.3/Python 3.14 assignment warning
is documented in the [run guide](stocks_history_repro.md). A targeted warning
filter was used for the live audit. Suppression is not a compatibility fix.
The local Python 3.11.9/pandas 2.2.3 repository suite passed **52 tests**.
The subsequent submission review added three Notebook startup/preservation
regression cases and passed **55 local tests**. These extra cases have not been
run on WRDS; the historical cloud result remains 35 tests. The history audit
algorithm is unchanged by this review.

The checked-in source provides new live runs and replay from saved scripted
evidence. The one-time comparison against the older Notebook audits was a
separate WRDS console procedure; it is not automatically performed by
`history_audit.py`. The manifests and detailed comparison evidence are retained
on WRDS, so a public reader can inspect the method and fictional tests but cannot
independently reproduce the real-data result from this repository alone.

This selected pilot is not a survivorship-free historical S&P 500 universe.
Calendar completeness is relative to CRSP, not an independent exchange calendar.
Crossed-quote causes remain unverified, closing spreads do not establish
executable trading costs, and the audit does not supply delisting-adjusted
returns, corporate-action event tables or cross-provider integration.

See the [contract](contracts/stocks.md) and
[reproduction instructions](stocks_history_repro.md) before downstream use.
