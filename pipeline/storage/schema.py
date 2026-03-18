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
            latitude REAL,
            longitude REAL,
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
    migrate_db(conn)
    create_views(conn)
    return conn


def migrate_db(conn: sqlite3.Connection) -> None:
    """Add columns introduced after initial schema creation. Safe to call multiple times."""
    for col, typedef in [("latitude", "REAL"), ("longitude", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE apartments ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass  # Column already exists — ALTER TABLE fails silently


def create_views(conn: sqlite3.Connection) -> None:
    """
    Create analysis views. Safe to call multiple times.
    Uses DROP VIEW IF EXISTS + CREATE VIEW to ensure the definition stays current.
    Called automatically by init_db().

    apartment_analysis VIEW columns:
        apartment_id, lawd_cd, apt_nm, umd_nm, build_year, total_households,
        latitude, longitude,
        latest_trade_ym, latest_trade_price_avg, latest_trade_price_min,
        latest_trade_price_max, latest_trade_deal_count,
        latest_rent_ym, latest_rent_deposit_avg,
        jeonse_ratio_pct,
        nearest_station, stops_to_gbd, stops_to_cbd, stops_to_ybd
    """
    conn.executescript("""
        DROP VIEW IF EXISTS apartment_analysis;

        CREATE VIEW apartment_analysis AS
        SELECT
            a.id                        AS apartment_id,
            a.lawd_cd,
            a.apt_nm,
            a.umd_nm,
            a.build_year,
            a.total_households,
            a.latitude,
            a.longitude,

            -- 최신 매매가 집계 (trade): pre-aggregate across size bands to prevent duplicate rows
            t_agg.deal_ym               AS latest_trade_ym,
            t_agg.price_avg             AS latest_trade_price_avg,
            t_agg.price_min             AS latest_trade_price_min,
            t_agg.price_max             AS latest_trade_price_max,
            t_agg.deal_count            AS latest_trade_deal_count,

            -- 최신 전세가 집계 (rent): same pattern
            r_agg.deal_ym               AS latest_rent_ym,
            r_agg.deposit_avg           AS latest_rent_deposit_avg,

            -- 전세가율 (%): deposit_avg / trade price_avg * 100, NULL-safe
            CASE
                WHEN t_agg.price_avg IS NOT NULL
                     AND t_agg.price_avg > 0
                     AND r_agg.deposit_avg IS NOT NULL
                THEN ROUND(
                         CAST(r_agg.deposit_avg AS REAL) / t_agg.price_avg * 100,
                         1
                     )
                ELSE NULL
            END                         AS jeonse_ratio_pct,

            -- 업무지구 접근성
            cs.nearest_station,
            cs.stops_to_gbd,
            cs.stops_to_cbd,
            cs.stops_to_ybd

        FROM apartments a

        -- Latest trade month: pre-aggregate size bands for that month
        LEFT JOIN (
            SELECT
                apartment_id,
                deal_ym,
                AVG(price_avg)   AS price_avg,
                MIN(price_min)   AS price_min,
                MAX(price_max)   AS price_max,
                SUM(deal_count)  AS deal_count
            FROM monthly_prices
            WHERE deal_type = 'trade'
            GROUP BY apartment_id, deal_ym
        ) t_agg
            ON  t_agg.apartment_id = a.id
            AND t_agg.deal_ym = (
                    SELECT MAX(deal_ym)
                    FROM monthly_prices
                    WHERE apartment_id = a.id
                      AND deal_type = 'trade'
                )

        -- Latest rent month: same pre-aggregate pattern
        LEFT JOIN (
            SELECT
                apartment_id,
                deal_ym,
                AVG(deposit_avg) AS deposit_avg
            FROM monthly_prices
            WHERE deal_type = 'rent'
            GROUP BY apartment_id, deal_ym
        ) r_agg
            ON  r_agg.apartment_id = a.id
            AND r_agg.deal_ym = (
                    SELECT MAX(deal_ym)
                    FROM monthly_prices
                    WHERE apartment_id = a.id
                      AND deal_type = 'rent'
                )

        LEFT JOIN commute_stops cs ON cs.apartment_id = a.id;
    """)
    conn.commit()
