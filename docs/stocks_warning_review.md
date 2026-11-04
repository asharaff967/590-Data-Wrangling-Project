# Stocks warning investigation

Scope: the October 28 investigation of Group 2 stocks code and its WRDS test
environment. That investigation applied no warning fix, global warning filter
or dependency install. This note accompanies the November 4 branch review;
the exact-runtime probe and compatibility fix are still pending.

## Observed counts

The user-provided WRDS test output reports 50 passed, 578 warnings, exit code 0.
577 FutureWarnings arise at 12 locations in src/stocks/quality.py. Those locations
are single-step assignments to explicitly copied frames, not df[column][row]
assignments. One DeprecationWarning originates in dateutil/tz/tz.py during import,
where the installed dependency calls datetime.utcfromtimestamp(0).

The aggregate count is repeated events across tests, not 578 independent defects.
The reference-count condition in the locally inspected pandas 2.2.3
DataFrame.__setitem__ can warn when an object appears to be temporary and its
blocks have references. Python 3.14 changes this reference-count assumption.

## Primary-source findings

* https://github.com/pandas-dev/pandas/issues/61368 documents Python 3.14
  false positives for ordinary single-step assignments, including pandas 2.2.3.
* https://github.com/pandas-dev/pandas/pull/63186 changes the detection for Python
  3.14; this is upstream-library work, not evidence that every project warning
  has the same cause or that a particular candidate environment is validated.
* https://pandas.pydata.org/docs/whatsnew/v2.3.3.html identifies 2.3.3 as the first
  generally Python-3.14-compatible pandas version. The WRDS test used 2.2.3.
* https://github.com/dateutil/dateutil/issues/1284 identifies the import-time
  utcfromtimestamp deprecation. The dateutil changelog records its removal in
  version 2.9.0: https://dateutil.readthedocs.io/en/stable/changelog.html.

## Current decision

Do not mechanically rewrite every assignment as .loc and do not ignore the
warnings. First reproduce a single-step copied-frame assignment in a fresh WRDS
subprocess and record the actual loaded pandas/dateutil versions and paths.
The leading hypothesis is an environment compatibility issue, pending that
exact-runtime probe. A local Python 3.11.9 / pandas 2.2.3 / dateutil 3.0.0 control
produced correct output, preserved its input and emitted no warnings.

If confirmed, test a compatible dependency combination in a separate environment,
then rerun fictional tests and compare the saved analysis without changing the
old data root or managed WRDS packages. General Python support does not guarantee
that any proposed upgrade preserves all dtypes, date handling and output bytes.
Do not monkeypatch pandas internals or add extra references merely to defeat its
warning detector. No dependency or business-rule change is validated yet.

The 50 passing tests and the earlier eight-table read-only comparison remain
positive evidence for current behavior; they do not prove future compatibility.
