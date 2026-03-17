"""
Foundation tests for pipeline/ package - Phase 1.

Requirements covered:
  FOUND-01: SQLite schema init (test_init_db_creates_tables, test_table_names)
  FOUND-02: MOLIT API client (test_molit_url_encoding, test_result_code_detection, test_pagination_stops)
  FOUND-03: Region config (test_lawd_cd_format, test_required_regions_present)
  FOUND-04: Idempotency (test_idempotency_check, test_idempotency_no_duplicate)
"""
import sqlite3
import pytest


# -----------------------------------------------------------------
# FOUND-01: SQLite schema
# -----------------------------------------------------------------

def test_init_db_creates_tables(tmp_db):
    """init_db() creates all 6 required tables; safe to call twice."""
    from pipeline.storage.schema import init_db

    conn = init_db(":memory:")
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "apartments",
        "monthly_prices",
        "building_info",
        "subway_distances",
        "commute_stops",
        "collection_log",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"
    init_db(":memory:")


def test_table_names(tmp_db):
    """All 6 table names are exactly as specified."""
    from pipeline.storage.schema import init_db

    conn = init_db(":memory:")
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for name in [
        "apartments",
        "monthly_prices",
        "building_info",
        "subway_distances",
        "commute_stops",
        "collection_log",
    ]:
        assert name in tables, f"Table '{name}' not found"


# -----------------------------------------------------------------
# FOUND-02: MOLIT API client
# -----------------------------------------------------------------

def test_molit_url_encoding():
    """MolitClient embeds serviceKey directly in URL - not via params dict."""
    from pipeline.clients.molit import MolitClient
    from urllib.parse import unquote, quote

    raw_key = "abc+def/ghi=="
    client = MolitClient(raw_key)
    expected_safe = quote(unquote(raw_key), safe="")

    assert hasattr(client, "safe_key"), "MolitClient must have safe_key attribute"
    assert client.safe_key == expected_safe, (
        f"safe_key mismatch: expected {expected_safe!r}, got {client.safe_key!r}"
    )


def test_result_code_detection():
    """_check_result_code returns (False, msg) for non-00/0000/000 resultCode."""
    from pipeline.clients.molit import _check_result_code

    error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header>
    <resultCode>30</resultCode>
    <resultMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</resultMsg>
  </header>
</response>"""
    ok, msg = _check_result_code(error_xml)
    assert ok is False
    assert "30" in msg or "SERVICE_KEY" in msg

    ok_xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL_SERVICE</resultMsg>
  </header>
  <body><items></items></body>
</response>"""
    ok, msg = _check_result_code(ok_xml)
    assert ok is True
    assert msg == ""


def test_pagination_stops():
    """fetch_all pagination loop stops when items returned < page_size."""
    import asyncio
    from unittest.mock import MagicMock
    from pipeline.clients.molit import MolitClient

    page1_xml = """<response><body><items>""" + "".join(
        f"<item><aptNm>Apt{i}</aptNm></item>" for i in range(5)
    ) + """</items></body><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header></response>"""
    page2_xml = """<response><body><items>
        <item><aptNm>Apt999</aptNm></item>
    </items></body><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header></response>"""

    responses = [page1_xml, page2_xml]
    call_count = 0

    async def fake_get(url, timeout=30.0):
        nonlocal call_count
        resp = MagicMock()
        resp.text = responses[call_count]
        resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    client = MolitClient("testkey")

    async def run():
        mock_http = MagicMock()
        mock_http.get = fake_get
        items = await client.fetch_all(mock_http, "11680", "202401", "trade", page_size=5)
        return items

    items = asyncio.run(run())
    assert call_count == 2, f"Expected 2 pages fetched, got {call_count}"
    assert len(items) == 6  # 5 from page1 + 1 from page2


# -----------------------------------------------------------------
# FOUND-03: Region config
# -----------------------------------------------------------------

def test_lawd_cd_format():
    """All values in PIPELINE_REGIONS are exactly 5-digit numeric strings."""
    from pipeline.config.regions import PIPELINE_REGIONS

    for name, code in PIPELINE_REGIONS.items():
        assert len(code) == 5, f"{name}: code '{code}' is not 5 digits"
        assert code.isdigit(), f"{name}: code '{code}' contains non-digit characters"


def test_required_regions_present():
    """PIPELINE_REGIONS contains all 25 Seoul districts and 4 required Gyeonggi regions."""
    from pipeline.config.regions import PIPELINE_REGIONS

    required_codes = {
        "11680", "11740", "11305", "11500", "11620", "11215", "11530",
        "11545", "11350", "11320", "11230", "11590", "11440", "11410",
        "11650", "11200", "11290", "11710", "11470", "11560", "11170",
        "11380", "11110", "11140", "11260",
        "41175", "41390", "41550", "41220",
    }
    present_codes = set(PIPELINE_REGIONS.values())
    missing = required_codes - present_codes
    assert not missing, f"Missing LAWD_CDs: {missing}"

    keys = set(PIPELINE_REGIONS.keys())
    assert any("분당" in k for k in keys), "성남시 분당구 key missing"
    assert any("과천" in k for k in keys), "과천시 key missing"
    assert any("하남" in k for k in keys), "하남시 key missing"
    assert any("동안" in k for k in keys), "안양시 동안구 key missing"


# -----------------------------------------------------------------
# FOUND-04: Idempotency
# -----------------------------------------------------------------

def test_idempotency_check(tmp_db):
    """is_collected() returns False before mark_collected, True after."""
    from pipeline.storage.schema import init_db
    from pipeline.utils.idempotency import is_collected, mark_collected

    conn = init_db(":memory:")

    result_before = is_collected(conn, "11680", "202401", "trade")
    assert result_before is False, "Should be False before marking"

    mark_collected(conn, "11680", "202401", "trade", record_count=42)

    result_after = is_collected(conn, "11680", "202401", "trade")
    assert result_after is True, "Should be True after marking"


def test_idempotency_no_duplicate(tmp_db):
    """Second mark_collected() with same key does not raise and does not create duplicate."""
    from pipeline.storage.schema import init_db
    from pipeline.utils.idempotency import mark_collected

    conn = init_db(":memory:")

    mark_collected(conn, "11680", "202401", "trade", record_count=10)
    mark_collected(conn, "11680", "202401", "trade", record_count=99)

    count = conn.execute(
        "SELECT COUNT(*) FROM collection_log WHERE lawd_cd='11680' AND deal_ym='202401' AND data_type='trade'"
    ).fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count} (duplicate inserted)"
