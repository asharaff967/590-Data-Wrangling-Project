from src.earnings.releases import exhibit_url, html_to_text, parse_index, pick_release, to_text

# Trimmed from a real EDGAR filing index page: the document table, then the XBRL data table.
INDEX_HTML = """
<table class="tableFile" summary="Document Format Files">
  <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
  <tr><td scope="row">1</td><td scope="row">8-K</td>
      <td scope="row"><a href="/ix?doc=/Archives/edgar/data/1/000000000124000001/x-8k.htm">x-8k.htm</a></td>
      <td scope="row">8-K</td><td scope="row">30000</td></tr>
  <tr><td scope="row">2</td><td scope="row">EXHIBIT 99.2</td>
      <td scope="row"><a href="/Archives/edgar/data/1/000000000124000001/ex992.htm">ex992.htm</a></td>
      <td scope="row">EX-99.2</td><td scope="row">9000</td></tr>
  <tr><td scope="row">3</td><td scope="row">EXHIBIT 99.1</td>
      <td scope="row"><a href="/Archives/edgar/data/1/000000000124000001/ex991.htm">ex991.htm</a></td>
      <td scope="row">EX-99.1</td><td scope="row">80000</td></tr>
  <tr><td scope="row">&nbsp;</td><td scope="row">Complete submission text file</td>
      <td scope="row"><a href="/Archives/edgar/data/1/000000000124000001/0000000001-24-000001.txt">x.txt</a></td>
      <td scope="row">&nbsp;</td><td scope="row">200000</td></tr>
</table>
<table class="tableFile" summary="Data Files">
  <tr><td scope="row">4</td><td scope="row">XBRL SCHEMA</td>
      <td scope="row"><a href="/Archives/edgar/data/1/000000000124000001/x.xsd">x.xsd</a></td>
      <td scope="row">EX-101.SCH</td><td scope="row">3000</td></tr>
</table>
"""


def docs(*types):
    return [{"type": t, "description": "", "href": f"/{i}.htm"} for i, t in enumerate(types)]


def test_parse_index_reads_document_table_only():
    found = parse_index(INDEX_HTML)
    assert [d["type"] for d in found] == ["8-K", "EX-99.2", "EX-99.1", ""]
    assert found[2]["href"].endswith("/ex991.htm")


def test_picks_ex99_1_even_when_ex99_2_comes_first():
    doc, status = pick_release(parse_index(INDEX_HTML))
    assert status == "ex99_1" and doc["href"].endswith("/ex991.htm")


def test_ex99_1_variants_and_lookalikes():
    assert pick_release(docs("8-K", "EX-99.01"))[1] == "ex99_1"
    assert pick_release(docs("8-K", "EX-99.1 CHARTER"))[1] == "ex99_1"  # odd label seen on a 2007 JNJ filing
    doc, status = pick_release(docs("8-K", "EX-99.10", "EX-99"))
    assert status == "other_ex99" and doc["type"] == "EX-99.10"  # EX-99.10 is not EX-99.1


def test_no_exhibit_is_flagged_not_dropped():
    assert pick_release(docs("8-K", "GRAPHIC", "EX-101.SCH")) == (None, "no_ex99")


def test_exhibit_url_strips_ixbrl_viewer():
    assert exhibit_url("/ix?doc=/Archives/edgar/data/1/a.htm") == "https://www.sec.gov/Archives/edgar/data/1/a.htm"
    assert exhibit_url("https://www.sec.gov/x.htm") == "https://www.sec.gov/x.htm"


def test_html_to_text_keeps_paragraphs_and_drops_markup():
    html = ("<html><head><style>p {color: red}</style></head><body>"
            "<p>CUPERTINO, California&nbsp;&mdash; January 30, 2024</p>"
            "<p>Apple   today announced results.</p>"
            "<table><tr><td>Revenue</td><td>$119.6</td></tr></table></body></html>")
    text = html_to_text(html)
    assert text.splitlines() == ["CUPERTINO, California — January 30, 2024", "",
                                 "Apple today announced results.", "", "Revenue $119.6"]
    assert "color" not in text


def test_old_txt_release_and_cp1252_bytes():
    raw = b"Q3 results \x93strong\x94\r\n\r\n\r\n\r\nNet sales < 5%"  # Windows-1252 curly quotes, not valid UTF-8
    assert to_text(raw, "ex99.txt") == "Q3 results “strong”\n\nNet sales < 5%"


def test_edgar_wrapper_is_removed():
    raw = b"<DOCUMENT>\n<TYPE>EX-99.15 OTH FIN ST\n<SEQUENCE>2\n<FILENAME>r.txt\n<TEXT>\nExhibit 99.15\n<PAGE>\nSales</TEXT>"
    assert to_text(raw, "r.txt") == "Exhibit 99.15\n\nSales"
    html = b"<DOCUMENT><TYPE>EX-99.1\n<SEQUENCE>2\n<FILENAME>a.htm\n<TEXT><html><p>Apple Reports\nQ4</p></html>"
    assert to_text(html, "a.htm") == "Apple Reports Q4"
