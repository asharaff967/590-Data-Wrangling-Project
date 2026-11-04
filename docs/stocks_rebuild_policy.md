# Stocks rebuild and historical audit retention policy

This policy applies to the Group 2 stocks area. On November 4, Loki authorized
review and publication of the ten code, test and documentation files to the
stocks branch for teammate review. Real-data operations still follow the
preservation procedure below.

## Rebuildable does not mean disposable

Raw files and their completed pull manifests are immutable. A vendor revision or
new pull needs a new data root, not replacements inside a previous raw run.
Processed tables can be regenerated from raw, as required by CLAUDE.md. However,
the current processed snapshot is evidence for its existing audits. Preserve that
snapshot together with the audits until an explicitly reviewed replacement exists.
Rebuild into a separately prepared workspace/data root with its own validated raw
snapshot. Never silently redirect downstream users to that new result.

The existing build function/CLI still replaces processed outputs. That behavior
has not been changed by this documentation or cleanup. Do not invoke it against
an active data root containing saved audits. The notebook's refusal to overwrite
is an additional entrypoint guard; direct calls and make targets do not inherit it.
The team's make-all reconstruction requirement applies to a separately prepared
clean workspace, not the frozen review workspace. This check does not run make all.

## Operations and effects

| Operation | Connects | Writes | Allowed in the present review |
|---|---|---|---|
| history_audit --check-only | No | No | Yes: validate saved raw/processed correspondence |
| --check-only --evidence-dir COMPLETE_RUN | No | No | Yes: recompute in memory and compare saved audit |
| run with evidence_dir but without --check-only | No | Creates a new audit directory | No: offline is not necessarily read-only |
| run without evidence_dir | WRDS | Creates a new audit directory | No |
| stocks-build / build | No | Replaces processed files | No; later only in a separate rebuild workspace |
| stocks-pull / pull | WRDS | Creates a new raw run | No |

## Audit identity and retention

An audit identifies its source file hash, window, code hashes, evidence and output
hashes. Keep those values and the old run folder unchanged. Do not relabel old
manifests with current code hashes. A future writing replay uses a NEW run ID and
records the parent manifest; it never replaces the old run or changes its date.
A failed audit is retained as a partial run with failure.json, not recycled.

The new read-only check can compare only a completed scripted run under that
window's repro_audits directory. It refuses older ad hoc folders, a mismatched
window/source or altered outputs. It validates all eight saved CSV tables and the
quality summary after recomputing with the current code. A pass means the saved
analysis is consistent; it does not independently verify vendor data, establish
trading eligibility or erase a quality_status of review_required.

## Present WRDS procedure

1. Confirm the group-project directory and Python version using metadata only.
2. Upload the source-only review ZIP and extract into a NEW code directory outside
   the real data tree. Never unzip it over the group checkout or another project folder.
3. Verify the package hashes and run fictional tests with a new scratch directory.
4. Point the review code at the confirmed existing group data root and requested
   date window. Run --check-only; this reads data but changes no market/audit files.
5. Identify a completed scripted audit with matching source/window; do not assume
   a fixed directory name or select the latest directory without checking it.
6. Add --evidence-dir while keeping --check-only. It compares in memory, prints
   counts/status and verifies saved file hashes are unchanged. Stop on an error.

Use PYTHONDONTWRITEBYTECODE=1 (or sys.dont_write_bytecode=True before imports).
Use the current Jupyter kernel's sys.executable. Do not install packages, open WRDS
connections, run build/make all or create audit folders as part of this check.
Local fixture results do not certify another runtime. See stocks_history_repro.md
for the October 28 WRDS results and the scope of the November 4 local recheck.
