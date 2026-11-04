# Stocks warnings: isolated dependency validation

The pinned Python 3.14 offline stocks profile passes the latest tested stocks
suite with warnings enabled. This is a stocks-only validation, not a migration
of the shared project environment. No business logic or tests changed to remove
warnings. The opt-in legacy warning filter was not used.

Tested branch: `loki/stocks-pilot-audit` at
`0e6648d779e2143309aac0d448621fcbe05d8b32`.
Machine-readable evidence: [stocks_warning_validation.json](stocks_warning_validation.json).

## What caused the investigation

The original WRDS run reported 50 passed and 578 warnings: 577 repeated pandas
FutureWarnings at 12 single-step assignment sites and one dateutil import
DeprecationWarning. These were not 578 separate code defects. Python 3.14.5 /
pandas 2.2.3 / dateutil 2.8.2 reproduced both warning categories in a minimal
copied-frame assignment test, with correct output and unchanged input.

The isolated Python 3.14.5 / pandas 3.0.1 / NumPy 2.4.6 /
dateutil 2.9.0.post0 environment produced zero warnings in the same probe.
This supports an environment-level remedy for the observed warnings; it is not
proof that arbitrary assignments or every pandas 3 workflow are compatible.

## Verification, with source scopes kept separate

| Source and check | Runtime | Result |
|---|---|---|
| October 28 source, original suite | WRDS Python 3.14.5, pandas 2.2.3 | 50 passed; 578 warnings |
| Same old source, candidate suite | WRDS Python 3.14.5, pandas 3.0.1 | 50 passed; no warning summary |
| Same old source, one four-row fictional fixture | Original versus candidate WRDS environment | 12 CSVs byte-identical; quality report and summary equal |
| Same old source, saved-data read-only check | Candidate WRDS environment | 49,107 rows, 10 securities, 8 audit CSVs matched; files unchanged |
| Latest tested commit, stocks suite | Local Windows Python 3.11.9, pandas 2.2.3 | 51 passed; 0 pytest warnings; empty stderr |
| Latest tested commit, stocks suite | WRDS Python 3.14.5, pandas 3.0.1 | 51 passed; 0 pytest warnings; empty stderr |

The latest suite includes the additional test rejecting a saved audit whose raw
manifest hash differs. It passed in both environments; the source package was
unchanged. The latest WRDS run used fictional fixtures only and did not read
real data or old audits. Its warnings were enabled and recorded, not ignored.

Local results were executed by the agent in an independent source copy. WRDS
results were executed by Loki using prepared cells, then supplied in chat. The
full latest remote receipt/logs remain in run `latest_stocks_test_pzb7evwd`.
The runner checked all pinned installed versions before running tests. Its
complete remote receipt has not been downloaded or independently rerun here.

The saved-data comparison belongs to the OLD source snapshot. It is not a
latest-source real-data check, a new vendor query or independent human arithmetic
verification. Its quality_status remains `documented_with_usage_restrictions`.

## Dependency use and preservation

[requirements-wrds-offline.txt](../src/stocks/requirements-wrds-offline.txt)
records the exact validated offline profile for CPython 3.14.5 on Linux x86_64
with glibc 2.34. It includes test dependencies; it excludes the live WRDS client.
Use it only in a fresh isolated venv. For an offline installation, supply a
previously hash-verified wheelhouse and run that venv's Python, for example:

```sh
"$VENV/bin/python" -I -B -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --only-binary=:all: --find-links "$WHEELHOUSE" -r src/stocks/requirements-wrds-offline.txt
```

The pins are a version record, not a replacement for wheel checksum validation.
Do not combine this profile with `requirements-tested.txt`: that file preserves
the older local Python 3.11 profile. Shared root requirements and WRDS-managed
packages remain unchanged. Other team modules and live pulls have not been
validated under this profile.

Keep the tested ZIP, its hash manifest, old raw/processed data and audit manifests
unchanged. Recomputing an audit without `--check-only` writes a new directory;
`build` can replace processed outputs. Neither is part of this review.
New version information belongs in new validation records, never in old audits.

The requested warning investigation and latest fictional regression review are
complete. Adoption by the group or any later data operation is a separate step.

## Primary-source findings retained from the earlier investigation

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
