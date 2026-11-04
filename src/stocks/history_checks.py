"""Pure dataframe checks used by the stocks history audit.

No file writes, database connections or source queries occur here. These checks
retain original rows and distinguish quoted-spread eligibility from row quality.
Public imports from history_audit remain available for existing notebooks.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from .quality import numeric, require

RETURN_CODES = [-44, -55, -66, -77, -88, -99]


def flag_counts(series):
    return dict(sorted(Counter(
        code for value in series.fillna("") for code in str(value).split(";") if code
    ).items()))


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
