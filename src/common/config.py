"""Paths and settings shared by every area of the project.

Each area (earnings, integration, and any area a teammate adds) keeps its own folders:
    data/raw/<area>/        immutable pulls, never committed
    data/processed/<area>/  tables rebuilt by make, never edited by hand
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is in requirements.txt, but do not crash if it is missing
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]
if load_dotenv:
    load_dotenv(ROOT / ".env")

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
DOCS = ROOT / "docs"
UNIVERSE_CSV = ROOT / "config" / "universe.csv"

START_DATE = os.getenv("START_DATE", "2004-01-01")
END_DATE = os.getenv("END_DATE", "2025-12-31")
WRDS_USERNAME = os.getenv("WRDS_USERNAME", "").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()


def raw_dir(area: str) -> Path:
    return RAW / area


def processed_dir(area: str) -> Path:
    return PROCESSED / area


def load_universe() -> list[str]:
    """Pilot tickers from config/universe.csv, uppercase and deduplicated."""
    import pandas as pd

    df = pd.read_csv(UNIVERSE_CSV)
    return sorted(df["ticker"].astype(str).str.upper().str.strip().unique())
