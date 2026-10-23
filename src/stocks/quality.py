"""Adapted from Loki's market-data-quality-demo (MIT), for legacy CRSP daily data.

Preserve inputs and attach traceable row flags. Daily records have no event clock.
Negative CRSP prc denotes a bid/ask average, not a negative economic price.
"""
from __future__ import annotations

import math

import pandas as pd


def require(frame, columns, label):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns {missing}")


def numeric(series):
    def parse(value):
        if isinstance(value, bool):
            return float("nan")
        try:
            result = float(value)
            return result if math.isfinite(result) else float("nan")
        except (ValueError, TypeError, OverflowError):
            return float("nan")
    return series.map(parse)


def dates(series):
    # CRSP DATE fields are date-only. Do not guess timezones or numeric epochs.
    text = series.astype("string")
    valid_shape = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}").fillna(False)
    return pd.to_datetime(text.where(valid_shape), format="%Y-%m-%d", errors="coerce")


def intervals(frame, start, end, label):
    require(frame, ["permno", start, end], label)
    out = frame.copy(deep=True).reset_index(drop=True)
    out["permno"] = numeric(out["permno"])
    lo, hi = dates(out[start]), dates(out[end])
    open_end = out[end].isna() | out[end].astype("string").eq("").fillna(False)
    bad_id = out["permno"].isna() | out["permno"].le(0) | out["permno"].mod(1).ne(0)
    bad = bad_id | lo.isna() | (~open_end & hi.isna()) | (hi.notna() & hi.lt(lo))
    if bad.any():
        rows = (out.index[bad] + 2).tolist()
        raise ValueError(f"{label}: invalid identifier/date intervals at CSV lines {rows[:20]}")
    out["_start"] = lo
    out["_end"] = hi.where(~open_end, pd.Timestamp.max.normalize())
    return out


def audit_daily(raw, names, membership, pilot, start, end):
    require(raw, ["permno", "date", "prc", "vol", "ret", "retx", "cfacpr", "cfacshr"], "daily")
    require(names, ["ticker", "shrcd"], "names")
    require(pilot, ["pilot_ticker", "permno"], "pilot securities")
    if raw.empty:
        raise ValueError("Empty daily sample is not a quality pass")
    if not raw.columns.is_unique:
        raise ValueError("Duplicate daily column names")
    out = raw.copy(deep=True).reset_index(drop=True)
    # The pull/build adds source_file and source_row; standalone calls still get a line.
    if "source_row" not in out:
        out["source_row"] = range(2, len(out) + 2)
    if "source_file" not in out:
        out["source_file"] = "supplied_dataframe"
    flags = [[] for _ in range(len(out))]
    diagnostics = [[] for _ in range(len(out))]

    def mark(mask, code, diagnostic=False):
        target = diagnostics if diagnostic else flags
        for i in out.index[mask.fillna(False)]:
            target[i].append(code)

    ids, day = numeric(out["permno"]), dates(out["date"])
    valid_id = ids.notna() & ids.gt(0) & ids.mod(1).eq(0)
    valid_key = valid_id & day.notna()
    keys = pd.DataFrame({"permno": ids, "date": day})
    mark(~valid_id, "INVALID_PERMNO")
    mark(day.isna(), "INVALID_DATE")
    mark(day.notna() & ~day.between(pd.Timestamp(start), pd.Timestamp(end)), "OUTSIDE_WINDOW")
    mark(keys.duplicated(keep=False) & valid_key, "DUPLICATE_KEY")
    price, volume = numeric(out["prc"]), numeric(out["vol"])
    mark(price.isna() | price.eq(0), "INVALID_PRICE")
    mark(price.lt(0), "PRICE_IS_BID_ASK_AVERAGE", True)
    # Legacy CRSP exports may retain numeric missing codes rather than SQL NULL.
    mark(volume.eq(-99), "VOLUME_MISSING_CODE", True)
    mark(volume.lt(0) & ~volume.eq(-99), "NEGATIVE_VOLUME")
    mark(volume.isna(), "MISSING_VOLUME", True)
    mark(volume.eq(0), "ZERO_VOLUME", True)
    out["price_abs"] = price.abs()
    out["price_is_bid_ask_average"] = price.lt(0)
    for col in ["ret", "retx"]:
        value = numeric(out[col])
        missing_code = value.isin([-44, -55, -66, -77, -88, -99])
        mark(value.isna(), f"MISSING_{col.upper()}", True)
        mark(missing_code, f"{col.upper()}_MISSING_CODE", True)
        mark(value.lt(-1) & ~missing_code, f"INVALID_{col.upper()}")
    for col in ["cfacpr", "cfacshr"]:
        value = numeric(out[col])
        mark(value.isna() | value.le(0), f"INVALID_{col.upper()}")
    if "bid" in out and "ask" in out:
        bid, ask = numeric(out["bid"]), numeric(out["ask"])
        present = bid.notna() & ask.notna()
        mark(~present, "MISSING_BID_ASK", True)
        mark(bid.lt(0) | ask.lt(0), "NEGATIVE_BID_ASK")
        mark(present & bid.gt(ask), "CROSSED_QUOTE")
        mark(present & (bid.eq(0) | ask.eq(0)), "ZERO_BID_ASK", True)
        mark(present & bid.eq(ask), "LOCKED_QUOTE", True)
    elif "bid" in out or "ask" in out:
        raise ValueError("Both genuine bid and ask columns are needed; never substitute bidlo/askhi")
    else:
        mark(pd.Series(True, index=out.index), "BID_ASK_UNAVAILABLE", True)

    nm = intervals(names, "namedt", "nameenddt", "names")
    mem = intervals(membership, "start", "ending", "membership")
    pids = numeric(pilot["permno"])
    if (pids.isna() | pids.le(0) | pids.mod(1).ne(0)).any() or pids.duplicated().any():
        raise ValueError("Pilot securities must have valid, unique permnos")
    labels = dict(zip(pids, pilot["pilot_ticker"]))
    out["pilot_ticker"] = ids.map(labels)
    mark(out["pilot_ticker"].isna(), "OUTSIDE_PILOT")
    name_counts, member_counts, historical_tickers = [], [], []
    for security, date in zip(ids, day):
        active_names = nm[nm["permno"].eq(security) & nm["_start"].le(date) & nm["_end"].ge(date)]
        active_members = mem[mem["permno"].eq(security) & mem["_start"].le(date) & mem["_end"].ge(date)]
        name_counts.append(len(active_names))
        member_counts.append(len(active_members))
        historical_tickers.append(active_names.iloc[0]["ticker"] if len(active_names) == 1 else None)
        if len(active_names) == 1:
            if pd.isna(active_names.iloc[0]["ticker"]) or not str(active_names.iloc[0]["ticker"]).strip():
                flags[len(name_counts) - 1].append("MISSING_HISTORICAL_TICKER")
            if numeric(active_names["shrcd"]).iloc[0] not in [10, 11]:
                flags[len(name_counts) - 1].append("NOT_COMMON_STOCK")
    out["historical_ticker"] = historical_tickers
    out["name_match_count"] = name_counts
    out["membership_match_count"] = member_counts
    out["in_sp500"] = pd.array([n > 0 if key else pd.NA for n, key in zip(member_counts, valid_key)], dtype="boolean")
    mark(out["name_match_count"].eq(0), "NO_DATED_NAME")
    mark(out["name_match_count"].gt(1), "AMBIGUOUS_DATED_NAME")
    mark(out["membership_match_count"].gt(1), "OVERLAPPING_MEMBERSHIP")
    mark(valid_key & out["membership_match_count"].eq(0), "OUTSIDE_SP500", True)
    out["core_flags"] = [";".join(row) for row in flags]
    out["diagnostic_flags"] = [";".join(row) for row in diagnostics]
    # No input row is dropped, repaired, deduplicated or selected as a winner.
    return out
