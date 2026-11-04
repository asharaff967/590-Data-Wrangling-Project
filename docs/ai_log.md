# AI workflow log

Graded on candor and specificity. Add an entry at each stage. For every entry answer the three questions: how AI supported us, how it failed us (half truths, buggy code, wrong claims about the data), and how it extended us (something we could not have done alone).

| Date | Stage | Supported | Failed | Extended |
| --- | --- | --- | --- | --- |
| Oct 6 | Setup | Drafted the repo scaffold, WRDS and EDGAR scripts, and offline tests | WRDS table and column names were written from memory and not yet run against WRDS. Verify with `make access`. | Not yet |
| Nov 3 | EDGAR press releases (Xueyun) | Wrote `src/earnings/releases.py` and its tests: finds Exhibit 99.1 on each filing index page and converts it to text. Checked the page layout on 12 real filings before writing the parser. | Its first regex probe of the index pages silently missed most EX-99.1 rows; it switched to a real HTML parser after the output looked implausible. A test it wrote encoded the sample bytes wrongly. Assuming every release is EX-99.1 was false: JNJ (2004 to 2008) files it as EX-99.15 and PG (2004 to 2009) as EX-99, so 102 of 773 rows rely on the fallback and carry status other_ex99. | Ran all 773 filings and surfaced cases to check by hand: 3 AAPL 8Ks with no exhibit, and JNJ filings whose exhibit is only a sales table (2007-04-18, 2019-10-23). |

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
