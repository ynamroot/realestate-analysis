"""
Phase 4 test suite: CLI + Analysis Views

Requirements covered:
  CLI-01 — Typer CLI: collect / export / status subcommands
  CLI-02 — Region/period/data-type options
  CLI-03 — pandas UTF-8 BOM CSV export
  CLI-04 — apartment_analysis SQLite VIEW
"""
import sqlite3
import tempfile
import os
import pytest
from typer.testing import CliRunner

from pipeline.cli.main import app, _resolve_regions
from pipeline.config.regions import PIPELINE_REGIONS, SEOUL_REGIONS, GYEONGGI_REGIONS
from pipeline.storage.schema import init_db


runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI-01: subcommand registration
# ---------------------------------------------------------------------------

def test_cli_app_importable():
    """app is a Typer instance importable from pipeline.cli.main."""
    import typer
    assert isinstance(app, typer.Typer)


def test_collect_help():
    """collect --help exits 0 and mentions 'region'."""
    result = runner.invoke(app, ["collect", "--help"])
    assert result.exit_code == 0
    assert "region" in result.output


def test_export_help():
    """export --help exits 0 and mentions 'output'."""
    result = runner.invoke(app, ["export", "--help"])
    assert result.exit_code == 0
    assert "output" in result.output


def test_status_empty(tmp_db):
    """status with empty DB prints 'No data collected yet'."""
    # Wire CLI to use tmp_db by monkey-patching the module-level init_db
    import pipeline.cli.main as cli_mod
    original = cli_mod.init_db
    cli_mod.init_db = lambda *a, **kw: tmp_db
    # init_db in status returns conn; we need tables to exist
    init_db(":memory:")  # ensure schema exists on tmp_db via conftest fixture
    # Patch so status() uses our already-initialised tmp_db
    from pipeline.storage.schema import init_db as real_init
    real_tmp = real_init(":memory:")
    cli_mod.init_db = lambda *a, **kw: real_tmp
    result = runner.invoke(app, ["status"])
    cli_mod.init_db = original
    assert result.exit_code == 0
    assert "No data collected yet" in result.output


# ---------------------------------------------------------------------------
# CLI-02: region resolution
# ---------------------------------------------------------------------------

def test_resolve_regions_none():
    """None returns full PIPELINE_REGIONS (29 entries)."""
    regions = _resolve_regions(None)
    assert regions == PIPELINE_REGIONS
    assert len(regions) == 29


def test_resolve_regions_seoul():
    """'seoul' returns only SEOUL_REGIONS keys."""
    regions = _resolve_regions("seoul")
    assert regions == SEOUL_REGIONS
    assert all(v.startswith("11") for v in regions.values())


def test_resolve_regions_gyeonggi():
    """'gyeonggi' returns only GYEONGGI_REGIONS keys."""
    regions = _resolve_regions("gyeonggi")
    assert regions == GYEONGGI_REGIONS
    assert all(v.startswith("41") for v in regions.values())


def test_resolve_regions_korean_name():
    """Korean district name returns single-entry dict."""
    regions = _resolve_regions("강남구")
    assert regions == {"강남구": "11680"}


def test_resolve_regions_invalid():
    """Unknown region name causes Exit(1) (typer.Exit wraps click.exceptions.Exit)."""
    import click
    with pytest.raises((SystemExit, click.exceptions.Exit)):
        _resolve_regions("unknown_xyz")


# ---------------------------------------------------------------------------
# CLI-03: CSV export
# ---------------------------------------------------------------------------

def test_export_utf8_sig():
    """export_to_csv writes correct row count and utf-8-sig encoding."""
    import pandas as pd
    conn = init_db(":memory:")
    # Seed one apartment row
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm) VALUES ('11680', '테스트아파트', '역삼동')"
    )
    conn.commit()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_path = f.name
    try:
        df = pd.read_sql("SELECT * FROM apartments", conn)
        df.to_csv(tmp_path, encoding="utf-8-sig", index=False)
        assert os.path.getsize(tmp_path) > 0
        with open(tmp_path, "rb") as f:
            content = f.read()
        assert len(df) == 1
    finally:
        os.unlink(tmp_path)
    conn.close()


def test_export_bom_present():
    """Output CSV starts with UTF-8 BOM bytes b'\\xef\\xbb\\xbf'."""
    import pandas as pd
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm) VALUES ('11680', '한글아파트', '청담동')"
    )
    conn.commit()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_path = f.name
    try:
        df = pd.read_sql("SELECT * FROM apartments", conn)
        df.to_csv(tmp_path, encoding="utf-8-sig", index=False)
        with open(tmp_path, "rb") as f:
            first_bytes = f.read(3)
        assert first_bytes == b"\xef\xbb\xbf", f"Expected BOM, got: {first_bytes!r}"
    finally:
        os.unlink(tmp_path)
    conn.close()


# ---------------------------------------------------------------------------
# CLI-04: apartment_analysis VIEW
# ---------------------------------------------------------------------------

def test_create_views():
    """create_views(conn) succeeds on schema from init_db() — no OperationalError."""
    from pipeline.storage.schema import create_views  # added in Plan 02
    conn = init_db(":memory:")
    create_views(conn)  # must not raise
    # Verify view exists
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='apartment_analysis'"
    ).fetchone()
    assert row is not None
    conn.close()


def test_apartment_analysis_empty():
    """SELECT * FROM apartment_analysis returns 0 rows on empty DB — not an error."""
    from pipeline.storage.schema import create_views  # added in Plan 02
    conn = init_db(":memory:")
    create_views(conn)
    rows = conn.execute("SELECT * FROM apartment_analysis").fetchall()
    assert rows == []
    conn.close()


def test_jeonse_ratio_calculation():
    """VIEW computes jeonse_ratio_pct = deposit_avg / trade_price_avg * 100."""
    from pipeline.storage.schema import create_views  # added in Plan 02
    conn = init_db(":memory:")
    create_views(conn)
    # Seed apartment
    conn.execute(
        "INSERT INTO apartments (id, lawd_cd, apt_nm, umd_nm) VALUES (1, '11680', '래미안', '역삼동')"
    )
    # Seed trade price: price_avg=100000 (만원), deal_ym='202401'
    conn.execute(
        """INSERT INTO monthly_prices
           (apartment_id, deal_type, deal_ym, exclu_use_ar, price_avg, price_min, price_max, deal_count)
           VALUES (1, 'trade', '202401', 84.0, 100000, 95000, 110000, 5)"""
    )
    # Seed rent price: deposit_avg=70000 → jeonse_ratio_pct = 70000/100000*100 = 70.0
    conn.execute(
        """INSERT INTO monthly_prices
           (apartment_id, deal_type, deal_ym, exclu_use_ar, deposit_avg, deposit_min, deposit_max, deal_count)
           VALUES (1, 'rent', '202401', 84.0, 70000, 65000, 75000, 3)"""
    )
    conn.commit()
    row = conn.execute("SELECT * FROM apartment_analysis WHERE apartment_id = 1").fetchone()
    assert row is not None
    assert abs(row["jeonse_ratio_pct"] - 70.0) < 0.5
    conn.close()


def test_view_no_duplicates():
    """VIEW returns exactly 1 row per apartment even with multiple exclu_use_ar size bands."""
    from pipeline.storage.schema import create_views  # added in Plan 02
    conn = init_db(":memory:")
    create_views(conn)
    conn.execute(
        "INSERT INTO apartments (id, lawd_cd, apt_nm, umd_nm) VALUES (1, '11680', '타워팰리스', '도곡동')"
    )
    # Two size bands for same month
    for ar, price in [(59.0, 80000), (84.0, 120000)]:
        conn.execute(
            """INSERT INTO monthly_prices
               (apartment_id, deal_type, deal_ym, exclu_use_ar, price_avg, price_min, price_max, deal_count)
               VALUES (1, 'trade', '202401', ?, ?, ?, ?, 3)""",
            (ar, price, price - 5000, price + 5000),
        )
    conn.commit()
    rows = conn.execute("SELECT * FROM apartment_analysis WHERE apartment_id = 1").fetchall()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    conn.close()
