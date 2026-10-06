"""Raw WRDS pull for the earnings area: Compustat report dates and I/B/E/S announce dates and times.

    python -m src.earnings.pull

Output goes to data/raw/earnings/wrds as CSV plus a .meta.json holding the query and pull time.
Raw files are immutable: rerun with --force to replace one on purpose.
Table and column names follow the usual WRDS layout but were not run against WRDS when this was
written. If a query fails, the error names the column, so fix the SQL here.
"""
from __future__ import annotations

import argparse

from ..common import config
from ..common.io_utils import iso_date, save_raw, sql_list
from ..common.wrds_conn import connect

AREA = "earnings"


def pull_earnings(db, tickers: list[str], start: str, end: str, force: bool) -> None:
    # Compustat quarterly. rdq is the report date of quarterly earnings. It has no time of day.
    comp_sql = f"""
        select f.gvkey, f.tic, c.conm, c.cik, f.datadate, f.fyearq, f.fqtr, f.rdq
        from comp.fundq as f
        join comp.company as c on c.gvkey = f.gvkey
        where f.tic in {sql_list(tickers)}
          and f.indfmt = 'INDL' and f.datafmt = 'STD' and f.popsrc = 'D' and f.consol = 'C'
          and f.datadate between '{iso_date(start)}' and '{iso_date(end)}'
        order by f.tic, f.datadate
    """
    comp = db.raw_sql(comp_sql, date_cols=["datadate", "rdq"])
    print(f"Compustat rows: {len(comp)}")
    save_raw(comp, "compustat_fundq_pilot", AREA, comp_sql, force)

    # I/B/E/S actuals, quarterly EPS. anndats and anntims are the announce date and time.
    ibes_sql = f"""
        select *
        from ibes.actu_epsus
        where oftic in {sql_list(tickers)}
          and pdicity = 'QTR' and measure = 'EPS'
          and anndats between '{iso_date(start)}' and '{iso_date(end)}'
        order by oftic, pends, anndats
    """
    ibes = db.raw_sql(ibes_sql, date_cols=["pends", "anndats", "actdats"])
    print(f"I/B/E/S rows: {len(ibes)}")
    save_raw(ibes, "ibes_actu_epsus_pilot", AREA, ibes_sql, force)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default=config.START_DATE)
    parser.add_argument("--end", default=config.END_DATE)
    parser.add_argument("--force", action="store_true", help="replace existing raw files")
    args = parser.parse_args()

    tickers = config.load_universe()
    print(f"Universe: {', '.join(tickers)}")
    db = connect()
    try:
        pull_earnings(db, tickers, args.start, args.end, args.force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
