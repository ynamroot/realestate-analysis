"""
SQLite schema initialization for the real estate pipeline.

Usage:
    python -c "from pipeline.storage.schema import init_db; init_db()"
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("realestate.db")


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Create all 6 pipeline tables and indexes. Safe to call multiple times
    (CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS).

    Args:
        db_path: Path to SQLite file, or ":memory:" for in-memory DB.

    Returns:
        Open sqlite3.Connection with row_factory=sqlite3.Row set.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            apt_nm TEXT NOT NULL,
            umd_nm TEXT,
            jibun TEXT,
            road_nm TEXT,
            build_year INTEGER,
            total_households INTEGER,
            floor_area_ratio REAL,
            building_coverage_ratio REAL,
            total_parking INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lawd_cd, apt_nm, umd_nm)
        );

        CREATE TABLE IF NOT EXISTS monthly_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            deal_type TEXT NOT NULL CHECK(deal_type IN ('trade','rent')),
            deal_ym TEXT NOT NULL,
            exclu_use_ar REAL,
            price_min INTEGER,
            price_max INTEGER,
            price_avg REAL,
            deal_count INTEGER,
            deposit_min INTEGER,
            deposit_max INTEGER,
            deposit_avg REAL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS building_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            build_year INTEGER,
            total_households INTEGER,
            floor_area_ratio REAL,
            building_coverage_ratio REAL,
            total_parking INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id)
        );

        CREATE TABLE IF NOT EXISTS subway_distances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            station_name TEXT NOT NULL,
            line_name TEXT,
            walk_distance_m INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id, station_name)
        );

        CREATE TABLE IF NOT EXISTS commute_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            nearest_station TEXT NOT NULL,
            stops_to_gbd INTEGER,
            stops_to_cbd INTEGER,
            stops_to_ybd INTEGER,
            calculated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id)
        );

        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            deal_ym TEXT NOT NULL,
            data_type TEXT NOT NULL,
            collected_at TEXT DEFAULT (datetime('now')),
            record_count INTEGER DEFAULT 0,
            UNIQUE(lawd_cd, deal_ym, data_type)
        );

        CREATE INDEX IF NOT EXISTS idx_apartments_lawd
            ON apartments(lawd_cd);

        CREATE INDEX IF NOT EXISTS idx_monthly_prices_apt
            ON monthly_prices(apartment_id, deal_ym);

        CREATE INDEX IF NOT EXISTS idx_monthly_prices_type
            ON monthly_prices(deal_type, deal_ym);

        CREATE INDEX IF NOT EXISTS idx_collection_log_key
            ON collection_log(lawd_cd, deal_ym, data_type);
    """)
    conn.commit()
    return conn
