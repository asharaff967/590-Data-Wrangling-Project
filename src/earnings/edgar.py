"""SEC EDGAR helpers: find each company's earnings 8K filings and when EDGAR accepted them.

    python -m src.earnings.edgar                      # pilot universe, whole window
    python -m src.earnings.edgar --tickers AAPL MSFT --start 2020-01-01 --refresh

An earnings press release is filed on Form 8K under Item 2.02. The EDGAR acceptance timestamp is a
third, independent clue for the announcement time. It is not the release time itself: companies
sometimes file minutes or hours after releasing, so treat it as a check, not the answer. The
press release text (Exhibit 99.1) is what the LLM step should read.

SEC rules: send a real User-Agent (SEC_USER_AGENT in .env) and stay under 10 requests a second.
The ticker to CIK map only covers current tickers. Historical tickers need the Compustat cik
through src/integration/crosswalk.py.

Raw JSON is cached in data/raw/earnings/edgar so reruns do not hit the SEC. Use --refresh to refetch.
"""
from __future__ import annotations

import argparse
import json
import time

import pandas as pd
import requests

from ..common import config
from ..common.io_utils import write_processed
from ..common.timing import classify_timing

AREA = "earnings"
SEC_DATA = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
MIN_INTERVAL = 0.15
_last_call = 0.0


def _get(url: str) -> requests.Response:
    global _last_call
    if not config.SEC_USER_AGENT:
        raise SystemExit("Set SEC_USER_AGENT in .env, for example 'Your Name your.netid@duke.edu'.")
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers={"User-Agent": config.SEC_USER_AGENT}, timeout=30)
    _last_call = time.monotonic()
    resp.raise_for_status()
    return resp


def get_json_cached(url: str, cache_name: str, refresh: bool = False) -> dict:
    path = config.raw_dir(AREA) / "edgar" / cache_name
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    data = _get(url).json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def ticker_to_cik(refresh: bool = False) -> dict[str, str]:
    data = get_json_cached(f"{SEC_WWW}/files/company_tickers.json", "company_tickers.json", refresh)
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}


def all_filings(cik: str, refresh: bool = False) -> pd.DataFrame:
    """Every filing the submissions API lists for a CIK, recent and older pages combined."""
    sub = get_json_cached(f"{SEC_DATA}/submissions/CIK{cik}.json", f"submissions_{cik}.json", refresh)
    frames = [pd.DataFrame(sub["filings"]["recent"])]
    for page in sub["filings"].get("files", []):
        older = get_json_cached(f"{SEC_DATA}/submissions/{page['name']}", f"submissions_{page['name']}", refresh)
        frames.append(pd.DataFrame(older))
    return pd.concat(frames, ignore_index=True)


def _eastern_seconds(ts: pd.Timestamp) -> float:
    return ts.hour * 3600 + ts.minute * 60 + ts.second


def earnings_8ks(filings: pd.DataFrame, cik: str, start: str, end: str) -> pd.DataFrame:
    """Keep Form 8K filings with Item 2.02 in the date range, with Eastern acceptance time."""
    cols = ["ticker", "cik", "accession", "filing_date", "accepted_et", "edgar_timing", "items", "url"]
    df = filings[filings["form"].eq("8-K")].copy()
    has_202 = df["items"].fillna("").map(lambda s: "2.02" in [x.strip() for x in str(s).split(",")])
    df = df[has_202]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = df.reset_index(drop=True)
    accepted = pd.to_datetime(df["acceptanceDateTime"], utc=True).dt.tz_convert("America/New_York")
    out = pd.DataFrame({
        "ticker": "",
        "cik": cik,
        "accession": df["accessionNumber"],
        "filing_date": pd.to_datetime(df["filingDate"]),
        "accepted_et": accepted,
        "items": df["items"],
        "primary_document": df["primaryDocument"],
    })
    out["edgar_timing"] = accepted.map(lambda t: classify_timing(_eastern_seconds(t)))
    out["url"] = [f"{SEC_WWW}/Archives/edgar/data/{int(cik)}/{a.replace('-', '')}/{d}"
                  for a, d in zip(out["accession"], out["primary_document"])]
    mask = (out["filing_date"] >= pd.Timestamp(start)) & (out["filing_date"] <= pd.Timestamp(end))
    return out[mask].sort_values("filing_date")[cols].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickers", nargs="*", help="default: config/universe.csv")
    parser.add_argument("--start", default=config.START_DATE)
    parser.add_argument("--end", default=config.END_DATE)
    parser.add_argument("--refresh", action="store_true", help="refetch instead of using the cache")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else config.load_universe()
    cik_map = ticker_to_cik(args.refresh)
    frames = []
    for ticker in tickers:
        cik = cik_map.get(ticker)
        if not cik:
            print(f"{ticker}: no CIK in the SEC ticker file (renamed or delisted?), skipping")
            continue
        found = earnings_8ks(all_filings(cik, args.refresh), cik, args.start, args.end)
        found["ticker"] = ticker
        print(f"{ticker}: {len(found)} earnings 8K filings")
        frames.append(found)
    if not frames:
        raise SystemExit("Nothing found.")
    result = pd.concat(frames, ignore_index=True)
    path = write_processed(result, "edgar_earnings_8k", AREA)
    print(result["edgar_timing"].value_counts().to_string())
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
