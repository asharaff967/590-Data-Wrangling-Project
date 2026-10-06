"""Small helpers for writing raw and processed files. Every call names its area."""
from __future__ import annotations

import json
import numbers
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")


def sql_list(values) -> str:
    """Turn a list of tickers or ids into a safe SQL list like ('AAPL','MSFT') or (1,2).

    Values are validated instead of passed as driver parameters, so this works the same
    on every version of the wrds package.
    """
    items = list(values)
    if not items:
        raise ValueError("Empty list for SQL IN clause")
    out = []
    for v in items:
        if isinstance(v, numbers.Integral) or (isinstance(v, float) and float(v).is_integer()):
            out.append(str(int(v)))
        else:
            s = str(v).strip().upper()
            if not _TICKER_RE.match(s):
                raise ValueError(f"Refusing to put {v!r} in a SQL query")
            out.append(f"'{s}'")
    return "(" + ",".join(out) + ")"


def iso_date(value: str) -> str:
    """Validate YYYY-MM-DD and return it, so it can go straight into a query."""
    return date.fromisoformat(value).isoformat()


def save_raw(df: pd.DataFrame, name: str, area: str, query: str = "", force: bool = False) -> Path:
    """Write data/raw/<area>/wrds/<name>.csv plus a .meta.json. Raw files are immutable."""
    folder = config.raw_dir(area) / "wrds"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.csv"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Raw data is immutable, rerun with --force to replace it.")
    df.to_csv(path, index=False)
    meta = {
        "name": name,
        "area": area,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query": query.strip(),
    }
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return path


def read_raw(name: str, area: str, **kwargs) -> pd.DataFrame:
    path = config.raw_dir(area) / "wrds" / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run the matching make pull target for the {area} area first.")
    return pd.read_csv(path, **kwargs)


def write_processed(df: pd.DataFrame, name: str, area: str) -> Path:
    folder = config.processed_dir(area)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.csv"
    df.to_csv(path, index=False)
    return path
