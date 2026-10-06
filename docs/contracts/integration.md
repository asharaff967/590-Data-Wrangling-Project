# Contract: integration

Owners: Abhi and Loki. Code: `src/integration`. Output folder: `data/processed/integration/`.

Status: draft, not yet run against WRDS.

## crosswalk_asof.csv

One row per pilot ticker that had a common stock permno on the as of date. CRSP permno is the hub, every other ID is attached through a dated link table.

Join key: `permno`.

| Column | Meaning |
| --- | --- |
| ticker, permno, comnam | CRSP ticker, permno and company name on the as of date |
| secid | OptionMetrics security id, from the OptionMetrics CRSP link |
| secid_score | Link match score, 1 is best. Anything above 1 is flagged. |
| gvkey | Compustat id, from the CRSP Compustat link, primary links first |
| ibes_ticker, ibes_score | I/B/E/S ticker and link score |
| cik | SEC CIK, from the Compustat company table |
| as_of | The date the join was made |
| flags | Semicolon list: no_secid, no_gvkey, no_ibes, no_cik, weak_secid_match, weak_ibes_match, multiple_secid, multiple_gvkey, multiple_ibes |

Rows with flags need a human look before the crosswalk is trusted.

## Planned

A full interval version of the crosswalk (valid_from, valid_to per link) so any date can be joined, not only one as of date.
