"""Time of day helpers shared by the I/B/E/S and EDGAR code.

Buckets are in US Eastern time, using regular market hours (open 9:30, close 16:00).
ASSUMPTION to verify: I/B/E/S announce times (anntims) are Eastern. Check the WRDS
I/B/E/S documentation and note the answer in docs/ai_log.md.
"""
from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

OPEN_S = 9 * 3600 + 30 * 60
CLOSE_S = 16 * 3600


def to_seconds(value) -> float:
    """Seconds since midnight from a time, 'HH:MM:SS' string or Timedelta. NaN if unusable."""
    if value is None:
        return np.nan
    if isinstance(value, time):
        return float(value.hour * 3600 + value.minute * 60 + value.second)
    if isinstance(value, pd.Timedelta):
        return float(value.total_seconds())
    try:
        if pd.isna(value):
            return np.nan
    except (TypeError, ValueError):
        pass
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return np.nan
    try:
        hours, minutes = int(parts[0]), int(parts[1])
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
    except ValueError:
        return np.nan
    return hours * 3600 + minutes * 60 + seconds


def classify_timing(seconds) -> str:
    """BMO (before open), DURING, AMC (after close) or UNKNOWN.

    A time of exactly 00:00:00 is treated as UNKNOWN because data vendors often use it
    when the time was not captured. Confirm this against the raw data.
    """
    if seconds is None or pd.isna(seconds) or seconds == 0:
        return "UNKNOWN"
    if seconds < OPEN_S:
        return "BMO"
    if seconds >= CLOSE_S:
        return "AMC"
    return "DURING"
