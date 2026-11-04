"""Offline daily audit and dated membership/name joins from one immutable raw run."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from .pull import data_root, sha256, window
from .quality import audit_daily
from .raw_inputs import daily_source_rows, read_raw_run


def build(root, start, end):
    start, end = window(start, end)
    folder, manifest, frames = read_raw_run(root, start, end)
    manifest_path = folder / "manifest.json"
    daily = daily_source_rows(frames, start, end)
    pilot = frames["pilot_securities.csv"]
    out = audit_daily(daily, frames["names.csv"],
                      frames["membership.csv"], pilot, start, end)
    counts = Counter(code for codes in out["core_flags"] for code in codes.split(";") if code)
    diagnostics = Counter(code for codes in out["diagnostic_flags"] for code in codes.split(";") if code)
    coverage = []
    for security in pilot.itertuples(index=False):
        rows = out[out["pilot_ticker"].eq(security.pilot_ticker)]
        coverage.append({"pilot_ticker": security.pilot_ticker, "permno": int(security.permno),
                         "rows": len(rows), "observed_dates": int(rows["date"].nunique()),
                         "rows_with_core_flags": int(rows["core_flags"].ne("").sum()),
                         "in_sp500_rows": int(rows["in_sp500"].fillna(False).sum()),
                         "missing_entirely": rows.empty})
    covered = pd.DataFrame(coverage)
    core_rows = int(out["core_flags"].ne("").sum())
    report = {
        "source": manifest["source"], "start": start, "end": end,
        "rows": len(out), "rows_with_core_flags": core_rows,
        "rows_without_core_flags": len(out) - core_rows,
        "core_flag_counts": dict(sorted(counts.items())),
        "diagnostic_counts": dict(sorted(diagnostics.items())),
        "missing_pilot_tickers": covered.loc[covered["missing_entirely"], "pilot_ticker"].tolist(),
        "raw_manifest_sha256": sha256(manifest_path),
        "build_source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
        "interpretation": [
            "All source rows retained; flag counts overlap. Inspect source_file and source_row (CSV header is line 1).",
            "Daily key is (permno, date). Arrival-order timestamp regression is not applicable.",
            "Negative CRSP prc is retained; price_abs and the bid/ask-average indicator are derived fields.",
            "Membership/name intervals are inclusive; blank end dates mean open-ended.",
            "The dated name is descriptive history, not proof the information was publicly available at that time.",
            "The seed universe is selected by present pilot labels: this is not a survivorship-free S&P 500 universe.",
            "Outside-membership rows and missing analytics remain visible; no silent filtering or filling.",
            "Observed dates are not a trading-calendar completeness check. No flags does not certify coverage or tradability.",
            "This module does not produce delisting-adjusted returns, corporate-action event tables, broker data, or an OptionMetrics ID bridge.",
        ],
    }
    output = Path(root) / "processed" / "stocks" / f"{start}_{end}"
    output.mkdir(parents=True, exist_ok=True)
    out.to_csv(output / "stock_daily.csv", index=False)
    covered.to_csv(output / "coverage.csv", index=False)
    # Copy intervals as separate documented tables for the integration area.
    frames["names.csv"].to_csv(output / "identifier_intervals.csv", index=False)
    frames["membership.csv"].to_csv(output / "membership_intervals.csv", index=False)
    (output / "quality_report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--data-root")
    args = parser.parse_args()
    output, report = build(data_root(args.data_root), args.start, args.end)
    print(json.dumps({"output": str(output), "rows": report["rows"],
                      "rows_with_core_flags": report["rows_with_core_flags"],
                      "missing_pilot_tickers": report["missing_pilot_tickers"]}, indent=2))


if __name__ == "__main__":
    main()
