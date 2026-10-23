"""Fictional offline evidence; never contacts WRDS."""
import json

import pandas as pd
import pytest

from src.stocks.build import build
from src.stocks.history_audit import (
    calendar_audit, load_inputs, quote_analysis, return_audit, run, validate_evidence,
)
from src.stocks.pull import raw_folder, sha256

START, END = "2020-12-21", "2020-12-24"


def fixture_data(root):
    folder = raw_folder(root, START, END)
    folder.mkdir(parents=True)
    names = pd.DataFrame([dict(permno=1, ticker="TEST", shrcd=11,
                              namedt=START, nameenddt=None)])
    rows = [dict(permno=1, date=f"2020-12-{day}", prc=100, vol=1000,
                 ret=None if day == 21 else .01, retx=None if day == 21 else .01,
                 cfacpr=1, cfacshr=1, bid=bid, ask=ask)
            for day, bid, ask in [(21, 99, 101), (22, 100, 100), (23, 102, 101), (24, 99, 101)]]
    frames = {"seed_names.csv": names, "names.csv": names,
              "pilot_securities.csv": pd.DataFrame([dict(permno=1, pilot_ticker="TEST")]),
              "membership.csv": pd.DataFrame([dict(permno=1, start=START, ending=None)]),
              "daily_2020.csv": pd.DataFrame(rows)}
    manifest = dict(status="complete", start=START, end=END, universe_asof=END,
                    source="fictional", files=[])
    for name, frame in frames.items():
        frame.to_csv(folder / name, index=False)
        manifest["files"].append(dict(name=name, rows=len(frame), sha256=sha256(folder / name)))
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    processed, _ = build(root, START, END)
    # Existing notebook evidence must remain byte-for-byte intact.
    (processed / "calendar_audit_v1").mkdir()
    (processed / "calendar_audit_v1" / "audit_record.json").write_text('{"old":true}', encoding="utf-8")
    return processed


class EvidenceDB:
    def __init__(self):
        self.closed = False
        self.queries = []

    def raw_sql(self, query, params=None):
        self.queries.append((query, params))
        if "LIMIT 0" in query:
            return pd.DataFrame(columns=["date", "permno", "ret", "retx"])
        if "FROM crsp.dsi" in query:
            return pd.DataFrame({"trading_date": pd.date_range(START, END)})
        assert "WHERE permno IN (1)" in query
        # MIN/MAX are unbounded: the date restriction belongs only to SUM(CASE).
        assert "WHERE date BETWEEN" not in query
        return pd.DataFrame([dict(permno=1, first_date=START, last_date=END,
                                  window_rows=4, first_ret=None, first_retx=None)])

    def close(self):
        self.closed = True


def test_roundtrip_replay_preservation_and_no_overwrite(tmp_path):
    processed = fixture_data(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    db = EvidenceDB()
    output, summary = run(tmp_path, START, END, "first", connect_factory=lambda: db)
    assert db.closed
    assert summary["quote_status_counts"] == {"NORMAL": 2, "LOCKED": 1, "CROSSED": 1}
    assert summary["quality_status"] == "documented_with_usage_restrictions"
    assert summary["returns"]["unresolved_rows"] == 0
    assert summary["calendar_status"] == "pass"
    assert all(p.read_bytes() == content for p, content in before.items())
    derived = pd.read_csv(output / "stock_daily_analysis.csv")
    original = pd.read_csv(processed / "stock_daily.csv")
    pd.testing.assert_frame_equal(derived[original.columns], original)
    assert derived.loc[1:2, "quoted_spread_bps_main"].isna().all()
    assert derived.loc[1, "quoted_spread_bps_with_locked"] == 0
    assert pd.isna(derived.loc[2, "quoted_spread_bps_with_locked"])
    assert derived.loc[2, "quoted_spread_signed"] == -1
    def no_connection():
        raise AssertionError("Offline replay/overwrite must not connect")
    replay, replay_summary = run(tmp_path, START, END, "second", output, no_connection)
    assert replay_summary == summary
    for name in ["stock_daily_analysis.csv", "quote_sensitivity.csv", "coverage_by_security.csv"]:
        pd.testing.assert_frame_equal(pd.read_csv(output / name), pd.read_csv(replay / name))
    with pytest.raises(FileExistsError):
        run(tmp_path, START, END, "first", connect_factory=no_connection)
    assert all(p.read_bytes() == content for p, content in before.items())


def test_calendar_detects_same_count_gap_duplicate_and_trailing_gap():
    pilot = pd.DataFrame([dict(permno=1, pilot_ticker="TEST")])
    calendar = pd.DataFrame({"trading_date": pd.date_range(START, END)})
    coverage = pd.DataFrame([dict(permno=1, first_date=START, last_date=END, window_rows=4)])
    daily = pd.DataFrame({"permno": [1] * 4, "date": [START, START, "2020-12-22", "2020-12-23"]})
    summary, exceptions = calendar_audit(daily, pilot, calendar, coverage, START, END)
    assert summary.iloc[0]["expected_dates"] == summary.iloc[0]["observed_rows"] == 4
    assert summary.iloc[0]["missing_dates"] == summary.iloc[0]["duplicate_dates"] == 1
    assert set(exceptions["issue"]) == {"MISSING_DATE", "DUPLICATE_DATE"}
    assert "2020-12-24" in exceptions["date"].tolist()
    # Source first date, not local MIN(date), determines the lower boundary.
    summary, _ = calendar_audit(daily.iloc[2:], pilot, calendar, coverage, START, END)
    assert summary.iloc[0]["missing_dates"] == 2


def test_later_listing_and_unexpected_date():
    pilot = pd.DataFrame([dict(permno=1, pilot_ticker="TEST")])
    calendar = pd.DataFrame({"trading_date": pd.date_range(START, END)})
    coverage = pd.DataFrame([dict(permno=1, first_date="2020-12-23", last_date=END, window_rows=2)])
    daily = pd.DataFrame({"permno": [1, 1], "date": ["2020-12-23", END]})
    summary, exceptions = calendar_audit(daily, pilot, calendar, coverage, START, END)
    assert summary.iloc[0]["expected_dates"] == 2 and exceptions.empty
    daily.loc[1, "date"] = "2020-12-26"
    _, exceptions = calendar_audit(daily, pilot, calendar, coverage, START, END)
    assert set(exceptions["issue"]) == {"MISSING_DATE", "UNEXPECTED_DATE"}


def test_return_missing_codes_and_nonfirst_missing_are_not_silently_resolved():
    daily = pd.DataFrame(dict(permno=[1, 1, 1], date=[START, "2020-12-22", "2020-12-23"],
                              ret=[-66, None, .01], retx=[None, .01, .01]))
    coverage = pd.DataFrame([dict(permno=1, first_date=START, first_ret=None, first_retx=None)])
    evidence, result = return_audit(daily, coverage)
    assert evidence["resolution"].tolist() == ["SOURCE_FIRST_OBSERVATION_MISSING", "REVIEW_REQUIRED"]
    assert result["unresolved_rows"] == 1 and not result["same_missing_rows"]
    assert daily.iloc[0]["ret"] == -66
    empty, result = return_audit(daily.iloc[[2]], coverage)
    assert empty.empty and result["ret_missing_or_code"] == 0


def test_invalid_quotes_and_all_excluded_group():
    daily = pd.DataFrame(dict(pilot_ticker=["TEST"] * 5, bid=[0, -1, float("inf"), None, 100],
                              ask=[0, 1, 1, 1, 100]))
    analysis, sensitivity = quote_analysis(daily)
    assert analysis["quote_status"].tolist() == ["INVALID_OR_MISSING"] * 4 + ["LOCKED"]
    assert analysis["quoted_spread_bps_main"].isna().all()
    assert sensitivity.iloc[0]["mean_with_locked_bps"] == 0
    assert pd.isna(sensitivity.iloc[0]["mean_main_bps"])


@pytest.mark.parametrize("target", ["raw", "processed", "replay"])
def test_tamper_detection(tmp_path, target):
    processed = fixture_data(tmp_path)
    if target == "replay":
        output, _ = run(tmp_path, START, END, "first", connect_factory=EvidenceDB)
        with (output / "trading_calendar.csv").open("a") as stream:
            stream.write("2020-12-25\n")
        with pytest.raises(ValueError, match="hash mismatch"):
            run(tmp_path, START, END, "replay", output)
        failed = processed / "repro_audits" / "replay"
        assert (failed / "failure.json").exists()
        assert not (failed / "audit_manifest.json").exists()
    elif target == "raw":
        with (raw_folder(tmp_path, START, END) / "daily_2020.csv").open("a") as stream:
            stream.write("\n")
        with pytest.raises(ValueError, match="checksum mismatch"):
            load_inputs(tmp_path, START, END)
    else:
        daily = pd.read_csv(processed / "stock_daily.csv")
        daily.loc[0, "prc"] = 999
        daily.to_csv(processed / "stock_daily.csv", index=False)
        with pytest.raises(AssertionError):
            load_inputs(tmp_path, START, END)


def test_failed_live_query_closes_connection_and_never_marks_complete(tmp_path):
    processed = fixture_data(tmp_path)
    class FailureDB(EvidenceDB):
        def raw_sql(self, query, params=None):
            raise RuntimeError("Fictional permission error")
    db = FailureDB()
    with pytest.raises(RuntimeError, match="permission"):
        run(tmp_path, START, END, "failed", connect_factory=lambda: db)
    assert db.closed
    assert not (processed / "repro_audits" / "failed" / "audit_manifest.json").exists()
    assert (processed / "repro_audits" / "failed" / "failure.json").exists()


def test_source_count_drift_requires_review(tmp_path):
    fixture_data(tmp_path)
    class ChangedDB(EvidenceDB):
        def raw_sql(self, query, params=None):
            frame = super().raw_sql(query, params)
            if "window_rows" in frame:
                frame.loc[0, "window_rows"] = 3
            return frame
    _, summary = run(tmp_path, START, END, "drift", connect_factory=ChangedDB)
    assert summary["calendar_status"] == "review_required"
    assert summary["quality_status"] == "review_required"


def test_invalid_calendar_and_run_id_fail(tmp_path):
    pilot = pd.DataFrame([dict(permno=1, pilot_ticker="TEST")])
    with pytest.raises(ValueError, match="Calendar"):
        validate_evidence(pd.DataFrame({"trading_date": [START, START]}), pd.DataFrame(), pilot, START, END)
    with pytest.raises(ValueError, match="run-id"):
        run(tmp_path, START, END, "../outside")
