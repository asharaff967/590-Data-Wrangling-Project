"""Fictional records only. No licensed samples, account access or network calls."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pandas as pd
import pytest

from src.stocks.build import build
from src.stocks.pull import TABLES, preflight, pull, resolve_seeds
from src.stocks.quality import audit_daily


@pytest.mark.parametrize("start_folder", [".", "notebooks"])
def test_notebook_bootstrap_imports_project_after_kernel_restart(start_folder):
    repo = Path(__file__).resolve().parents[2]
    notebook = json.loads((repo / "notebooks/stocks_pilot_wrds.ipynb").read_text())
    setup = next("".join(c["source"]) for c in notebook["cells"]
                 if "".join(c["source"]).startswith("from pathlib import Path"))
    # Model a fresh kernel with an absolute startup path and no project entry.
    # A chdir alone cannot fix imports in this supported launch scenario.
    script = """import sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve()
sys.path = [str(repo / 'notebooks')] + [p for p in sys.path
    if p and Path(p).resolve() not in {repo, repo / 'notebooks'}]
exec(sys.argv[2])
import src.stocks.history_audit
assert Path.cwd() == repo
"""
    subprocess.run([sys.executable, "-c", script, str(repo), setup],
                   cwd=repo / start_folder, capture_output=True, text=True,
                   check=True, timeout=30)


def test_notebook_refuses_to_build_over_existing_outputs(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    notebook = json.loads((repo / "notebooks/stocks_pilot_wrds.ipynb").read_text())
    cell = next("".join(c["source"]) for c in notebook["cells"]
                if "".join(c["source"]).startswith("from src.stocks.build import build"))
    existing = tmp_path / "processed/stocks/2020-12-01_2020-12-31"
    existing.mkdir(parents=True)
    marker = existing / "saved-evidence.txt"
    marker.write_text("fictional preservation marker", encoding="utf-8")
    with patch("src.stocks.build.build") as mocked:
        with pytest.raises(FileExistsError, match="Processed output already exists"):
            exec(cell, {"DATA_ROOT": tmp_path, "START": "2020-12-01", "END": "2020-12-31"})
        mocked.assert_not_called()
    assert marker.read_text(encoding="utf-8") == "fictional preservation marker"


def row(**kwargs):
    result = dict(permno=1, date="2020-12-21", prc=100, vol=1000, ret=.01,
                  retx=.01, cfacpr=1, cfacshr=1, bid=99, ask=101)
    result.update(kwargs)
    return result


def inputs():
    names = pd.DataFrame([
        dict(permno=1, ticker="OLD", namedt="2010-01-01", nameenddt="2020-12-20", shrcd=11),
        dict(permno=1, ticker="NEW", namedt="2020-12-21", nameenddt=None, shrcd=11),
    ])
    membership = pd.DataFrame([dict(permno=1, start="2020-12-21", ending=None)])
    pilot = pd.DataFrame([dict(pilot_ticker="NEW", permno=1)])
    return names, membership, pilot


def audit(rows, frames=None):
    return audit_daily(pd.DataFrame(rows), *(frames or inputs()), "2020-12-01", "2020-12-31")


def test_negative_crsp_price_is_diagnostic_and_raw_unchanged():
    original = pd.DataFrame([row(prc=-100, vol=0, ret=None)])
    saved = original.copy(deep=True)
    result = audit_daily(original, *inputs(), "2020-12-01", "2020-12-31")
    pd.testing.assert_frame_equal(original, saved)
    assert result.iloc[0]["core_flags"] == ""
    assert result.iloc[0]["price_abs"] == 100
    assert "PRICE_IS_BID_ASK_AVERAGE" in result.iloc[0]["diagnostic_flags"]
    assert "ZERO_VOLUME" in result.iloc[0]["diagnostic_flags"]


def test_dates_use_historical_ticker_and_membership_inclusive_boundaries():
    result = audit([row(date="2020-12-20"), row(), row(date="2020-12-22")])
    assert result["historical_ticker"].tolist() == ["OLD", "NEW", "NEW"]
    assert result["in_sp500"].tolist() == [False, True, True]
    names, member, pilot = inputs()
    member["ending"] = "2020-12-21"
    result = audit([row(), row(date="2020-12-22")], (names, member, pilot))
    assert result["in_sp500"].tolist() == [True, False]


def test_duplicate_keys_flag_all_members_without_dropping_or_reordering():
    result = audit([row(), row(prc=102)])
    assert result["prc"].tolist() == [100, 102]
    assert result["core_flags"].str.contains("DUPLICATE_KEY").all()
    assert result["source_row"].tolist() == [2, 3]


@pytest.mark.parametrize("value", [None, 0, float("inf"), True, "bad"])
def test_invalid_prices(value):
    assert "INVALID_PRICE" in audit([row(prc=value)]).iloc[0]["core_flags"]


def test_no_event_clock_checks_and_no_low_high_substitution():
    rows = pd.DataFrame([row(date="2020-12-22"), row(date="2020-12-21")]).drop(columns=["bid", "ask"])
    rows["bidlo"], rows["askhi"] = 120, 80
    result = audit_daily(rows, *inputs(), "2020-12-01", "2020-12-31")
    assert result["core_flags"].eq("").all()
    assert result["diagnostic_flags"].str.contains("BID_ASK_UNAVAILABLE").all()


def test_crossed_quotes_and_missing_analytics_have_different_severity():
    result = audit([row(bid=102, ret=None, retx=None), row(date="2020-12-22", vol=None)])
    assert "CROSSED_QUOTE" in result.iloc[0]["core_flags"]
    assert "MISSING_RET" in result.iloc[0]["diagnostic_flags"]
    assert result.iloc[1]["core_flags"] == ""
    assert "NEGATIVE_BID_ASK" in audit([row(bid=None, ask=-1)]).iloc[0]["core_flags"]


def test_legacy_missing_codes_are_diagnostics_not_economic_returns():
    result = audit([row(vol=-99, ret=-66, retx=-99)])
    assert result.iloc[0]["core_flags"] == ""
    assert "VOLUME_MISSING_CODE" in result.iloc[0]["diagnostic_flags"]
    assert "RET_MISSING_CODE" in result.iloc[0]["diagnostic_flags"]


def test_missing_entire_security_and_empty_membership_are_explicit(tmp_path):
    folder = pull(FakeWRDS(), tmp_path, "2020-12-01", "2020-12-31", ["NEW"])
    # Feed a second resolved pilot security with no daily observations.
    pilot_path = folder / "pilot_securities.csv"
    # This is a fictional raw-fixture construction, not a licensed data repair.
    pd.DataFrame([dict(pilot_ticker="NEW", permno=1), dict(pilot_ticker="ABSENT", permno=2)]).to_csv(pilot_path, index=False)
    from src.stocks.pull import sha256
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        if entry["name"] == "pilot_securities.csv":
            entry.update(rows=2, sha256=sha256(pilot_path))
    manifest_path.write_text(json.dumps(manifest))
    _, report = build(tmp_path, "2020-12-01", "2020-12-31")
    assert report["missing_pilot_tickers"] == ["ABSENT"]
    names, membership, pilot = inputs()
    result = audit([row()], (names, membership.iloc[:0], pilot))
    assert result["in_sp500"].tolist() == [False]


def test_overlapping_links_do_not_multiply_rows_or_pick_a_winner():
    names, member, pilot = inputs()
    names = pd.concat([names, names.iloc[[1]]], ignore_index=True)
    member = pd.concat([member, member], ignore_index=True)
    result = audit([row()], (names, member, pilot))
    assert len(result) == 1
    assert result.iloc[0]["historical_ticker"] is None
    assert "AMBIGUOUS_DATED_NAME" in result.iloc[0]["core_flags"]
    assert "OVERLAPPING_MEMBERSHIP" in result.iloc[0]["core_flags"]


def test_invalid_dates_are_not_treated_as_open_intervals():
    names, member, pilot = inputs()
    member.loc[0, "ending"] = "bad"
    with pytest.raises(ValueError, match="invalid identifier/date intervals"):
        audit([row()], (names, member, pilot))
    result = audit([row(date="bad"), row(permno=1.5), row(permno=True)])
    assert "INVALID_DATE" in result.iloc[0]["core_flags"]
    assert pd.isna(result.iloc[0]["in_sp500"])
    assert result["core_flags"].iloc[1:].str.contains("INVALID_PERMNO").all()


def test_empty_and_missing_schema_fail():
    with pytest.raises(ValueError):
        audit([])
    with pytest.raises(ValueError, match="Empty daily"):
        audit_daily(pd.DataFrame(columns=row()), *inputs(), "2020-12-01", "2020-12-31")


def test_seed_lookup_rejects_reused_tickers():
    seed = pd.DataFrame([dict(ticker="NEW", permno=1, shrcd=11), dict(ticker="NEW", permno=2, shrcd=11)])
    with pytest.raises(ValueError, match="Human review required"):
        resolve_seeds(seed, ["NEW"])


def test_seed_anchor_selects_active_security_without_changing_source():
    seed = pd.DataFrame([
        dict(ticker="NEW", permno=99, shrcd=11, namedt="1990-01-01", nameenddt="2000-12-31"),
        dict(ticker="NEW", permno=1, shrcd=11, namedt="2020-01-01", nameenddt="2024-12-31"),
    ])
    original = seed.copy(deep=True)
    assert resolve_seeds(seed, ["NEW"], as_of="2024-06-30")["permno"].tolist() == [1]
    assert resolve_seeds(seed, ["NEW"], as_of="2000-12-31")["permno"].tolist() == [99]
    pd.testing.assert_frame_equal(seed, original)
    with pytest.raises(ValueError, match="Human review required"):
        resolve_seeds(seed, ["NEW"], as_of="2010-01-01")


def test_seed_anchor_still_rejects_simultaneous_candidates_and_invalid_dates():
    seed = pd.DataFrame([
        dict(ticker="NEW", permno=1, shrcd=11, namedt="2020-01-01", nameenddt=None),
        dict(ticker="NEW", permno=2, shrcd=11, namedt="2020-01-01", nameenddt=None),
    ])
    with pytest.raises(ValueError, match="Human review required"):
        resolve_seeds(seed, ["NEW"], as_of="2024-06-30")
    seed.loc[1, "nameenddt"] = "bad"
    with pytest.raises(ValueError, match="invalid identifier/date intervals"):
        resolve_seeds(seed, ["NEW"], as_of="2024-06-30")


def test_pull_records_explicit_seed_anchor_and_recovers_old_name_history(tmp_path):
    folder = pull(FakeWRDS(), tmp_path, "2020-12-01", "2020-12-20", ["NEW"],
                  universe_asof="2020-12-31")
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["universe_asof"] == "2020-12-31"
    assert pd.read_csv(folder / "names.csv")["ticker"].tolist() == ["OLD", "NEW"]


class FakeWRDS:
    """Simulates SQL results, not real CRSP securities or coverage."""
    def __init__(self):
        self.queries = []

    def raw_sql(self, query):
        self.queries.append(query)
        if query.endswith("limit 0"):
            table = query.split("crsp.")[1].split()[0]
            return pd.DataFrame(columns=TABLES[table] + (["bid", "ask"] if table == "dsf" else []))
        names, membership, pilot = inputs()
        if "where ticker in" in query:
            return names[names["ticker"].eq("NEW")].copy()
        if "crsp.stocknames" in query:
            return names
        if "crsp.dsp500list" in query:
            return membership
        if "crsp.dsf" in query:
            return pd.DataFrame([row(date="2020-12-20"), row(), row(prc=-100, vol=0)])
        raise AssertionError(query)


def test_pull_build_roundtrip_raw_integrity_and_duplicate_traceability(tmp_path):
    db = FakeWRDS()
    folder = pull(db, tmp_path, "2020-12-01", "2020-12-31", ["NEW"])
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert len([q for q in db.queries if "crsp.dsf where" in q]) == 1
    assert "where permno in (1)" in db.queries[-1]
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    output, report = build(tmp_path, "2020-12-01", "2020-12-31")
    assert report["rows"] == 3
    assert report["core_flag_counts"]["DUPLICATE_KEY"] == 2
    daily = pd.read_csv(output / "stock_daily.csv")
    assert daily["historical_ticker"].tolist() == ["OLD", "NEW", "NEW"]
    assert daily["source_file"].eq("daily_2020.csv").all()
    assert daily["source_row"].tolist() == [2, 3, 4]
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(FileExistsError):
        pull(db, tmp_path, "2020-12-01", "2020-12-31", ["NEW"])
    with (folder / "daily_2020.csv").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        build(tmp_path, "2020-12-01", "2020-12-31")


def test_schema_check_fails_loudly_and_partial_run_is_not_a_pass(tmp_path):
    class WrongSchema(FakeWRDS):
        def raw_sql(self, query):
            return pd.DataFrame(columns=["permno", "dlycaldt", "dlyprc"])
    with pytest.raises(ValueError, match="missing legacy columns"):
        preflight(WrongSchema())
    class FailedQuery(FakeWRDS):
        def raw_sql(self, query):
            if "crsp.dsf where" in query:
                raise RuntimeError("Simulated source permission error")
            return super().raw_sql(query)
    with pytest.raises(RuntimeError, match="Simulated source permission"):
        pull(FailedQuery(), tmp_path, "2020-12-01", "2020-12-31", ["NEW"])
    with pytest.raises(ValueError, match="incomplete"):
        build(tmp_path, "2020-12-01", "2020-12-31")


def test_no_raw_directory_created_for_reversed_window(tmp_path):
    with pytest.raises(ValueError):
        pull(FakeWRDS(), tmp_path, "2021-01-01", "2020-01-01", ["NEW"])
    assert list(tmp_path.iterdir()) == []


def test_cloud_queries_partition_dates_and_only_selected_securities(tmp_path):
    db = FakeWRDS()
    pull(db, tmp_path, "2020-12-15", "2021-01-10", ["NEW"])
    queries = [q for q in db.queries if "crsp.dsf where" in q]
    assert len(queries) == 2
    assert "between '2020-12-15' and '2020-12-31'" in queries[0]
    assert "between '2021-01-01' and '2021-01-10'" in queries[1]
    assert all("where permno in (1)" in q for q in queries)
    assert all("bidlo" not in q and "askhi" not in q for q in queries)


def test_absent_genuine_quotes_are_reported_without_fabrication(tmp_path):
    class NoQuotes(FakeWRDS):
        def raw_sql(self, query):
            frame = super().raw_sql(query)
            if "crsp.dsf" in query:
                return frame.drop(columns=["bid", "ask"])
            return frame
    pull(NoQuotes(), tmp_path, "2020-12-01", "2020-12-31", ["NEW"])
    output, report = build(tmp_path, "2020-12-01", "2020-12-31")
    assert report["diagnostic_counts"]["BID_ASK_UNAVAILABLE"] == 3
    assert "bid" not in pd.read_csv(output / "stock_daily.csv").columns
