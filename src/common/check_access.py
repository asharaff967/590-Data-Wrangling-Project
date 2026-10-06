"""Check which WRDS libraries and tables this account can open, and that EDGAR answers.

Run:  make access   (python -m src.common.check_access)
Writes data/processed/common/access_report.json and docs/access_report.md.
Paste the table from docs/access_report.md into the setup card.

Table names below are the usual WRDS names. Any that fail show up in the report with the
error, so fix the name here or ask WRDS support.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import requests

from . import config


def table_checks() -> list[tuple[str, str, list[str]]]:
    first = config.START_DATE[:4]
    last = config.END_DATE[:4]
    return [
        ("OptionMetrics", "optionm",
         ["secnmd", "secprd", f"opprcd{first}", f"opprcd{last}", f"vsurfd{first}", "zerocd"]),
        ("CRSP", "crsp", ["dsf", "stocknames", "dsp500list", "ccmxpf_lnkhist"]),
        ("Compustat", "comp", ["fundq", "company"]),
        ("I/B/E/S", "ibes", ["actu_epsus", "statsum_epsus"]),
        ("Link tables", "wrdsapps", ["opcrsphist", "ibcrsphist"]),
    ]


def first_line(exc: Exception) -> str:
    text = str(exc).strip().splitlines()
    return (text[0] if text else type(exc).__name__)[:200]


def probe_table(db, library: str, table: str) -> dict:
    full = f"{library}.{table}"
    try:
        df = db.raw_sql(f"select * from {full} limit 1")
        return {"table": full, "ok": True, "n_columns": int(df.shape[1]),
                "columns": [str(c) for c in df.columns][:15], "error": ""}
    except Exception as exc:  # any failure means we cannot use this table
        return {"table": full, "ok": False, "n_columns": 0, "columns": [], "error": first_line(exc)}


def check_wrds() -> list[dict]:
    import wrds

    if not config.WRDS_USERNAME:
        raise SystemExit("Set WRDS_USERNAME in .env first (copy .env.example).")
    db = wrds.Connection(wrds_username=config.WRDS_USERNAME)
    try:
        visible = set(db.list_libraries())
        rows = []
        for source, library, tables in table_checks():
            probes = [probe_table(db, library, t) for t in tables] if library in visible else []
            rows.append({"source": source, "library": library, "library_visible": library in visible,
                         "tables": probes})
        return rows
    finally:
        db.close()


def check_edgar() -> dict:
    if not config.SEC_USER_AGENT:
        return {"ok": False, "detail": "SEC_USER_AGENT is not set in .env"}
    try:
        resp = requests.get("https://data.sec.gov/submissions/CIK0000320193.json",
                            headers={"User-Agent": config.SEC_USER_AGENT}, timeout=30)
        return {"ok": resp.ok, "detail": f"HTTP {resp.status_code}"}
    except requests.RequestException as exc:
        return {"ok": False, "detail": first_line(exc)}


def render_markdown(wrds_rows: list[dict] | None, edgar: dict | None) -> str:
    lines = ["# Access report", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y/%m/%d %H:%M')} UTC", "",
             "| Source | Library visible | Tables open | Status for the card |",
             "| --- | --- | --- | --- |"]
    for row in wrds_rows or []:
        probes = row["tables"]
        n_ok = sum(p["ok"] for p in probes)
        if not row["library_visible"]:
            status = "Not yet: library not visible to this account, ask WRDS or the Duke admin"
        elif n_ok == len(probes):
            status = "Yes, all checked tables open"
        elif n_ok == 0:
            status = "Not yet: library visible but no checked table opens"
        else:
            bad = ", ".join(p["table"].split(".")[1] for p in probes if not p["ok"])
            status = f"Partly: these did not open: {bad}"
        lines.append(f"| {row['source']} | {'yes' if row['library_visible'] else 'no'} | "
                     f"{n_ok} of {len(probes)} | {status} |")
    if edgar is not None:
        status = "Yes, reachable" if edgar["ok"] else f"Not yet: {edgar['detail']}"
        lines.append(f"| SEC EDGAR | n/a | n/a | {status} |")
    failures = [p for r in (wrds_rows or []) for p in r["tables"] if not p["ok"]]
    if failures:
        lines += ["", "## Tables that failed", ""]
        lines += [f"* {p['table']}: {p['error']}" for p in failures]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-wrds", action="store_true")
    parser.add_argument("--skip-edgar", action="store_true")
    args = parser.parse_args()

    wrds_rows = None if args.skip_wrds else check_wrds()
    edgar = None if args.skip_edgar else check_edgar()

    out_dir = config.processed_dir("common")
    out_dir.mkdir(parents=True, exist_ok=True)
    config.DOCS.mkdir(parents=True, exist_ok=True)
    (out_dir / "access_report.json").write_text(
        json.dumps({"wrds": wrds_rows, "edgar": edgar}, indent=2))
    md = render_markdown(wrds_rows, edgar)
    (config.DOCS / "access_report.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
