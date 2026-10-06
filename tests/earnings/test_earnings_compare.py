import pandas as pd

from src.earnings.compare import build, summarize


def comp_frame():
    return pd.DataFrame({
        "tic": ["AAA", "AAA", "AAA", "AAA", "BBB"],
        "gvkey": ["000001"] * 4 + ["000002"],
        "datadate": ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31", "2020-03-28"],
        "rdq": ["2020-04-30", "2020-07-30", "2020-10-28", None, "2020-04-22"],
        "fyearq": [2020] * 5,
        "fqtr": [1, 2, 3, 4, 1],
    })


def ibes_frame():
    return pd.DataFrame({
        "oftic": ["AAA", "AAA", "AAA", "AAA", "BBB", "BBB", "CCC"],
        "pends": ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31", "2020-03-31", "2020-03-31", "2020-03-31"],
        # same day, off by one (AMC), differs by days, ibes only, matched within tolerance,
        # a later revision that must be dropped, and a ticker Compustat does not have
        "anndats": ["2020-04-30", "2020-07-29", "2020-10-20", "2021-02-02", "2020-04-22", "2020-05-30", "2020-04-15"],
        "anntims": ["07:00:00", "16:30:00", "00:00:00", "16:10:00", "08:00:00", "10:00:00", "12:00:00"],
    })


def test_status_labels():
    out = build(comp_frame(), ibes_frame())
    aaa = out[out["ticker"] == "AAA"].set_index("period_end")["status"]
    assert aaa[pd.Timestamp("2020-03-31")] == "same_day"
    assert aaa[pd.Timestamp("2020-06-30")] == "off_by_one_day"
    assert aaa[pd.Timestamp("2020-09-30")] == "differs_by_more"
    assert aaa[pd.Timestamp("2020-12-31")] == "ibes_only"


def test_fuzzy_period_end_and_revision_dedupe():
    out = build(comp_frame(), ibes_frame())
    bbb = out[out["ticker"] == "BBB"]
    assert len(bbb) == 1  # revision row dropped, 3 day period end gap matched
    assert bbb.iloc[0]["status"] == "same_day"
    assert bbb.iloc[0]["ibes_timing"] == "BMO"


def test_ibes_only_ticker_is_kept():
    out = build(comp_frame(), ibes_frame())
    ccc = out[out["ticker"] == "CCC"]
    assert len(ccc) == 1 and ccc.iloc[0]["status"] == "ibes_only"


def test_timing_buckets():
    out = build(comp_frame(), ibes_frame()).set_index(["ticker", "period_end"])
    assert out.loc[("AAA", pd.Timestamp("2020-06-30")), "ibes_timing"] == "AMC"
    assert out.loc[("AAA", pd.Timestamp("2020-09-30")), "ibes_timing"] == "UNKNOWN"


def test_summary_runs_and_counts_rows():
    out = build(comp_frame(), ibes_frame())
    text = summarize(out)
    assert f"Rows (ticker and fiscal period): {len(out)}" in text
    assert "same_day" in text and "Coverage by fiscal year" in text
