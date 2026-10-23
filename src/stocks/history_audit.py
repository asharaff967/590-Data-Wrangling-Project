"""Repeat the WRDS history notebook audits in a new, non-overwriting run folder.

This stage reads an existing pull/build. It never calls pull() or build().
Fetch evidence on WRDS once; replay using that saved evidence without a connection.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import uuid
import warnings

import pandas as pd

from ..common.io_utils import sql_list
from .pull import data_root, raw_folder, sha256, window
from .quality import numeric, require

VERSION = "1"
RETURN_CODES = [-44, -55, -66, -77, -88, -99]
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


def flag_counts(series):
    return dict(sorted(Counter(
        code for value in series.fillna("") for code in str(value).split(";") if code
    ).items()))


def load_inputs(root, start, end):
    """Check immutable raw hashes and processed row correspondence before querying."""
    raw = raw_folder(root, start, end)
    processed = Path(root) / "processed" / "stocks" / f"{start}_{end}"
    manifest_path = raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or (manifest["start"], manifest["end"]) != (start, end):
        raise ValueError("Raw manifest is incomplete or has different dates")
    daily_names = [f"daily_{y}.csv" for y in range(int(start[:4]), int(end[:4]) + 1)]
    expected = {"seed_names.csv", "pilot_securities.csv", "names.csv", "membership.csv", *daily_names}
    entries = manifest["files"]
    if len(entries) != len(expected) or {e["name"] for e in entries} != expected:
        raise ValueError("Unexpected raw manifest file set")
    frames = {}
    for entry in entries:
        path = raw / entry["name"]
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Raw checksum mismatch: {path}")
        frames[entry["name"]] = pd.read_csv(path)
        if len(frames[entry["name"]]) != entry["rows"]:
            raise ValueError(f"Raw row count mismatch: {path}")
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
    source = pd.concat([
        frames[name].assign(source_file=name, source_row=range(2, len(frames[name]) + 2))
        for name in daily_names
    ], ignore_index=True)
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


def validate_evidence(calendar, coverage, pilot, start, end):
    require(calendar, ["trading_date"], "calendar")
    days = pd.to_datetime(calendar["trading_date"], errors="raise")
    if days.empty or days.isna().any() or days.duplicated().any() or not days.between(start, end).all() or days.dt.dayofweek.ge(5).any():
        raise ValueError("Calendar is empty, invalid, duplicated, outside the window or contains weekends")
    require(coverage, ["permno", "first_date", "last_date", "window_rows", "first_ret", "first_retx"], "source coverage")
    if coverage["permno"].duplicated().any() or set(coverage["permno"]) != set(pilot["permno"]):
        raise ValueError("Source coverage must contain exactly one row per pilot permno")
    lo, hi = (pd.to_datetime(coverage[c], errors="raise") for c in ["first_date", "last_date"])
    counts = numeric(coverage["window_rows"])
    if lo.isna().any() or hi.isna().any() or lo.gt(hi).any() or (counts.isna() | counts.lt(0) | counts.mod(1).ne(0)).any():
        raise ValueError("Invalid source coverage bounds or counts")


def quote_analysis(daily):
    empty = pd.Series(float("nan"), index=daily.index)
    bid, ask = (numeric(daily[c]) if c in daily else empty for c in ["bid", "ask"])
    positive = bid.notna() & ask.notna() & bid.gt(0) & ask.gt(0)
    normal, locked, crossed = positive & bid.lt(ask), positive & bid.eq(ask), positive & bid.gt(ask)
    status = pd.Series("INVALID_OR_MISSING", index=daily.index, dtype="string")
    status = status.mask(normal, "NORMAL").mask(locked, "LOCKED").mask(crossed, "CROSSED")
    signed = (ask - bid).where(positive)
    bps = 10000 * signed / ((ask + bid) / 2).where(positive)
    extra = dict(quote_status=status, quote_eligible_main=normal,
                 quote_eligible_with_locked=normal | locked, quoted_spread_signed=signed,
                 quoted_spread_bps_main=bps.where(normal),
                 quoted_spread_bps_with_locked=bps.where(normal | locked))
    if set(extra) & set(daily.columns):
        raise ValueError("Input already has analysis columns; supply stock_daily.csv from build")
    analysis = daily.copy(deep=True).assign(**extra)
    pd.testing.assert_frame_equal(analysis[daily.columns], daily)
    sensitivity = analysis.groupby("pilot_ticker", sort=True).agg(
        total_rows=("quote_status", "size"), normal_rows=("quote_eligible_main", "sum"),
        locked_rows=("quote_status", lambda s: s.eq("LOCKED").sum()),
        crossed_rows=("quote_status", lambda s: s.eq("CROSSED").sum()),
        mean_main_bps=("quoted_spread_bps_main", "mean"),
        mean_with_locked_bps=("quoted_spread_bps_with_locked", "mean"),
        median_main_bps=("quoted_spread_bps_main", "median"),
        median_with_locked_bps=("quoted_spread_bps_with_locked", "median"),
    ).reset_index()
    denominator = (sensitivity["normal_rows"] + sensitivity["locked_rows"]).replace(0, float("nan"))
    sensitivity = sensitivity.assign(
        locked_share_of_eligible_pct=100 * sensitivity["locked_rows"] / denominator,
        mean_change_bps=sensitivity["mean_with_locked_bps"] - sensitivity["mean_main_bps"],
    )
    return analysis, sensitivity


def return_missing(series):
    value = numeric(series)
    return value.isna() | value.isin(RETURN_CODES)


def return_audit(daily, coverage):
    ret, retx = return_missing(daily["ret"]), return_missing(daily["retx"])
    evidence = daily.loc[ret | retx].copy()
    lookup = coverage.set_index("permno")
    evidence = evidence.assign(
        source_first_date=evidence["permno"].map(lookup["first_date"]),
        source_first_ret=evidence["permno"].map(lookup["first_ret"]),
        source_first_retx=evidence["permno"].map(lookup["first_retx"]),
    )
    matches = pd.to_datetime(evidence["date"]).eq(pd.to_datetime(evidence["source_first_date"]))
    agrees = ((~ret.loc[evidence.index] | return_missing(evidence["source_first_ret"]))
              & (~retx.loc[evidence.index] | return_missing(evidence["source_first_retx"])))
    evidence = evidence.assign(
        missing_ret=ret.loc[evidence.index], missing_retx=retx.loc[evidence.index],
        resolution=pd.Series("REVIEW_REQUIRED", index=evidence.index).mask(
            matches & agrees, "SOURCE_FIRST_OBSERVATION_MISSING"),
    )
    return evidence, {"ret_missing_or_code": int(ret.sum()), "retx_missing_or_code": int(retx.sum()),
                      "missing_both": int((ret & retx).sum()), "same_missing_rows": ret.equals(retx),
                      "unresolved_rows": int(evidence["resolution"].eq("REVIEW_REQUIRED").sum())}


def calendar_audit(daily, pilot, calendar, coverage, start, end):
    days = pd.DatetimeIndex(pd.to_datetime(calendar["trading_date"])).sort_values()
    observed = pd.to_datetime(daily["date"])
    lookup = coverage.set_index("permno")
    summaries, exceptions = [], []
    for security in pilot.itertuples(index=False):
        source = lookup.loc[security.permno]
        lower = max(pd.Timestamp(start), pd.Timestamp(source["first_date"]))
        # Keep the requested end, not the local/source last date: trailing gaps stay visible.
        expected = days[(days >= lower) & (days <= pd.Timestamp(end))]
        actual = observed[daily["permno"].eq(security.permno)]
        unique = pd.DatetimeIndex(actual.unique())
        counts = actual.value_counts()
        missing, unexpected, duplicates = expected.difference(unique), unique.difference(expected), counts[counts.gt(1)]
        summaries.append(dict(
            pilot_ticker=security.pilot_ticker, permno=int(security.permno),
            coverage_start=lower.strftime("%Y-%m-%d"), coverage_end=end,
            expected_dates=len(expected), observed_rows=len(actual), observed_unique_dates=len(unique),
            missing_dates=len(missing), unexpected_dates=len(unexpected), duplicate_dates=len(duplicates),
            extra_duplicate_rows=int((duplicates - 1).sum()), source_window_rows=int(source["window_rows"]),
            source_count_matches=int(source["window_rows"]) == len(actual),
        ))
        for issue, dates in [("MISSING_DATE", missing), ("UNEXPECTED_DATE", unexpected), ("DUPLICATE_DATE", duplicates.index)]:
            for date in dates:
                exceptions.append(dict(pilot_ticker=security.pilot_ticker, permno=int(security.permno),
                                       date=date.strftime("%Y-%m-%d"), issue=issue,
                                       observed_rows_on_date=int(counts.get(date, 0))))
    return pd.DataFrame(summaries), pd.DataFrame(exceptions, columns=[
        "pilot_ticker", "permno", "date", "issue", "observed_rows_on_date"])


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
        validate_evidence(calendar, coverage, pilot, start, end)
        analysis, sensitivity = quote_analysis(daily)
        returns, return_result = return_audit(daily, coverage)
        cal_summary, exceptions = calendar_audit(daily, pilot, calendar, coverage, start, end)
        years = pd.to_datetime(calendar["trading_date"]).dt.year.value_counts().sort_index().rename_axis("year").reset_index(name="trading_days")
        tables = {"stock_daily_analysis.csv": analysis, "quote_sensitivity.csv": sensitivity,
                  "missing_return_records.csv": returns, "coverage_by_security.csv": cal_summary,
                  "calendar_exceptions.csv": exceptions, "calendar_by_year.csv": years,
                  "trading_calendar.csv": calendar, "source_coverage.csv": coverage}
        outputs = {}
        for name, frame in tables.items():
            path = output / name
            frame.to_csv(path, index=False, mode="x")
            saved = pd.read_csv(path)
            if len(saved) != len(frame) or saved.columns.tolist() != frame.columns.tolist():
                raise ValueError(f"Export verification failed: {name}")
            outputs[name] = {"rows": len(frame), "sha256": sha256(path)}
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--run-id", help="New directory name; default: UTC timestamp plus random suffix")
    parser.add_argument("--evidence-dir", help="Completed scripted run to replay; no WRDS connection")
    parser.add_argument("--check-only", action="store_true", help="Offline input validation only; no writes or connection")
    parser.add_argument("--quiet-known-pandas-warning", action="store_true", help="Only suppress the known pandas 2.2.3/Python 3.14 assignment warning")
    args = parser.parse_args()
    if args.quiet_known_pandas_warning and platform.python_version_tuple()[:2] == ("3", "14") and pd.__version__ == "2.2.3":
        warnings.filterwarnings("ignore", message=r"^ChainedAssignmentError: behaviour will change in pandas 3\.0!",
                                category=FutureWarning, module=r"^(__main__|pandas\.core\.reshape\.merge|src\.stocks\.(quality|history_audit))$")
    start, end = window(args.start, args.end)
    root = data_root(args.data_root)
    if args.check_only:
        _, daily, pilot, _, _ = load_inputs(root, start, end)
        print(json.dumps({"input_check": "pass", "rows": len(daily), "securities": len(pilot),
                          "connection_opened": False, "files_written": False}, indent=2))
        return
    output, summary = run(root, start, end, args.run_id, args.evidence_dir)
    print(json.dumps({"output": str(output), **summary}, indent=2))
    if summary["quality_status"] == "review_required":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
