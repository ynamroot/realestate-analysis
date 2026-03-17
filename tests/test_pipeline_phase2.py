"""
Phase 2 tests: normalizer, aggregator, storage repository functions.
All tests are xfail until Wave 1/2 implementation is complete.

Requirements covered:
  PRICE-01: upsert_apartment, insert_monthly_prices storage functions
  PRICE-02: get_month_range month iteration bounds
  PRICE-03: aggregate_monthly grouping and statistics
  PRICE-04: normalize_trade_item, normalize_rent_item field normalization
  BLDG-01/02: upsert_building_info insert and replace
"""
import pytest
from pipeline.storage.schema import init_db


# --- PRICE-04: Normalization tests ---

@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_normalize_trade_deal_amount():
    """dealAmount '55,000' -> price=55000 (int, comma stripped)."""
    from pipeline.processors.normalizer import normalize_trade_item
    item = {"aptNm": "은마", "umdNm": "대치동", "dealAmount": "55,000",
            "excluUseAr": "84.9700", "dealMonth": "3", "dealYear": "2024",
            "buildYear": "1979", "jibun": "1", "roadNm": ""}
    result = normalize_trade_item(item)
    assert result["price"] == 55000
    assert isinstance(result["price"], int)


@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_normalize_trade_exclu_use_ar():
    """excluUseAr '84.9700' -> exclu_use_ar=84.97 (float)."""
    from pipeline.processors.normalizer import normalize_trade_item
    item = {"aptNm": "은마", "umdNm": "대치동", "dealAmount": "55,000",
            "excluUseAr": "84.9700", "dealMonth": "3", "dealYear": "2024",
            "buildYear": "1979", "jibun": "", "roadNm": ""}
    result = normalize_trade_item(item)
    assert isinstance(result["exclu_use_ar"], float)
    assert abs(result["exclu_use_ar"] - 84.97) < 0.01


@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_normalize_trade_deal_month_padding():
    """dealMonth '1' -> deal_month='01' (zero-padded to 2 digits)."""
    from pipeline.processors.normalizer import normalize_trade_item
    item = {"aptNm": "은마", "umdNm": "대치동", "dealAmount": "55,000",
            "excluUseAr": "84.9700", "dealMonth": "1", "dealYear": "2024",
            "buildYear": "", "jibun": "", "roadNm": ""}
    result = normalize_trade_item(item)
    assert result["deal_month"] == "01"
    assert result["deal_ym"] == "202401"


@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_normalize_rent_deposit():
    """deposit '30,000' -> deposit=30000 (int, comma stripped)."""
    from pipeline.processors.normalizer import normalize_rent_item
    item = {"aptNm": "은마", "umdNm": "대치동", "deposit": "30,000",
            "excluUseAr": "84.9700", "dealMonth": "3", "dealYear": "2024",
            "buildYear": "", "jibun": "", "roadNm": "", "monthlyRent": "0"}
    result = normalize_rent_item(item)
    assert result["deposit"] == 30000
    assert isinstance(result["deposit"], int)


# --- PRICE-03: Aggregation tests ---

@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_aggregate_monthly_grouping():
    """Two items with same (apt_nm, umd_nm, deal_ym, exclu_use_ar) collapse to one row."""
    from pipeline.processors.normalizer import aggregate_monthly
    items = [
        {"apt_nm": "은마", "umd_nm": "대치동", "deal_ym": "202401",
         "exclu_use_ar": 84.97, "price": 55000, "deposit": None,
         "monthly_rent": None, "floor": 10, "build_year": 1979,
         "jibun": "", "road_nm": "", "deal_year": 2024, "deal_month": "01"},
        {"apt_nm": "은마", "umd_nm": "대치동", "deal_ym": "202401",
         "exclu_use_ar": 84.97, "price": 57000, "deposit": None,
         "monthly_rent": None, "floor": 5, "build_year": 1979,
         "jibun": "", "road_nm": "", "deal_year": 2024, "deal_month": "01"},
    ]
    result = aggregate_monthly(items, "trade")
    assert len(result) == 1
    assert result[0]["deal_count"] == 2


@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_aggregate_monthly_stats():
    """aggregate_monthly computes correct min/max/avg for trade."""
    from pipeline.processors.normalizer import aggregate_monthly
    items = [
        {"apt_nm": "은마", "umd_nm": "대치동", "deal_ym": "202401",
         "exclu_use_ar": 84.97, "price": 55000, "deposit": None,
         "monthly_rent": None, "floor": 10, "build_year": 1979,
         "jibun": "", "road_nm": "", "deal_year": 2024, "deal_month": "01"},
        {"apt_nm": "은마", "umd_nm": "대치동", "deal_ym": "202401",
         "exclu_use_ar": 84.97, "price": 57000, "deposit": None,
         "monthly_rent": None, "floor": 5, "build_year": 1979,
         "jibun": "", "road_nm": "", "deal_year": 2024, "deal_month": "01"},
    ]
    result = aggregate_monthly(items, "trade")
    row = result[0]
    assert row["price_min"] == 55000
    assert row["price_max"] == 57000
    assert row["price_avg"] == 56000.0


# --- PRICE-01/02: Month range test ---

@pytest.mark.xfail(strict=False, reason="normalizer not yet implemented")
def test_month_range_bounds():
    """get_month_range('200601') starts at '200601' and ends before current calendar month."""
    from pipeline.processors.normalizer import get_month_range
    from datetime import datetime, timedelta
    months = get_month_range("200601")
    assert months[0] == "200601"
    prev = datetime.now().replace(day=1) - timedelta(days=1)
    expected_end = prev.strftime("%Y%m")
    assert months[-1] == expected_end
    current_ym = datetime.now().strftime("%Y%m")
    assert current_ym not in months


# --- PRICE-01: Storage upsert tests (in-memory DB) ---

@pytest.mark.xfail(strict=False, reason="repository not yet implemented")
def test_upsert_apartment_new():
    """upsert_apartment inserts a new apartment and returns a positive integer id."""
    from pipeline.storage.repository import upsert_apartment
    conn = init_db(":memory:")
    apt_id = upsert_apartment(conn, "11680", "은마", "대치동", jibun="1", road_nm="", build_year=1979)
    assert isinstance(apt_id, int)
    assert apt_id > 0


@pytest.mark.xfail(strict=False, reason="repository not yet implemented")
def test_upsert_apartment_idempotent():
    """upsert_apartment returns the same id on a second call for the same apartment."""
    from pipeline.storage.repository import upsert_apartment
    conn = init_db(":memory:")
    id1 = upsert_apartment(conn, "11680", "은마", "대치동")
    id2 = upsert_apartment(conn, "11680", "은마", "대치동")
    assert id1 == id2


@pytest.mark.xfail(strict=False, reason="repository not yet implemented")
def test_insert_monthly_prices_no_dup():
    """insert_monthly_prices does not insert duplicate rows for the same (apt_id, deal_type, deal_ym, exclu_use_ar)."""
    from pipeline.storage.repository import upsert_apartment, insert_monthly_prices
    conn = init_db(":memory:")
    apt_id = upsert_apartment(conn, "11680", "은마", "대치동")
    row = {"deal_type": "trade", "deal_ym": "202401", "exclu_use_ar": 84.97,
           "price_min": 55000, "price_max": 57000, "price_avg": 56000.0,
           "deal_count": 2, "deposit_min": None, "deposit_max": None, "deposit_avg": None}
    n1 = insert_monthly_prices(conn, apt_id, [row])
    n2 = insert_monthly_prices(conn, apt_id, [row])
    assert n1 == 1
    assert n2 == 0


# --- BLDG-01/02: Building info tests (in-memory DB) ---

@pytest.mark.xfail(strict=False, reason="repository not yet implemented")
def test_upsert_building_info():
    """upsert_building_info inserts a building_info row linked by apartment_id FK."""
    from pipeline.storage.repository import upsert_apartment, upsert_building_info
    conn = init_db(":memory:")
    apt_id = upsert_apartment(conn, "11680", "은마", "대치동")
    upsert_building_info(conn, apt_id, {
        "build_year": 1979, "total_households": 4424,
        "floor_area_ratio": 204.85, "building_coverage_ratio": 15.0,
        "total_parking": 2180,
    })
    row = conn.execute("SELECT * FROM building_info WHERE apartment_id=?", (apt_id,)).fetchone()
    assert row is not None
    assert row["build_year"] == 1979
    assert row["total_households"] == 4424


@pytest.mark.xfail(strict=False, reason="repository not yet implemented")
def test_upsert_building_info_replace():
    """upsert_building_info replaces on second call (INSERT OR REPLACE) — updated values survive."""
    from pipeline.storage.repository import upsert_apartment, upsert_building_info
    conn = init_db(":memory:")
    apt_id = upsert_apartment(conn, "11680", "은마", "대치동")
    upsert_building_info(conn, apt_id, {"build_year": 1979, "total_households": 4424,
                                        "floor_area_ratio": None, "building_coverage_ratio": None,
                                        "total_parking": None})
    upsert_building_info(conn, apt_id, {"build_year": 1979, "total_households": 4500,
                                        "floor_area_ratio": 205.0, "building_coverage_ratio": 15.0,
                                        "total_parking": 2200})
    row = conn.execute("SELECT * FROM building_info WHERE apartment_id=?", (apt_id,)).fetchone()
    assert row["total_households"] == 4500
    count = conn.execute("SELECT COUNT(*) FROM building_info WHERE apartment_id=?", (apt_id,)).fetchone()[0]
    assert count == 1
