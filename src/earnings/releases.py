"""Download the earnings press release (Exhibit 99.1) for every earnings 8K and turn it into plain text.

    python -m src.earnings.releases                   # every filing in edgar_earnings_8k.csv
    python -m src.earnings.releases --tickers AAPL --limit 5

Input is data/processed/earnings/edgar_earnings_8k.csv from src.earnings.edgar (make earnings-edgar).
For each filing we open the EDGAR filing index page, find the exhibit typed EX-99.1, and download it.
Some filings put the release under another EX-99 number, or attach none at all, so every row gets
a status instead of being dropped:

    ex99_1      found the exhibit typed EX-99.1
    other_ex99  no EX-99.1, used the first other EX-99 exhibit (check these by hand)
    no_ex99     the filing has no EX-99 exhibit
    fetch_error the SEC request failed, see the error column

Index pages and exhibits are cached as received in data/raw/earnings/edgar/index and .../releases,
so reruns do not hit the SEC. Use --refresh to refetch. Plain text goes to
data/processed/earnings/releases_text/<accession>.txt, one file per release, for the LLM step to read.
"""
from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

from ..common import config
from ..common.io_utils import write_processed
from .edgar import AREA, SEC_WWW, _get

TEXT_DIR = "releases_text"
_EX99_1 = re.compile(r"^EX-99\.0?1(?!\d)")
_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}
_SKIP_TAGS = {"script", "style", "ix:header"}
_SGML_WRAPPER = re.compile(r"<(TYPE|SEQUENCE|FILENAME|DESCRIPTION)>[^\n]*|</?(DOCUMENT|TEXT|PAGE)>", re.I)


class _IndexParser(HTMLParser):
    """Rows of the 'Document Format Files' table on an EDGAR filing index page."""

    def __init__(self):
        super().__init__()
        self.docs: list[dict] = []
        self._in_table = False
        self._row = None
        self._cell = None
        self._href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and "tableFile" in (attrs.get("class") or ""):
            self._in_table = attrs.get("summary") == "Document Format Files"
        elif self._in_table and tag == "tr":
            self._row, self._href = [], None
        elif self._row is not None and tag == "td":
            self._cell = ""
        elif self._cell is not None and tag == "a":
            self._href = attrs.get("href")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == "tr" and self._row:
            # columns are Seq, Description, Document, Type, Size
            if len(self._row) >= 4 and self._href:
                self.docs.append({"type": self._row[3].upper(), "description": self._row[1], "href": self._href})
            self._row = None
        elif tag == "table":
            self._in_table = False


def parse_index(html: str) -> list[dict]:
    parser = _IndexParser()
    parser.feed(html)
    return parser.docs


def pick_release(docs: list[dict]) -> tuple[dict | None, str]:
    """The EX-99.1 exhibit if there is one, else the first other EX-99 exhibit, with a status."""
    for doc in docs:
        if _EX99_1.match(doc["type"]):
            return doc, "ex99_1"
    for doc in docs:
        if doc["type"].startswith("EX-99"):
            return doc, "other_ex99"
    return None, "no_ex99"


def exhibit_url(href: str) -> str:
    """Absolute link, also for the iXBRL viewer form /ix?doc=/Archives/..."""
    href = href.replace("/ix?doc=", "")
    return href if href.startswith("http") else SEC_WWW + href


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
        elif tag == "td":
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(self._skip - 1, 0)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            # a line break inside HTML source is just a space, only block tags start a new line
            self.parts.append(re.sub(r"\s+", " ", data))


def html_to_text(html: str) -> str:
    """Readable plain text: tags removed, one line per paragraph or table row, blank lines collapsed."""
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return tidy("".join(parser.parts))


def tidy(text: str) -> str:
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.replace("\r", "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def decode(raw: bytes) -> str:
    """EDGAR documents are mostly UTF-8 or Windows-1252. Never fail on a stray byte."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def to_text(raw: bytes, name: str) -> str:
    """Old releases (2004 to about 2008) are .txt files, newer ones are HTML."""
    # drop the EDGAR wrapper (<DOCUMENT>, <TYPE>EX-99.1, <FILENAME>...) so only the release is left
    text = _SGML_WRAPPER.sub("", decode(raw))
    if name.lower().endswith((".htm", ".html")):
        return html_to_text(text)
    return tidy(text)


def fetch_cached(url: str, path: Path, refresh: bool = False) -> bytes:
    if path.exists() and not refresh:
        return path.read_bytes()
    raw = _get(url).content
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def get_release(filing: pd.Series, refresh: bool = False) -> dict:
    """Find, download and convert one filing's press release. Never raises on an SEC error."""
    edgar_raw = config.raw_dir(AREA) / "edgar"
    folder = filing["url"].rsplit("/", 1)[0]
    acc = filing["accession"]
    row = {"exhibit_type": "", "exhibit_url": "", "status": "", "n_chars": 0, "text_path": "", "error": ""}
    try:
        index_html = decode(fetch_cached(f"{folder}/{acc}-index.htm", edgar_raw / "index" / f"{acc}-index.htm", refresh))
        doc, row["status"] = pick_release(parse_index(index_html))
        if doc is None:
            return row
        url = exhibit_url(doc["href"])
        name = url.rsplit("/", 1)[-1]
        raw = fetch_cached(url, edgar_raw / "releases" / f"{acc}_{name}", refresh)
    except requests.RequestException as err:
        row.update(status="fetch_error", error=str(err))
        return row
    text = to_text(raw, name)
    text_path = config.processed_dir(AREA) / TEXT_DIR / f"{acc}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    row.update(exhibit_type=doc["type"], exhibit_url=url, n_chars=len(text),
               text_path=str(text_path.relative_to(config.ROOT)))
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickers", nargs="*", help="default: every ticker in edgar_earnings_8k.csv")
    parser.add_argument("--limit", type=int, help="only the first N filings, for a quick try")
    parser.add_argument("--refresh", action="store_true", help="refetch instead of using the cache")
    args = parser.parse_args()

    src = config.processed_dir(AREA) / "edgar_earnings_8k.csv"
    if not src.exists():
        raise SystemExit(f"Missing {src}. Run make earnings-edgar first.")
    filings = pd.read_csv(src, dtype={"cik": str})
    if args.tickers:
        filings = filings[filings["ticker"].isin([t.upper() for t in args.tickers])]
    if args.limit:
        filings = filings.head(args.limit)
    if filings.empty:
        raise SystemExit("No filings matched.")

    rows = []
    for i, (_, filing) in enumerate(filings.iterrows(), 1):
        rows.append(get_release(filing, args.refresh))
        if i % 50 == 0:
            print(f"{i}/{len(filings)} filings done")
    cols = ["ticker", "cik", "accession", "filing_date", "accepted_et", "edgar_timing"]
    result = pd.concat([filings[cols].reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    path = write_processed(result, "edgar_releases", AREA)
    print(pd.crosstab(result["ticker"], result["status"]).to_string())
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
