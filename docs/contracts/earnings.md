# Contract: earnings

Owner: Abhi. Code: `src/earnings`. Output folder: `data/processed/earnings/`.

Status: draft. The columns below come from the code and tests and have not yet been checked against a real WRDS pull.

## earnings_dates_compare.csv

One row per ticker and fiscal period. Compares the Compustat report date with the I/B/E/S announce date.

Join keys: `ticker` and `period_end`. Use `gvkey` to reach the integration crosswalk, which maps to permno.

| Column | Meaning |
| --- | --- |
| ticker | Ticker as given by Compustat, or I/B/E/S for rows with no Compustat match |
| gvkey, cik, conm | Compustat company id, SEC CIK, company name |
| fyearq, fqtr | Compustat fiscal year and quarter |
| period_end | Fiscal period end date |
| rdq | Compustat report date of quarterly earnings. No time of day. |
| ibes_period_end | I/B/E/S period end, can differ from period_end by a few days |
| ibes_anndats | I/B/E/S announce date |
| ibes_time_s | I/B/E/S announce time as seconds since midnight, US Eastern (assumed, to verify) |
| ibes_timing | BMO, DURING, AMC, UNKNOWN, or NO_IBES when there is no I/B/E/S row |
| diff_days | rdq minus ibes_anndats in days |
| status | same_day, off_by_one_day, differs_by_more, compustat_only, ibes_only, neither |

## edgar_earnings_8k.csv

One row per Form 8K filing with Item 2.02 (earnings results), from SEC EDGAR.

Join keys: `ticker`, `cik`, `filing_date`.

| Column | Meaning |
| --- | --- |
| ticker, cik | Ticker and SEC CIK |
| accession | EDGAR accession number |
| filing_date | Filing date |
| accepted_et | When EDGAR accepted the filing, US Eastern |
| edgar_timing | BMO, DURING, AMC from accepted_et. A noisy clue, the filing can lag the press release. |
| items | 8K item numbers |
| url | Link to the primary document |

## Planned

`earnings_events.csv`: the final cleaned table, one row per company and earnings event, with the announcement date and before open or after close flag verified by the LLM press release step and the hand validated sample. Target for the Oct 21 checkpoint.
