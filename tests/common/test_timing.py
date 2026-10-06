import datetime as dt

import numpy as np
import pandas as pd

from src.common.timing import classify_timing, to_seconds


def test_to_seconds_handles_common_types():
    assert to_seconds("08:30:00") == 8 * 3600 + 30 * 60
    assert to_seconds(dt.time(16, 5, 10)) == 16 * 3600 + 5 * 60 + 10
    assert to_seconds(pd.Timedelta(hours=7)) == 7 * 3600
    assert to_seconds("16:00") == 16 * 3600


def test_to_seconds_missing_or_garbage_is_nan():
    assert np.isnan(to_seconds(None))
    assert np.isnan(to_seconds(float("nan")))
    assert np.isnan(to_seconds("not a time"))
    assert np.isnan(to_seconds("12345"))


def test_classify_boundaries():
    assert classify_timing(to_seconds("09:29:59")) == "BMO"
    assert classify_timing(to_seconds("09:30:00")) == "DURING"
    assert classify_timing(to_seconds("15:59:59")) == "DURING"
    assert classify_timing(to_seconds("16:00:00")) == "AMC"
    assert classify_timing(to_seconds("21:30:00")) == "AMC"


def test_midnight_and_missing_are_unknown():
    assert classify_timing(to_seconds("00:00:00")) == "UNKNOWN"
    assert classify_timing(np.nan) == "UNKNOWN"
    assert classify_timing(None) == "UNKNOWN"
