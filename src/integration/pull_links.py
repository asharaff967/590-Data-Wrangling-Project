"""Raw WRDS pull of the ID link tables used by src/integration/crosswalk.py.

    python -m src.integration.pull_links

Output goes to data/raw/integration/wrds. Raw files are immutable: rerun with --force to replace.
Table and column names follow the usual WRDS layout but were not run against WRDS when this was
written. If a query fails, the error names the problem, so fix the SQL here.
"""
from __future__ import annotations

import argparse

from ..common import config
from ..common.io_utils import save_raw, sql_list
from ..common.wrds_conn import connect

AREA = "integration"


def pull_links(db, tickers: list[str], force: bool) -> None:
    names_sql = f"select * from crsp.stocknames where ticker in {sql_list(tickers)}"
    names = db.raw_sql(names_sql, date_cols=["namedt", "nameenddt"])
    print(f"CRSP stocknames rows: {len(names)}")
    save_raw(names, "crsp_stocknames_pilot", AREA, names_sql, force)
    permnos = sorted(names["permno"].dropna().astype(int).unique())

    op_sql = f"select * from wrdsapps.opcrsphist where permno in {sql_list(permnos)}"
    op = db.raw_sql(op_sql, date_cols=["sdate", "edate"])
    print(f"OptionMetrics to CRSP link rows: {len(op)}")
    save_raw(op, "opcrsphist_pilot", AREA, op_sql, force)

    ccm_sql = (f"select * from crsp.ccmxpf_lnkhist where lpermno in {sql_list(permnos)} "
               "and linktype in ('LC','LU') and linkprim in ('P','C')")
    ccm = db.raw_sql(ccm_sql, date_cols=["linkdt", "linkenddt"])
    print(f"CRSP Compustat link rows: {len(ccm)}")
    save_raw(ccm, "ccm_lnkhist_pilot", AREA, ccm_sql, force)

    ib_sql = f"select * from wrdsapps.ibcrsphist where permno in {sql_list(permnos)}"
    ib = db.raw_sql(ib_sql, date_cols=["sdate", "edate"])
    print(f"I/B/E/S to CRSP link rows: {len(ib)}")
    save_raw(ib, "ibcrsphist_pilot", AREA, ib_sql, force)

    gvkeys = sorted(ccm["gvkey"].dropna().astype(str).str.zfill(6).unique())
    if gvkeys:
        # gvkey is a string, so quote the values directly. They are digits only.
        quoted = "(" + ",".join(f"'{g}'" for g in gvkeys if g.isdigit()) + ")"
        co_sql = f"select gvkey, cik, tic, conm from comp.company where gvkey in {quoted}"
        co = db.raw_sql(co_sql)
        print(f"Compustat company rows: {len(co)}")
        save_raw(co, "comp_company_pilot", AREA, co_sql, force)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="replace existing raw files")
    args = parser.parse_args()

    tickers = config.load_universe()
    print(f"Universe: {', '.join(tickers)}")
    db = connect()
    try:
        pull_links(db, tickers, args.force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
