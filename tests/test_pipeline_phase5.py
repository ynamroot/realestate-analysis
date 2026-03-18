"""
Phase 5 tests: subway_distances UNIQUE constraint migration + CLI geocode dispatch.
All tests are xfail until Wave 1 implementation is complete.

Requirements covered:
  SUBW-02: 3-column UNIQUE(apartment_id, station_name, line_name) in subway_distances
  SUBW-01/SUBW-03: geocode dispatch wiring in CLI collect()
  COMM-05: geocode prerequisite ensures subway/commute collectors process real data
"""
import pytest
from pipeline.storage.schema import init_db, migrate_db


# --- SUBW-02: 3-column UNIQUE migration ---

@pytest.mark.xfail(strict=False, reason="migrate_db 3-column UNIQUE not yet implemented")
def test_migrate_subway_unique():
    """migrate_db() changes subway_distances UNIQUE to (apartment_id, station_name, line_name)."""
    conn = init_db(":memory:")
    # After init+migrate, DDL must contain the 3-column constraint
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='subway_distances'"
    ).fetchone()[0]
    assert "station_name, line_name" in ddl, f"Expected 3-column UNIQUE in DDL, got: {ddl}"


@pytest.mark.xfail(strict=False, reason="3-column UNIQUE not yet implemented")
def test_subway_distances_multiline():
    """강남역 can store 2호선 AND 분당선 as separate rows after 3-column UNIQUE fix."""
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm, latitude, longitude) "
        "VALUES ('11680', '은마아파트', '대치동', 37.4940, 127.0634)"
    )
    conn.commit()
    apt_id = conn.execute("SELECT id FROM apartments").fetchone()[0]
    # Insert two rows for 강남역 on different lines — second must NOT be silently dropped
    conn.execute(
        "INSERT OR IGNORE INTO subway_distances "
        "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?, '강남', '2호선', 350)",
        (apt_id,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO subway_distances "
        "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?, '강남', '분당선', 380)",
        (apt_id,),
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM subway_distances WHERE apartment_id=? AND station_name='강남'",
        (apt_id,),
    ).fetchone()[0]
    assert count == 2, f"Expected 2 rows for 강남역 (2호선 + 분당선), got {count}"


# --- SUBW-01/SUBW-03: CLI geocode dispatch ---

@pytest.mark.xfail(strict=False, reason="geocode data_type not yet in CLI dispatch")
def test_collect_geocode_dispatch():
    """collect() with data_type='geocode' invokes geocode_all_apartments path."""
    from unittest.mock import patch, MagicMock
    from typer.testing import CliRunner
    from pipeline.cli.main import app
    runner = CliRunner()
    with patch("pipeline.collectors.geocode.geocode_all_apartments", return_value={"geocoded": 0}) as mock_geo, \
         patch.dict("os.environ", {"KAKAO_REST_API_KEY": "test-key"}):
        result = runner.invoke(app, ["collect", "--data-type", "geocode"])
    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    mock_geo.assert_called_once()


@pytest.mark.xfail(strict=False, reason="geocode not yet wired before subway in CLI")
def test_collect_subway_runs_geocode_first():
    """collect() with data_type='subway' runs geocoding before subway distances."""
    from unittest.mock import patch, call, MagicMock
    from typer.testing import CliRunner
    from pipeline.cli.main import app
    runner = CliRunner()
    call_order = []
    def mock_geo(conn): call_order.append("geocode"); return {"geocoded": 0}
    def mock_subway(conn): call_order.append("subway"); return {"processed": 0}
    def mock_commute(conn): call_order.append("commute"); return {"processed": 0}
    with patch("pipeline.collectors.geocode.geocode_all_apartments", side_effect=mock_geo), \
         patch("pipeline.collectors.subway_distances.collect_all_subway_distances", side_effect=mock_subway), \
         patch("pipeline.collectors.commute_stops.collect_all_commute_stops", side_effect=mock_commute), \
         patch.dict("os.environ", {"KAKAO_REST_API_KEY": "test-key", "TMAP_APP_KEY": "test-key"}):
        result = runner.invoke(app, ["collect", "--data-type", "subway"])
    assert "geocode" in call_order, f"geocode_all_apartments not called. Order: {call_order}"
    assert call_order.index("geocode") < call_order.index("subway"), \
        f"geocode must run before subway. Order was: {call_order}"
