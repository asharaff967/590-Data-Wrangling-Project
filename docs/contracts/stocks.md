# Contract: stocks

Owner: Loki. Code: `src/stocks`. Status: tested with fictional records and run on
WRDS for the ten-stock 2004-2024 sample on October 23, 2026. The scripted audit
matched the saved Notebook results; see the
[validation summary](../stocks_validation_2026-10-23.md). This module uses legacy CRSP,
not broker intraday data. The universe is read from `config/universe.csv`.

## Scope and paths

An explicit start/end window is required by the Python commands. The Make targets
default to June 2024 as a small example, not an agreed project coverage window.
`STOCKS_DATA_ROOT` or `--data-root` relocates both raw and processed files without
editing shared config. Default root: the repository's `data/` directory.

Raw: `<root>/raw/stocks/wrds/<start>_<end>/`. Processed:
`<root>/processed/stocks/<start>_<end>/`. Raw pulls are immutable. A manifest records
queries, actual schemas, requested window, universe, timestamps, row counts,
SHA-256 digests, Python/pandas versions, code digests, Git revision and dirty state.
The build requires a complete manifest and checks every raw file digest and count.

## stock_daily.csv

One row per **source record**, intended key `(permno, date)`. Duplicate keys stay in
the output with flags on every member; the table must not be used as a unique-key
join until those flags are reviewed. It never selects a duplicate winner.

| Column | Meaning / units |
| --- | --- |
| permno, date | CRSP security identifier and date, ISO YYYY-MM-DD |
| prc | Unchanged legacy CRSP price, USD/share; negative sign denotes bid/ask average |
| vol | Unchanged daily share volume; zero/missing and legacy -99 missing code are diagnostics |
| ret, retx | Source decimal returns, with/without distributions; raw missing codes retained; not delisting-adjusted |
| cfacpr, cfacshr | Source cumulative price/share adjustment factors; no adjustment applied here |
| bid, ask | Genuine CRSP closing bid/ask if BOTH source columns exist; USD/share, unadjusted |
| price_abs | Derived absolute value of finite prc; zero remains zero and is flagged |
| price_is_bid_ask_average | Derived prc < 0 indicator |
| pilot_ticker | Research-universe label; may differ from the historical ticker |
| historical_ticker | Ticker from exactly one name interval active on date; blank if missing/ambiguous |
| name_match_count | Number of dated name candidates; zero or several requires review |
| membership_match_count | Number of S&P 500 membership intervals active on date |
| in_sp500 | True for at least one active membership interval, false for none, blank for invalid key |
| source_file, source_row | Raw daily CSV basename and original CSV line, header = line 1 |
| core_flags | Semicolon-separated structural/value/join issues requiring review |
| diagnostic_flags | Semicolon-separated context/missing-data indicators; not automatic deletion rules |

Daily rows are never dropped, filled, repaired or reordered. Raw field values are
preserved by the audit; processed CSV serialization can change formatting/dtypes.
The raw CSV is authoritative. Counts may overlap. CSV outputs are deterministic
from the same raw input and code. The report includes provenance digests.

## Other outputs

* `identifier_intervals.csv`: source name rows, grain `(permno, namedt, nameenddt)`;
  also `ticker, shrcd`. All name history for resolved permnos, including renames.
* `membership_intervals.csv`: source S&P 500 membership rows, grain
  `(permno, start, ending)` for the selected securities and overlapping window.
* `coverage.csv`: one row per resolved pilot security, `pilot_ticker, permno, rows,
  observed_dates, rows_with_core_flags, in_sp500_rows, missing_entirely`.
* `quality_report.json`: total/core/diagnostic counts, entirely absent securities,
  scope limitations and raw/build provenance.

Intervals use inclusive endpoints. A missing end is open-ended; an invalid date
string is an error, never an open end. Invalid raw intervals stop the build with
their CSV line numbers. Overlaps at an observation are flagged without multiplying
the daily rows. Pilot labels resolve on an explicit `universe_asof` date (default: requested
end date). Several common-stock permnos active on that date stop the pull for
human review; expired candidates do not create artificial ambiguity. The anchor
is recorded in the manifest. Use `--universe-asof` when a later label identifies
a selected security whose earlier ticker differs from the label. No ticker-only join attaches daily observations.

## Limits

The ten pilot labels are a selected universe, not the historical S&P 500 universe;
membership flags do not remove survivorship bias from that selection. Historical
name dates do not establish publication-time availability. Observed dates do not
prove trading-calendar completeness. Closing quotes do not establish intraday
freshness, NBBO or executable trading costs. `bidlo/askhi` are never substituted
for genuine bid/ask. Event-clock regression checks do not apply to a daily export.

Known legacy return missing codes (-44, -55, -66, -77, -88, -99) and volume -99
remain visible as diagnostics. SQL NULL and non-finite analytics also remain
visible. These values must not be interpreted as economic returns or volume.

No corporate-action event pull, delisting-return integration, broker symbol
bridge, OptionMetrics secid link or final database is delivered by this pilot.
The existing integration area owns cross-provider IDs; this module does not
modify its code. Schema preflight rejects incompatible CIZ layouts and source
permission errors propagate. The completed pilot audit covers the documented
checks; it does not certify all fields or the final integrated dataset.

## Reproducible history audits

`python -m src.stocks.history_audit` reads an existing pull/build and writes only
to a new `processed/stocks/START_END/repro_audits/RUN_ID` directory. See
`../stocks_history_repro.md` for evidence capture/replay and GitHub handoff.

New fields are `quote_status` (NORMAL, LOCKED, CROSSED, INVALID_OR_MISSING),
`quote_eligible_main`, `quote_eligible_with_locked`, `quoted_spread_signed`
(ask minus bid), `quoted_spread_bps_main` and `quoted_spread_bps_with_locked`
(10,000 times spread divided by midpoint). Eligibility is quote-only, not a
general row-quality or membership pass. No missing analytic spread is filled.
Source-first evidence distinguishes first-observation missing returns from
unresolved cases. Calendar coverage uses source-wide first dates and the
requested end, keeping trailing gaps visible. All original records remain.
