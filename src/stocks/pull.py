"""Pull only the configured pilot securities; run this on WRDS JupyterHub/Cloud.

Legacy CRSP schemas are checked before querying. This is not a CIZ adapter.
Raw files are never replaced, and incomplete runs cannot be built.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..common import config
from ..common.io_utils import iso_date, sql_list
from ..common.wrds_conn import connect
from .quality import intervals

TABLES = {
    "stocknames": ["permno", "ticker", "namedt", "nameenddt", "shrcd"],
    "dsp500list": ["permno", "start", "ending"],
    "dsf": ["permno", "date", "prc", "vol", "ret", "retx", "cfacpr", "cfacshr"],
}


def data_root(value=None):
    return Path(value or os.getenv("STOCKS_DATA_ROOT") or config.ROOT / "data").resolve()


def window(start, end):
    start, end = iso_date(start), iso_date(end)
    if start > end:
        raise ValueError("start must be on or before end")
    return start, end


def raw_folder(root, start, end):
    start, end = window(start, end)
    return Path(root) / "raw" / "stocks" / "wrds" / f"{start}_{end}"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight(db):
    schemas = {}
    for table, required in TABLES.items():
        # LIMIT 0 verifies the real columns without exporting source records.
        columns = list(db.raw_sql(f"select * from crsp.{table} limit 0").columns)
        missing = sorted(set(required) - set(columns))
        if missing:
            raise ValueError(f"crsp.{table}: missing legacy columns {missing}; "
                             f"actual columns: {columns}. Confirm the WRDS schema; do not guess a CIZ mapping.")
        schemas[table] = columns
    return schemas


def resolve_seeds(seed, tickers, as_of=None):
    """Ticker chooses a research security; subsequent history is always by permno.

    With as_of, only name intervals active on that explicit date are candidates.
    Several active common-stock permnos remain deliberately unresolved. Without
    a reference date the strict all-history check is retained for compatibility.
    A rename (META/FB) is recovered by fetching *all* names for the resolved permno.
    """
    if as_of is not None:
        reference = pd.Timestamp(iso_date(as_of))
        dated = intervals(seed, "namedt", "nameenddt", "seed_names")
        seed = dated.loc[dated["_start"].le(reference) & dated["_end"].ge(reference)]
    rows = []
    for ticker in tickers:
        found = seed[seed["ticker"].eq(ticker) & seed["shrcd"].isin([10, 11])]
        ids = pd.to_numeric(found["permno"], errors="coerce")
        if ids.isna().any() or ids.le(0).any() or ids.mod(1).ne(0).any():
            raise ValueError(f"Invalid permno in seed lookup for {ticker}")
        candidates = sorted(int(value) for value in ids.unique())
        if len(candidates) != 1:
            scope = f" on {as_of}" if as_of is not None else " across all history"
            raise ValueError(f"Pilot ticker {ticker}{scope}: expected one common-stock permno, "
                             f"found {candidates}. Human review required; no automatic ticker-only choice.")
        rows.append({"pilot_ticker": ticker, "permno": candidates[0]})
    result = pd.DataFrame(rows)
    if result["permno"].duplicated().any():
        raise ValueError("Several pilot labels resolve to one permno; review the universe")
    return result


def pull(db, root, start, end, tickers, universe_asof=None):
    start, end = window(start, end)
    universe_asof = iso_date(universe_asof or end)
    tickers = sorted(set(tickers))
    sql_list(tickers)  # Validate before creating anything or connecting queries.
    folder = raw_folder(root, start, end)
    if folder.exists():
        raise FileExistsError(f"{folder} already exists. Raw is immutable. "
                              "Inspect any incomplete run; use a different --data-root for a new pull.")
    schemas = preflight(db)
    folder.mkdir(parents=True, exist_ok=False)
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=config.ROOT, text=True))
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "unavailable", None
    manifest = {"status": "incomplete", "source": "WRDS legacy CRSP",
                "start": start, "end": end, "pilot_tickers": tickers,
                "universe_asof": universe_asof,
                "seed_resolution": "Exactly one common-stock permno with an active name interval on universe_asof",
                "schemas": schemas, "python": platform.python_version(),
                "pandas": pd.__version__, "git_head": revision, "git_dirty": dirty,
                "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
                "universe_sha256": sha256(config.UNIVERSE_CSV),
                "files": [], "pulled_at_utc": datetime.now(timezone.utc).isoformat()}

    def record_manifest():
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def save(frame, name, query):
        path = folder / name
        with path.open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False)
        manifest["files"].append({"name": name, "rows": len(frame), "query": query,
                                  "sha256": sha256(path)})
        record_manifest()

    record_manifest()
    seed_sql = ("select permno, ticker, namedt, nameenddt, shrcd from crsp.stocknames "
                f"where ticker in {sql_list(tickers)}")
    seed = db.raw_sql(seed_sql)
    save(seed, "seed_names.csv", seed_sql)
    resolved = resolve_seeds(seed, tickers, as_of=universe_asof)
    save(resolved, "pilot_securities.csv",
         f"Derived from seed_names; unique active common-stock permno per pilot label on {universe_asof}")
    permnos = sql_list(resolved["permno"].tolist())
    names_sql = ("select permno, ticker, namedt, nameenddt, shrcd from crsp.stocknames "
                 f"where permno in {permnos}")
    save(db.raw_sql(names_sql), "names.csv", names_sql)
    membership_sql = (f"select permno, start, ending from crsp.dsp500list where permno in {permnos} "
                      f"and start <= '{end}' and (ending >= '{start}' or ending is null)")
    save(db.raw_sql(membership_sql), "membership.csv", membership_sql)
    # True bid/ask only if the schema has BOTH. Never substitute bidlo/askhi.
    quote_columns = ["bid", "ask"] if {"bid", "ask"} <= set(schemas["dsf"]) else []
    manifest["quote_columns_available"] = bool(quote_columns)
    columns = TABLES["dsf"] + quote_columns
    for year in range(int(start[:4]), int(end[:4]) + 1):
        lo, hi = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        query = (f"select {', '.join(columns)} from crsp.dsf where permno in {permnos} "
                 f"and date between '{lo}' and '{hi}' order by permno, date")
        save(db.raw_sql(query), f"daily_{year}.csv", query)
    manifest["status"] = "complete"
    record_manifest()
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--data-root", help="Cloud storage root; or set STOCKS_DATA_ROOT")
    parser.add_argument("--universe-asof", help="Date used to resolve pilot labels; defaults to --end. Selection anchor, not a historical index universe.")
    args = parser.parse_args()
    window(args.start, args.end)
    if raw_folder(data_root(args.data_root), args.start, args.end).exists():
        raise FileExistsError("Raw run already exists; no WRDS connection opened")
    db = connect()
    try:
        print(pull(db, data_root(args.data_root), args.start, args.end, config.load_universe(), args.universe_asof))
    finally:
        db.close()


if __name__ == "__main__":
    main()
