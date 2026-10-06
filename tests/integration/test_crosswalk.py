import numpy as np
import pandas as pd

from src.integration.crosswalk import build_crosswalk
from src.common.io_utils import sql_list

import pytest


def frames():
    # Ticker XYZ was reused: permno 100 until 2015, permno 200 afterwards.
    names = pd.DataFrame({
        "permno": [100, 200, 300],
        "ticker": ["XYZ", "XYZ", "ABC"],
        "namedt": ["2000-01-01", "2015-06-01", "2000-01-01"],
        "nameenddt": ["2015-05-31", None, None],
        "shrcd": [11, 11, 11],
        "comnam": ["OLD CO", "NEW CO", "ABC CO"],
    })
    opcrsp = pd.DataFrame({
        "secid": [1, 2, 3, 3], "permno": [100, 200, 300, 300],
        "sdate": ["2000-01-01", "2015-06-01", "2000-01-01", "2000-01-01"],
        "edate": ["2015-05-31", None, None, None], "score": [1, 1, 3, 1],
    })
    ccm = pd.DataFrame({
        "gvkey": ["000010", "000020", "000030", "000031"], "lpermno": [100, 200, 300, 300],
        "linktype": ["LC", "LC", "LU", "LC"], "linkprim": ["P", "P", "C", "P"],
        "linkdt": ["2000-01-01", "2015-06-01", "2000-01-01", "2000-01-01"],
        "linkenddt": ["2015-05-31", None, None, None],
    })
    ibcrsp = pd.DataFrame({
        "ticker": ["XYZ", "XYZN", "ABC"], "permno": [100, 200, 300],
        "sdate": ["2000-01-01", "2015-06-01", "2000-01-01"], "edate": ["2015-05-31", None, None],
        "score": [1, 2, 1],
    })
    company = pd.DataFrame({"gvkey": ["000010", "000020", "000030", "000031"],
                            "cik": ["111", "222", "333", "334"]})
    return names, opcrsp, ccm, ibcrsp, company


def test_reused_ticker_resolves_by_date():
    names, opcrsp, ccm, ibcrsp, company = frames()
    old = build_crosswalk(names, opcrsp, ccm, ibcrsp, company, pd.Timestamp("2010-01-01"))
    new = build_crosswalk(names, opcrsp, ccm, ibcrsp, company, pd.Timestamp("2020-01-01"))
    xyz_old = old[old["ticker"] == "XYZ"].iloc[0]
    xyz_new = new[new["ticker"] == "XYZ"].iloc[0]
    assert (xyz_old["permno"], xyz_old["secid"], xyz_old["gvkey"]) == (100, 1, "000010")
    assert (xyz_new["permno"], xyz_new["secid"], xyz_new["gvkey"]) == (200, 2, "000020")


def test_best_score_and_primary_link_win_and_are_flagged():
    names, opcrsp, ccm, ibcrsp, company = frames()
    out = build_crosswalk(names, opcrsp, ccm, ibcrsp, company, pd.Timestamp("2020-01-01"))
    abc = out[out["ticker"] == "ABC"].iloc[0]
    assert abc["secid_score"] == 1          # score 1 beat score 3
    assert abc["gvkey"] == "000031"         # primary LC link beat the LU candidate
    assert "multiple_secid" in abc["flags"] and "multiple_gvkey" in abc["flags"]


def test_weak_match_is_flagged():
    names, opcrsp, ccm, ibcrsp, company = frames()
    out = build_crosswalk(names, opcrsp, ccm, ibcrsp, company, pd.Timestamp("2020-01-01"))
    xyz = out[out["ticker"] == "XYZ"].iloc[0]
    assert "weak_ibes_match" in xyz["flags"]


def test_sql_list_quotes_and_validates():
    assert sql_list(["aapl", "BRK.B"]) == "('AAPL','BRK.B')"
    assert sql_list([1, 2]) == "(1,2)"
    assert sql_list(np.array([100, 200])) == "(100,200)"  # numpy ints must stay unquoted numbers
    with pytest.raises(ValueError):
        sql_list(["AAPL'); drop table x;--"])
    with pytest.raises(ValueError):
        sql_list([])
