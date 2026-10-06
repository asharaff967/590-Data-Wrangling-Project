"""Build an ID crosswalk as of one date, offline from data/raw.

    python -m src.integration.crosswalk --as-of 2024-06-28

CRSP permno is the hub. For each pilot ticker this finds the permno that held the ticker on the
as of date, then attaches:
    secid        OptionMetrics, from wrdsapps.opcrsphist (best match score wins)
    gvkey        Compustat, from the CRSP Compustat link history (primary links first)
    ibes_ticker  I/B/E/S, from wrdsapps.ibcrsphist (best match score wins)
    cik          SEC, from the Compustat company table

Every link table has start and end dates, so the join is as of a date. That is what stops a
reused ticker from silently joining two different companies.

The flags column lists anything a human should look at before trusting the row.
"""
from __future__ import annotations

import argparse

import pandas as pd

from ..common import config
from ..common.io_utils import read_raw, write_processed

AREA = "integration"
FAR_FUTURE = pd.Timestamp("2200-01-01")


def require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(f"{name} is missing columns {missing}. Found: {list(df.columns)}")


def active_as_of(df: pd.DataFrame, start_col: str, end_col: str, as_of: pd.Timestamp) -> pd.DataFrame:
    start = pd.to_datetime(df[start_col], errors="coerce")
    end = pd.to_datetime(df[end_col], errors="coerce").fillna(FAR_FUTURE)
    return df[(start <= as_of) & (as_of <= end)]


def best_per_key(df: pd.DataFrame, key: str, sort_cols: list[str], count_name: str) -> pd.DataFrame:
    """Keep the first row per key after sorting, and record how many candidates there were."""
    ordered = df.sort_values(sort_cols)
    counts = ordered.groupby(key).size().rename(count_name)
    return ordered.drop_duplicates(key, keep="first").merge(counts, left_on=key, right_index=True)


def build_crosswalk(names: pd.DataFrame, opcrsp: pd.DataFrame, ccm: pd.DataFrame,
                    ibcrsp: pd.DataFrame, company: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    require_columns(names, ["permno", "ticker", "namedt", "nameenddt"], "crsp.stocknames")
    require_columns(opcrsp, ["secid", "permno", "sdate", "edate", "score"], "wrdsapps.opcrsphist")
    require_columns(ccm, ["gvkey", "lpermno", "linktype", "linkprim", "linkdt", "linkenddt"], "ccmxpf_lnkhist")
    require_columns(ibcrsp, ["ticker", "permno", "sdate", "edate", "score"], "wrdsapps.ibcrsphist")
    require_columns(company, ["gvkey", "cik"], "comp.company")

    nm = active_as_of(names, "namedt", "nameenddt", as_of)
    if "shrcd" in nm.columns:  # keep common stock, drop ETFs, ADRs and the like
        nm = nm[nm["shrcd"].isin([10, 11])]
    nm = nm[[c for c in ["ticker", "permno", "comnam"] if c in nm.columns]].copy()
    nm["permno"] = nm["permno"].astype(int)
    nm["ticker"] = nm["ticker"].astype(str).str.upper()

    op = active_as_of(opcrsp, "sdate", "edate", as_of)
    op = best_per_key(op, "permno", ["permno", "score"], "secid_candidates")
    op = op[["permno", "secid", "score", "secid_candidates"]].rename(columns={"score": "secid_score"})

    cc = active_as_of(ccm, "linkdt", "linkenddt", as_of).copy()
    cc["prim_rank"] = cc["linkprim"].map({"P": 0, "C": 1}).fillna(2)
    cc["type_rank"] = cc["linktype"].map({"LC": 0, "LU": 1}).fillna(2)
    cc = best_per_key(cc, "lpermno", ["lpermno", "prim_rank", "type_rank"], "gvkey_candidates")
    cc = cc.rename(columns={"lpermno": "permno"})[["permno", "gvkey", "gvkey_candidates"]]
    cc["gvkey"] = cc["gvkey"].astype(str).str.zfill(6)

    ib = active_as_of(ibcrsp, "sdate", "edate", as_of)
    ib = best_per_key(ib, "permno", ["permno", "score"], "ibes_candidates")
    ib = ib[["permno", "ticker", "score", "ibes_candidates"]].rename(
        columns={"ticker": "ibes_ticker", "score": "ibes_score"})

    co = company.copy()
    co["gvkey"] = co["gvkey"].astype(str).str.zfill(6)
    co = co.drop_duplicates("gvkey")[["gvkey", "cik"]]

    for frame in (op, cc, ib):
        frame["permno"] = frame["permno"].astype(int)

    out = (nm.merge(op, on="permno", how="left")
             .merge(cc, on="permno", how="left")
             .merge(ib, on="permno", how="left")
             .merge(co, on="gvkey", how="left"))
    out["as_of"] = as_of.date().isoformat()

    def flags(row) -> str:
        found = []
        if pd.isna(row.get("secid")):
            found.append("no_secid")
        elif row.get("secid_score", 1) > 1:
            found.append("weak_secid_match")
        if pd.isna(row.get("gvkey")):
            found.append("no_gvkey")
        if pd.isna(row.get("ibes_ticker")):
            found.append("no_ibes")
        elif row.get("ibes_score", 1) > 1:
            found.append("weak_ibes_match")
        if pd.isna(row.get("cik")):
            found.append("no_cik")
        for col in ("secid_candidates", "gvkey_candidates", "ibes_candidates"):
            if row.get(col, 1) > 1:
                found.append(f"multiple_{col.split('_')[0]}")
        return ";".join(found)

    out["flags"] = out.apply(flags, axis=1)
    return out.sort_values(["ticker", "permno"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", default="2024-06-28", help="date for the point in time join, YYYY-MM-DD")
    args = parser.parse_args()
    as_of = pd.Timestamp(args.as_of)

    result = build_crosswalk(
        names=read_raw("crsp_stocknames_pilot", AREA),
        opcrsp=read_raw("opcrsphist_pilot", AREA),
        ccm=read_raw("ccm_lnkhist_pilot", AREA, dtype={"gvkey": str}),
        ibcrsp=read_raw("ibcrsphist_pilot", AREA),
        company=read_raw("comp_company_pilot", AREA, dtype={"gvkey": str, "cik": str}),
        as_of=as_of,
    )
    path = write_processed(result, "crosswalk_asof", AREA)
    wanted = set(config.load_universe())
    missing = sorted(wanted - set(result["ticker"]))
    print(result.to_string(index=False))
    print(f"\nWrote {path}")
    if missing:
        print(f"No active permno on {args.as_of} for: {', '.join(missing)}")
    flagged = result[result["flags"] != ""]
    if len(flagged):
        print(f"{len(flagged)} rows have flags, review them before using the crosswalk.")


if __name__ == "__main__":
    main()
