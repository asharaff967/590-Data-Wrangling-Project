# AI workflow log

## Oct 23: second pre-submission review

* Supported: reviewed all 19 proposed files, including Notebook metadata and
  source cells, fictional test fixtures, exclusion rules, and documentation.
  Checked for data/evidence files, embedded outputs, credentials and private
  account paths; only aggregate results and public repository attribution are
  intended for submission.
* Failed: the fresh-Notebook bootstrap changed the working directory but did not
  explicitly add the project root to `sys.path`. An isolated startup reproduced
  `ModuleNotFoundError: No module named 'src'`. The README also retained a blanket
  claim that live WRDS access had not been verified, contradicting the stocks
  validation summary.
* Extended: fixed the bootstrap and reproduction example, corrected the README's
  scope, and added three local regression cases for launch paths and refusing to
  rebuild over existing output. The audit algorithm is unchanged. The final local
  suite passed 55 tests; the historical WRDS run still records 35 tests, since
  these new Notebook tests have not been run there. No cloud files, commits,
  pushes or PRs were changed during this review.

## Oct 23: verified WRDS execution and source-only handoff

* Supported: restored the WRDS session paths, verified and installed the source
  bundle, ran 35 fictional stocks tests, and executed the complete history audit
  on WRDS. Compared it with saved Notebook evidence: 12 checks passed, including
  exact parsed values in seven corresponding tables. Wrote an aggregate result
  summary for team review; the data and audit files stay on WRDS.
* Failed/limits: earlier documentation still described the new run as pending
  and was updated after direct verification. Browser/Kernel reconnection delayed
  execution; the task was submitted only after the session recovered. The old
  Notebook build cell could overwrite processed outputs on rerun, so the source
  template now stops when that output directory exists. The standalone build
  remains an explicit rebuilding command. The pandas warning remains a runtime
  compatibility limitation, and a successful audit does not resolve quote causes,
  survivorship bias, or final dataset integration.
* Extended: recorded fresh source counts and first observations, retained all
  56 pre-existing data/audit file hashes, and stored the comparison separately
  from the completed run manifest. Prepared source/doc changes and a file-level
  review inventory without uploading licensed records. The previous entries
  below describe what was known at those earlier stages; this entry supersedes
  their pending cloud-verification status. No commit, push, PR or paid enrichment
  API call was made in this stage. Team review and commit attribution remain
  with the students.

## Oct 23: repeatable stocks history audit scripts (local, not pushed)

* Supported: translated the user's successful WRDS notebook sequence into input
  validation, quote policy/sensitivity, missing-return source evidence, calendar
  reconciliation, and a per-run manifest. Cloud results remain user-reported;
  local validation uses fictional records, not licensed samples.
* Failed/limits: notebook variables and hardcoded expected counts were not a
  repeatable pipeline; the previous build replaces processed files. The new
  stage reads existing outputs instead. pandas 2.2.3 on Python 3.14 can emit a
  known assignment warning; optional narrow suppression is not a compatibility fix.
* Extended: isolated output directories, frozen evidence replay without WRDS,
  source-count drift detection, preservation hashes and failure records. Added
  ignore rules for nested stocks data roots before any future GitHub handoff.
  No push, commit, live local WRDS connection or paid enrichment API call.

Graded on candor and specificity. Add an entry at each stage. For every entry answer the three questions: how AI supported us, how it failed us (half truths, buggy code, wrong claims about the data), and how it extended us (something we could not have done alone).

| Date | Stage | Supported | Failed | Extended |
| --- | --- | --- | --- | --- |
| Oct 6 | Setup | Drafted the repo scaffold, WRDS and EDGAR scripts, and offline tests | WRDS table and column names were written from memory and not yet run against WRDS. Verify with `make access`. | Not yet |
| Oct 22 | Stocks pilot (local, not pushed) | Adapted Loki's input-preserving checker to daily CRSP, added bounded WRDS pulls, dated names/membership, row provenance and offline tests | Initial test fixture reused a daily key while expecting no duplicate flag; corrected the fixture. Initial pytest temp directory was inaccessible; used the task workspace. Live WRDS schemas and this user's permissions remain unverified. | Added raw checksums and incomplete-run rejection; kept source missing codes, negative CRSP prices and historical rename/membership boundaries distinct from corrupt observations. No paid enrichment API was used. |

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

## Oct 23: live seed-resolution failure and correction

* Supported: read actual candidate name intervals returned by the user; distinguished expired candidates from active ones.
* Failed: the first resolver required uniqueness over all historical ticker uses, blocking valid JPM and META selections. Local fixtures had not covered a reused label with non-overlapping dates.
* Extended: added explicit universe_asof selection and manifest provenance, retained rejection of concurrent ambiguity, and tested date boundaries, bad dates and rename history. The old incomplete raw run is preserved; retry uses a separate data root. No push or paid enrichment API call.
