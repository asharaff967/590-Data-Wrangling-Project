import pandas as pd

from src.earnings.edgar import earnings_8ks


def filings():
    return pd.DataFrame({
        "accessionNumber": ["0001-24-000001", "0001-24-000002", "0001-24-000003", "0001-24-000004", "0001-23-000009"],
        "filingDate": ["2024-02-01", "2024-07-25", "2024-07-25", "2024-03-01", "2023-02-02"],
        "form": ["8-K", "8-K", "8-K", "10-K", "8-K"],
        "items": ["2.02,9.01", "2.02", "5.02", "", "7.01,2.02"],
        # 21:30Z in winter is 16:30 EST (after close), 20:05Z in summer is 16:05 EDT,
        # 11:00Z in summer would be 07:00 EDT (before open)
        "acceptanceDateTime": ["2024-02-01T21:30:33.000Z", "2024-07-25T11:00:00.000Z",
                               "2024-07-25T12:00:00.000Z", "2024-03-01T12:00:00.000Z",
                               "2023-02-02T20:05:00.000Z"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm", "e.htm"],
    })


def test_only_item_202_8ks_in_range():
    out = earnings_8ks(filings(), "0000000123", "2024-01-01", "2024-12-31")
    assert list(out["accession"]) == ["0001-24-000001", "0001-24-000002"]


def test_eastern_time_conversion_handles_dst():
    out = earnings_8ks(filings(), "0000000123", "2020-01-01", "2025-12-31").set_index("accession")
    assert out.loc["0001-24-000001", "edgar_timing"] == "AMC"   # 16:30 EST
    assert out.loc["0001-24-000002", "edgar_timing"] == "BMO"   # 07:00 EDT
    assert out.loc["0001-23-000009", "edgar_timing"] == "DURING"  # 20:05Z is 15:05 EST (it would read 16:05 if DST were wrongly applied)


def test_url_uses_integer_cik_and_no_dashes():
    out = earnings_8ks(filings(), "0000000123", "2024-01-01", "2024-12-31")
    assert out.iloc[0]["url"].endswith("/data/123/000124000001/a.htm")


def test_empty_result_keeps_columns():
    out = earnings_8ks(filings(), "0000000123", "2030-01-01", "2030-12-31")
    assert out.empty and "edgar_timing" in out.columns
