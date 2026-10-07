"""Compare earnings dates from Compustat and I/B/E/S, offline from data/raw.

    python -m src.earnings.compare

Compustat gives the report date (rdq) with no time of day. I/B/E/S gives an announce date and a
time of day. This script matches the two by ticker and fiscal period end, labels how they agree,
and buckets the I/B/E/S time into BMO, DURING, AMC or UNKNOWN. The disagreement rate is the
motivation for the LLM step on press releases.

Outputs in data/processed/earnings:
    earnings_dates_compare.csv        one row per ticker and fiscal period
    earnings_compare_summary.md       counts and coverage, ready to quote in the setup card
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..common import config
from ..common.io_utils import read_raw, write_processed
from ..common.timing import classify_timing, to_seconds

AREA = "earnings"
STATUS_ORDER = ["same_day", "off_by_one_day", "differs_by_more", "compustat_only", "ibes_only", "neither"]


def _to_ns(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").astype("datetime64[ns]")


def prep_compustat(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.rename(columns={"tic": "ticker"}).copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["period_end"] = _to_ns(out["datadate"])
    out["rdq"] = _to_ns(out["rdq"])
    keep = [c for c in ["ticker", "gvkey", "cik", "conm", "fyearq", "fqtr", "period_end", "rdq"] if c in out.columns]
    return out.dropna(subset=["period_end"])[keep].reset_index(drop=True)


def prep_ibes(raw: pd.DataFrame) -> pd.DataFrame:
    # Raw I/B/E/S already has its own internal "ticker" column. Use the official ticker, oftic, instead.
    out = raw.drop(columns=["ticker"], errors="ignore").rename(columns={"oftic": "ticker"}).copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["ibes_period_end"] = _to_ns(out["pends"])
    out["ibes_anndats"] = _to_ns(out["anndats"])
    out["ibes_time_s"] = out["anntims"].map(to_seconds) if "anntims" in out.columns else np.nan
    out["ibes_timing"] = out["ibes_time_s"].map(classify_timing)
    out = out.dropna(subset=["ibes_period_end"])
    # Keep the earliest announcement per ticker and period. Later rows are revisions.
    out = (out.sort_values(["ticker", "ibes_period_end", "ibes_anndats", "ibes_time_s"])
              .drop_duplicates(["ticker", "ibes_period_end"], keep="first"))
    keep = ["ticker", "ibes_period_end", "ibes_anndats", "ibes_time_s", "ibes_timing"]
    return out[keep].reset_index(drop=True)


def match_periods(comp: pd.DataFrame, ibes: pd.DataFrame, tolerance_days: int = 7) -> pd.DataFrame:
    """Match each Compustat period to the nearest I/B/E/S period for the same ticker.

    Fiscal period ends can differ by a few days between vendors (52 and 53 week years), hence
    the tolerance. I/B/E/S rows with no Compustat partner are kept as ibes_only.
    """
    comp = comp.sort_values("period_end").reset_index(drop=True)
    ibes = ibes.sort_values("ibes_period_end").reset_index(drop=True)
    ibes["ibes_row"] = ibes.index

    merged = pd.merge_asof(
        comp, ibes,
        left_on="period_end", right_on="ibes_period_end", by="ticker",
        direction="nearest", tolerance=pd.Timedelta(days=tolerance_days),
    )
    used = set(merged["ibes_row"].dropna().astype(int))
    extra = ibes[~ibes["ibes_row"].isin(used)].copy()
    if len(extra):
        extra["period_end"] = extra["ibes_period_end"]
        merged = pd.concat([merged, extra], ignore_index=True)
    return merged.drop(columns=["ibes_row"])


def label_agreement(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    diff = (out["rdq"] - out["ibes_anndats"]).dt.days
    out["diff_days"] = diff
    conditions = [
        out["rdq"].isna() & out["ibes_anndats"].notna(),
        out["ibes_anndats"].isna() & out["rdq"].notna(),
        diff == 0,
        diff.abs() == 1,
        diff.abs() > 1,
    ]
    choices = ["ibes_only", "compustat_only", "same_day", "off_by_one_day", "differs_by_more"]
    out["status"] = np.select(conditions, choices, default="neither")
    out["ibes_timing"] = out["ibes_timing"].fillna("NO_IBES")
    return out.sort_values(["ticker", "period_end"]).reset_index(drop=True)


def summarize(df: pd.DataFrame) -> str:
    n = len(df)
    lines = ["# Earnings dates: Compustat vs I/B/E/S", "",
             f"Rows (ticker and fiscal period): {n}",
             f"Tickers: {df['ticker'].nunique()}",
             f"Period range: {df['period_end'].min():%Y/%m/%d} to {df['period_end'].max():%Y/%m/%d}", "",
             "## Agreement", "", "| Status | Rows | Share |", "| --- | --- | --- |"]
    counts = df["status"].value_counts()
    for status in STATUS_ORDER:
        c = int(counts.get(status, 0))
        lines.append(f"| {status} | {c} | {c / n:.1%} |" if n else f"| {status} | 0 | n/a |")

    both = df[df["status"].isin(["same_day", "off_by_one_day", "differs_by_more"])]
    if len(both):
        lines += ["", f"Of {len(both)} periods with both dates, {(both['status'] == 'same_day').mean():.1%} match "
                      "on the same day."]

    lines += ["", "## I/B/E/S time of day bucket by agreement status", ""]
    table = pd.crosstab(df["status"], df["ibes_timing"])
    lines.append("| Status | " + " | ".join(table.columns) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in table.columns) + " |")
    for status in [s for s in STATUS_ORDER if s in table.index]:
        lines.append(f"| {status} | " + " | ".join(str(int(v)) for v in table.loc[status]) + " |")

    by_year = df.assign(year=df["period_end"].dt.year).groupby("year").agg(
        periods=("status", "size"),
        compustat_date_share=("rdq", lambda s: s.notna().mean()),
        ibes_date_share=("ibes_anndats", lambda s: s.notna().mean()),
        ibes_time_known_share=("ibes_timing", lambda s: s.isin(["BMO", "DURING", "AMC"]).mean()),
    )
    lines += ["", "## Coverage by fiscal year", "",
              "| Year | Periods | Compustat date | I/B/E/S date | I/B/E/S time known |",
              "| --- | --- | --- | --- | --- |"]
    for year, r in by_year.iterrows():
        lines.append(f"| {year} | {int(r['periods'])} | {r['compustat_date_share']:.0%} | "
                     f"{r['ibes_date_share']:.0%} | {r['ibes_time_known_share']:.0%} |")
    return "\n".join(lines) + "\n"


def build(comp_raw: pd.DataFrame, ibes_raw: pd.DataFrame) -> pd.DataFrame:
    return label_agreement(match_periods(prep_compustat(comp_raw), prep_ibes(ibes_raw)))


def main() -> None:
    comp_raw = read_raw("compustat_fundq_pilot", AREA, dtype={"gvkey": str, "cik": str})
    ibes_raw = read_raw("ibes_actu_epsus_pilot", AREA, dtype={"cusip": str})
    result = build(comp_raw, ibes_raw)
    path = write_processed(result, "earnings_dates_compare", AREA)
    summary = summarize(result)
    (config.processed_dir(AREA) / "earnings_compare_summary.md").write_text(summary)
    print(summary)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
