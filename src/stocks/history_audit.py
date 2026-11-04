"""Repeat the WRDS history notebook audits in a new, non-overwriting run folder.

This stage reads an existing pull/build. It never calls pull() or build().
Fetch evidence on WRDS once; replay using that saved evidence without a connection.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from io import StringIO
from pathlib import Path
import platform
import re
import uuid
import warnings

import pandas as pd

from ..common.io_utils import sql_list
from .pull import data_root, raw_folder, sha256, window
from .quality import numeric, require
from .raw_inputs import daily_source_rows, read_raw_run
# Keep these imports public for existing notebooks and downstream callers.
from .history_checks import (
    RETURN_CODES, calendar_audit, flag_counts, quote_analysis, return_audit,
    return_missing, validate_evidence,
)

VERSION = "1"
CALENDAR_SQL = """SELECT date AS trading_date FROM crsp.dsi
WHERE date BETWEEN %(start)s AND %(end)s ORDER BY date"""


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def file_hashes(folder):
    return {str(p.resolve()): sha256(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def unchanged(hashes):
    for name, digest in hashes.items():
        if sha256(name) != digest:
            raise ValueError(f"Existing file changed during audit: {name}")


def load_inputs(root, start, end):
    """Check immutable raw hashes and processed row correspondence before querying."""
    raw, manifest, frames = read_raw_run(root, start, end)
    processed = Path(root) / "processed" / "stocks" / f"{start}_{end}"
    manifest_path = raw / "manifest.json"
    pilot = frames["pilot_securities.csv"]
    require(pilot, ["permno", "pilot_ticker"], "pilot")
    ids = numeric(pilot["permno"])
    if (ids.isna() | ids.le(0) | ids.mod(1).ne(0)).any() or ids.duplicated().any() or pilot.empty:
        raise ValueError("Invalid or duplicate pilot identifiers")
    if pilot["pilot_ticker"].isna().any() or pilot["pilot_ticker"].duplicated().any():
        raise ValueError("Invalid pilot labels")
    daily = pd.read_csv(processed / "stock_daily.csv")
    require(daily, ["permno", "date", "ret", "retx", "pilot_ticker", "core_flags",
                    "diagnostic_flags", "source_file", "source_row"], "processed daily")
    source = daily_source_rows(frames, start, end)
    # CSV round trips can differ in the last floating-point digits, not economically.
    pd.testing.assert_frame_equal(daily[source.columns], source, check_dtype=False,
                                  check_exact=False, rtol=1e-12, atol=1e-12)
    if daily.empty or not daily["permno"].isin(ids).all():
        raise ValueError("Empty data or securities outside the saved pilot")
    labels = dict(zip(pilot["permno"], pilot["pilot_ticker"]))
    if not daily["pilot_ticker"].eq(daily["permno"].map(labels)).all():
        raise ValueError("Processed pilot labels do not match saved permnos")
    days = pd.to_datetime(daily["date"], format="%Y-%m-%d", errors="raise")
    if days.isna().any():
        raise ValueError("Missing daily dates")
    report = json.loads((processed / "quality_report.json").read_text(encoding="utf-8"))
    if report["raw_manifest_sha256"] != sha256(manifest_path):
        raise ValueError("Processed report belongs to a different raw manifest")
    if report["rows"] != len(daily) or report["core_flag_counts"] != flag_counts(daily["core_flags"]) or report["diagnostic_counts"] != flag_counts(daily["diagnostic_flags"]):
        raise ValueError("Processed flags/counts do not match the saved report")
    return processed, daily, pilot, report, manifest


def source_sql(pilot):
    ids = sql_list([int(x) for x in pilot["permno"]])
    return f"""WITH coverage AS (
        SELECT permno, MIN(date) AS first_date, MAX(date) AS last_date,
        SUM(CASE WHEN date BETWEEN %(start)s AND %(end)s THEN 1 ELSE 0 END) AS window_rows
        FROM crsp.dsf WHERE permno IN {ids} GROUP BY permno
    ) SELECT c.*, d.ret AS first_ret, d.retx AS first_retx
    FROM coverage c JOIN crsp.dsf d ON d.permno = c.permno AND d.date = c.first_date
    ORDER BY c.permno"""


def fetch_evidence(db, pilot, start, end):
    # LIMIT 0 gives a clear schema/access error; no alternate table is guessed.
    for table, columns in [("dsi", ["date"]), ("dsf", ["permno", "date", "ret", "retx"])]:
        require(db.raw_sql(f"SELECT * FROM crsp.{table} LIMIT 0"), columns, f"crsp.{table}")
    params = {"start": start, "end": end}
    query = source_sql(pilot)
    calendar = db.raw_sql(CALENDAR_SQL, params=params)
    coverage = db.raw_sql(query, params=params)
    metadata = {"mode": "wrds", "queried_at_utc": datetime.now(timezone.utc).isoformat(),
                "calendar_sql": CALENDAR_SQL, "source_coverage_sql": query, "parameters": params}
    return calendar, coverage, metadata


def replay_evidence(folder, source_hash, start, end):
    folder = Path(folder)
    record = json.loads((folder / "audit_manifest.json").read_text(encoding="utf-8"))
    if record["status"] != "complete" or record["source_sha256"] != source_hash or record["window"] != [start, end]:
        raise ValueError("Replay requires a complete run with identical source data and dates")
    frames = []
    for name in ["trading_calendar.csv", "source_coverage.csv"]:
        if sha256(folder / name) != record["outputs"][name]["sha256"]:
            raise ValueError(f"Replay evidence hash mismatch: {name}")
        frames.append(pd.read_csv(folder / name))
    return *frames, {"mode": "replay", "parent_manifest": str((folder / "audit_manifest.json").resolve()),
                     "parent_manifest_sha256": sha256(folder / "audit_manifest.json"),
                     "original_evidence": record["evidence"]}


def analyze(daily, pilot, report, raw_manifest, calendar, coverage, start, end):
    """Compute audit tables and summary in memory, without file writes or a connection."""
    validate_evidence(calendar, coverage, pilot, start, end)
    analysis, sensitivity = quote_analysis(daily)
    returns, return_result = return_audit(daily, coverage)
    cal_summary, exceptions = calendar_audit(daily, pilot, calendar, coverage, start, end)
    years = pd.to_datetime(calendar["trading_date"]).dt.year.value_counts().sort_index().rename_axis("year").reset_index(name="trading_days")
    tables = {"stock_daily_analysis.csv": analysis, "quote_sensitivity.csv": sensitivity,
              "missing_return_records.csv": returns, "coverage_by_security.csv": cal_summary,
              "calendar_exceptions.csv": exceptions, "calendar_by_year.csv": years,
              "trading_calendar.csv": calendar, "source_coverage.csv": coverage}
    quote_counts = {str(k): int(v) for k, v in analysis["quote_status"].value_counts().items()}
    calendar_pass = exceptions.empty and bool(cal_summary["source_count_matches"].all())
    other_core = {k: v for k, v in report["core_flag_counts"].items() if k != "CROSSED_QUOTE" and v}
    review = not calendar_pass or bool(return_result["unresolved_rows"] or other_core or quote_counts.get("INVALID_OR_MISSING", 0))
    summary = {
        "rows": len(daily), "securities": len(pilot), "window": [start, end],
        "universe_asof": raw_manifest.get("universe_asof"),
        "quality_status": "review_required" if review else "documented_with_usage_restrictions",
        "quote_status_counts": quote_counts, "returns": return_result,
        "calendar_status": "pass" if calendar_pass else "review_required",
        "calendar_exception_records": len(exceptions),
        "core_flag_counts": report["core_flag_counts"], "diagnostic_counts": report["diagnostic_counts"],
        "rules": [
            "Preserve original columns, row order, missing values and source provenance.",
            "Main spread: finite positive bid < ask; sensitivity: also positive bid == ask at zero spread.",
            "Crossed or invalid quotes have missing analytic spreads; never swap quotes or take absolute spreads.",
            "Quote eligibility is not general row eligibility; preserve other quality and membership flags.",
            "Missing returns and legacy missing codes are not zero returns; exclude from relevant return statistics.",
            "Earliest-source missing returns are consistent with no prior price; no IPO or precise cause claim.",
            "Calendar starts use source MIN(date), capped at requested start; requested end is retained.",
        ],
        "limitations": [
            "Fixed pilot labels are not a survivorship-free historical S&P 500 universe.",
            "Calendar completeness is relative to crsp.dsi, not an independent exchange calendar.",
            "Source counts were queried now and can differ after a vendor revision; such differences require review.",
            "Closing quoted spreads are not executable prices or total transaction costs.",
            "Crossed-quote causes remain unverified; full-period statistics can hide year effects.",
            "Older notebook audits are historical snapshots and are not overwritten or newly certified by this run.",
        ],
    }
    return tables, summary


def run(root, start, end, run_id=None, evidence_dir=None, connect_factory=None):
    start, end = window(start, end)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("run-id must use 1-80 letters, digits, underscores or hyphens")
    processed = Path(root) / "processed" / "stocks" / f"{start}_{end}"
    output = processed / "repro_audits" / run_id
    if output.exists():
        raise FileExistsError(f"Audit run already exists: {output}; choose a new run-id")
    protected = {**file_hashes(raw_folder(root, start, end)), **file_hashes(processed)}
    processed, daily, pilot, report, raw_manifest = load_inputs(root, start, end)
    source_hash = sha256(processed / "stock_daily.csv")
    output.mkdir(parents=True, exist_ok=False)
    try:
        if evidence_dir:
            calendar, coverage, evidence = replay_evidence(evidence_dir, source_hash, start, end)
        else:
            if connect_factory is None:
                from ..common.wrds_conn import connect
                connect_factory = connect
            db = connect_factory()
            try:
                calendar, coverage, evidence = fetch_evidence(db, pilot, start, end)
            finally:
                db.close()
        tables, summary = analyze(daily, pilot, report, raw_manifest, calendar, coverage, start, end)
        outputs = {}
        for name, frame in tables.items():
            path = output / name
            frame.to_csv(path, index=False, mode="x")
            saved = pd.read_csv(path)
            if len(saved) != len(frame) or saved.columns.tolist() != frame.columns.tolist():
                raise ValueError(f"Export verification failed: {name}")
            outputs[name] = {"rows": len(frame), "sha256": sha256(path)}
        write_json(output / "quality_summary.json", summary)
        outputs["quality_summary.json"] = {"sha256": sha256(output / "quality_summary.json")}
        unchanged(protected)
        write_json(output / "audit_manifest.json", {
            "status": "complete", "script_version": VERSION, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "window": [start, end], "source_sha256": source_hash,
            "raw_manifest_sha256": report["raw_manifest_sha256"], "evidence": evidence,
            "python": platform.python_version(), "pandas": pd.__version__,
            "code_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
            "protected_existing_files": protected, "outputs": outputs,
        })
        return output, summary
    except BaseException as exc:
        write_json(output / "failure.json", {"status": "incomplete", "error_type": type(exc).__name__,
                                            "message": str(exc)})
        raise


def check_saved(root, start, end, evidence_dir=None):
    """Read-only validation; optionally compare a completed audit with recomputed tables.

    This function never calls run(), build(), pull() or a connection factory.
    It returns counts/status only, and verifies that no saved file was changed,
    added or removed while checking. All analytical calculations stay in memory.
    """
    start, end = window(start, end)
    processed = Path(root) / "processed" / "stocks" / f"{start}_{end}"
    raw = raw_folder(root, start, end)
    before_raw, before_processed = file_hashes(raw), file_hashes(processed)
    try:
        processed, daily, pilot, report, raw_manifest = load_inputs(root, start, end)
        result = {
            "input_check": "pass", "rows": len(daily), "securities": len(pilot),
            "window": [start, end], "evidence_check": "not_requested",
            "connection_opened": False, "files_written": False,
        }
        if evidence_dir is not None:
            evidence_dir = Path(evidence_dir).resolve()
            # A history check must use evidence from this exact preserved window.
            audit_root = (processed / "repro_audits").resolve()
            if not evidence_dir.is_relative_to(audit_root) or evidence_dir == audit_root:
                raise ValueError("Evidence must be a completed run inside this window's repro_audits")
            calendar, coverage, _ = replay_evidence(
                evidence_dir, sha256(processed / "stock_daily.csv"), start, end,
            )
            tables, summary = analyze(
                daily, pilot, report, raw_manifest, calendar, coverage, start, end,
            )
            manifest = json.loads((evidence_dir / "audit_manifest.json").read_text(encoding="utf-8"))
            if manifest.get("raw_manifest_sha256") != report["raw_manifest_sha256"]:
                raise ValueError("Saved audit belongs to a different raw manifest")
            expected_files = set(tables) | {"quality_summary.json"}
            if set(manifest["outputs"]) != expected_files:
                raise ValueError("Unexpected saved audit output file set")
            for name in sorted(expected_files):
                if sha256(evidence_dir / name) != manifest["outputs"][name]["sha256"]:
                    raise ValueError(f"Saved audit output hash mismatch: {name}")
            for name, frame in tables.items():
                # Compare like-for-like CSV representations without writing a file.
                expected = pd.read_csv(StringIO(frame.to_csv(index=False)))
                saved = pd.read_csv(evidence_dir / name)
                pd.testing.assert_frame_equal(
                    saved, expected, check_dtype=False, check_exact=False,
                    rtol=1e-12, atol=1e-12,
                )
                if manifest["outputs"][name]["rows"] != len(frame):
                    raise ValueError(f"Saved audit row count mismatch: {name}")
            saved_summary = json.loads((evidence_dir / "quality_summary.json").read_text(encoding="utf-8"))
            if saved_summary != summary:
                raise ValueError("Saved audit quality summary differs from recalculation")
            result.update(
                evidence_check="pass", csv_tables_compared=len(tables),
                quality_status=summary["quality_status"],
                calendar_status=summary["calendar_status"],
            )
    finally:
        if before_raw != file_hashes(raw) or before_processed != file_hashes(processed):
            raise ValueError("Saved input or audit files changed during read-only checking")
    result["saved_files_unchanged"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--run-id", help="New directory name; default: UTC timestamp plus random suffix")
    parser.add_argument("--evidence-dir", help="Completed scripted run to replay; no WRDS connection")
    parser.add_argument("--check-only", action="store_true", help="Read-only input validation; with --evidence-dir also compare the completed audit")
    parser.add_argument("--quiet-known-pandas-warning", action="store_true", help="Only suppress the known pandas 2.2.3/Python 3.14 assignment warning")
    args = parser.parse_args()
    if args.quiet_known_pandas_warning and platform.python_version_tuple()[:2] == ("3", "14") and pd.__version__ == "2.2.3":
        warnings.filterwarnings("ignore", message=r"^ChainedAssignmentError: behaviour will change in pandas 3\.0!",
                                category=FutureWarning, module=r"^(__main__|pandas\.core\.reshape\.merge|src\.stocks\.(quality|history_audit|history_checks|raw_inputs))$")
    start, end = window(args.start, args.end)
    root = data_root(args.data_root)
    if args.check_only:
        print(json.dumps(check_saved(root, start, end, args.evidence_dir), indent=2))
        return
    output, summary = run(root, start, end, args.run_id, args.evidence_dir)
    print(json.dumps({"output": str(output), **summary}, indent=2))
    if summary["quality_status"] == "review_required":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
