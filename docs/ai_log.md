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


## Oct 28: stocks code organization cleanup

* Supported: located the unchanged local/GitHub `loki/stocks-pilot-audit` version,
  consolidated duplicated raw-run checks in the stocks area, and moved pure
  historical dataframe checks out of run/evidence management. Preserved public
  imports, CLI commands, SQL and data-quality rules.
* Failed: initially interpreted the request as the independent Audible project.
  Its unmerged draft PR was closed after Loki clarified the group project and
  explicitly selected stocks only. No Audible changes were merged. The stocks
  cleanup itself made no change to other members' area code.
* Extended: all 38 existing stocks tests remain passing; six focused cases cover
  both raw-input consumers and multi-year CSV line provenance. The full offline
  suite passes 61 tests. Twelve fictional build/audit CSVs and the quality summary
  match the pre-refactor version byte for byte; only source-code hash metadata
  changes. These software checks are not a new WRDS or independent human audit.
* Scope and ownership: no actual market records, saved WRDS audit evidence,
  credentials or Trading data were read or modified. No paid API calls were made.
  The code, student review and commit ownership remain with the stocks area;
  this cleanup is local, uncommitted and not pushed.


## Oct 28: rebuild policy and read-only WRDS check preparation

* Supported: separated regeneration of processed tables from retention of the
  existing source/audit snapshot. Documented that offline commands may still
  write, and that the current build CLI retains its overwrite behavior.
* Failed: earlier local tests alone did not exercise a strictly read-only
  comparison against complete saved audits. Added a check-only evidence path
  rather than treating a writing replay as safe for the current instruction.
* Extended: reused one in-memory calculation for both audit modes; verified all
  saved output hashes and compared eight CSVs/quality summary without writes.
  The 67-test suite blocks write/build/query calls in read-only checks; twelve
  fictional CSVs remain byte-identical to the original branch. A changed table
  with a rewritten manifest hash is still detected by recomputation.
* Boundaries: no actual WRDS input/evidence, real data or PBIX was accessed or
  changed. No live query, paid API call, commit or push. The source-only review
  package is for extraction into a new code directory. WRDS runtime validation
  and student confirmation remain pending; the first teaching step checks only
  directory and interpreter metadata.


## Oct 28: user-run WRDS read-only verification completed

* Supported: guided Loki through path verification, source ZIP checksums,
  isolated code/dependency extraction, a fresh test subprocess, input-only
  validation and the saved-audit comparison while retaining --check-only.
* Failed/limits: pytest was absent in the WRDS kernel; used the hash-verified
  prior universal-wheel bundle in a separate directory, with no system install
  or network. The suite produced 578 dateutil/pandas warnings; those were kept
  as evidence rather than declared fixed or globally suppressed.
* Extended: Loki's reported WRDS output shows 50 fictional tests passed and two
  read-only checks exited 0. The real saved window has 49,107 rows and 10 stocks;
  eight audit CSVs/quality summary match and saved files remain unchanged.
  quality_status is still documented_with_usage_restrictions.
* Ownership and scope: Loki executed prepared cells and provided the outputs.
  No independent human arithmetic or new vendor-source verification is claimed.
  The agent recorded aggregate results locally; original market/audit records
  remain on WRDS. No real-data rebuild, new audit output, PBIX/Trading changes,
  commit, push or merge. Earlier preparation entries remain historical records.


## Oct 28: warning triage after WRDS validation

* Supported: counted 577 pandas FutureWarnings at twelve single-assignment
  locations and one dateutil import deprecation. Inspected pandas 2.2.3 warning
  detection and consulted upstream pandas/dateutil issues and release notes.
* Failed/limits: repeated independent-project terminology in a group-project
  response. Corrected the scope. Test success alone did not establish the warning
  root cause; the exact WRDS minimal reproduction and loaded dateutil version are
  still needed. A local older-Python control does not settle the WRDS case.
* Extended: distinguished repeated warning events from distinct defects and
  prepared a fresh-process, fictional-DataFrame probe with warnings recorded and
  displayed. No ignore filter, pandas monkeypatch, blind .loc rewrite or dependency
  upgrade was applied. No real data were used; no commit or push.

## Nov 4: stocks branch release review

* Supported: reviewed the ten pending stocks code, test and documentation files
  at Loki's explicit request to publish them to his stocks branch for teammates.
  Shared code and other members' modules are outside this change.
* Failed: found that the saved-audit comparison verified the daily CSV and
  recalculated outputs without explicitly comparing the audit's raw-manifest
  hash to the processed report. Added that provenance check and a fictional
  regression test. Updated current-scope wording that still described the
  earlier local-only review.
* Extended: all 68 repository tests pass locally, including 51 stocks tests.
  Twelve fictional build/audit CSVs and the quality summary match the original
  branch. All six extracted check function bodies have identical syntax trees.
  Validation used Python 3.11.9 and pandas 2.2.3, without warning suppression.
* Limits: the added provenance guard has not been rerun on the real WRDS snapshot.
  The previously recorded 578 WRDS warnings remain unresolved and visible.
  The October 28 WRDS verification belongs to its original source package.
* Publication scope: ten reviewed text files on loki/stocks-pilot-audit, authorized
  by Loki on November 4. AI assisted review and preparation. Student review of
  the implementation remains necessary before integration into the group main.


## Completed isolated stocks warning validation and teammate review

* Supported: prepared hash-verified offline dependencies and source copies;
  guided Loki through exact-runtime reproduction, old-source regression,
  fictional equivalence, saved-data read-only comparison and latest-source tests.
  Recorded dependency pins and source/hash scope without editing old evidence.
* Failed/limits: the online download failed because WRDS could not reach PyPI,
  not because the verified wheel tags were incompatible. Old 50-test results
  initially did not cover the latest raw-manifest guard. A separate 51-test run
  now covers it. Full remote receipts were not downloaded; WRDS outcomes are
  explicitly user-reported. Live-client and other-team-module compatibility are
  not established by offline stocks tests.
* Extended: latest commit 0e6648d passes all 51 stocks tests locally and in the
  user-run WRDS candidate environment, with zero pytest warnings, empty stderr,
  a passing provenance-rejection test and unchanged source package. Earlier
  twelve-CSV equivalence and 49,107-row/eight-table saved-data results remain
  attributed to the older source snapshot.
* Preparation scope: these dependency/documentation records were first prepared
  as uncommitted working-tree changes for Loki's review. No business logic/test
  changes, warning suppression, shared dependency replacement, real-data rewrite
  or audit rewrite was performed.
* Publication authorization: Loki subsequently requested a final review and
  commit/push of exactly these five files to loki/stocks-pilot-audit for teammate
  review. This publication excludes main, any merge, real data and old audits.
  AI assisted the review and commit preparation under Loki's explicit instruction.
  Existing test evidence remains attributed to tested commit 0e6648d; this
  documentation/dependency-record update does not change the tested Python code.
