# AI workflow log

Graded on candor and specificity. Add an entry at each stage. For every entry answer the three questions: how AI supported us, how it failed us (half truths, buggy code, wrong claims about the data), and how it extended us (something we could not have done alone).

| Date | Stage | Supported | Failed | Extended |
| --- | --- | --- | --- | --- |
| Oct 6 | Setup | Drafted the repo scaffold, WRDS and EDGAR scripts, and offline tests | WRDS table and column names were written from memory and not yet run against WRDS. Verify with `make access`. | Not yet |

## Assumptions to verify

* I/B/E/S announce times (anntims) are US Eastern. Check the WRDS I/B/E/S documentation.
* A time of 00:00:00 means the time was not captured. Check against the raw data.
* EDGAR acceptance time is when the SEC received the filing, which can be later than the press release.

## Required LLM enrichment step

Press release extraction of announcement date and before open or after close.

* Model and prompt:
* Sample size validated by hand:
* Agreement rate:
* Errors caught:
* API cost so far:

## Accountability statement

We reviewed, understand and can defend everything in this repository.
