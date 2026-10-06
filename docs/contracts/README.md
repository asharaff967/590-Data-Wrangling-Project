# Data contracts

Each area writes its processed tables to `data/processed/<area>/` and describes them in `docs/contracts/<area>.md`. Other areas read only those tables, never another area's raw data or code. That is how the pieces fit together without everyone editing the same files.

A contract states, for every table:

* the file name and what one row means (the grain)
* the key columns and how to join to other areas
* every column with its meaning and units
* time conventions and known gaps

## Shared conventions

* **Hub key:** CRSP `permno`. The integration area holds the crosswalk to every other ID (OptionMetrics secid, Compustat gvkey, I/B/E/S ticker, SEC CIK). Areas that cannot carry permno carry the ID they have and let integration map it.
* **Dates:** ISO `YYYY-MM-DD`. Times of day are US Eastern.
* **Point in time:** never use a value that was not public on the date it is attached to.
* **Missing values:** keep a status or flag column instead of silently dropping rows.

## Areas

| Area | Folder | Contract |
| --- | --- | --- |
| Earnings | `src/earnings` | [earnings.md](earnings.md) |
| Integration | `src/integration` | [integration.md](integration.md) |
| Options | `src/options` | to write |
| Stocks | `src/stocks` | to write |
