"""
Storage repository for Phase 2 data collection.

All functions accept an open sqlite3.Connection and are responsible for
their own commit calls.
"""
import sqlite3


def upsert_apartment(conn: sqlite3.Connection, lawd_cd: str, apt_nm: str, umd_nm: str, **kwargs) -> int:
    """
    Insert apartment if not exists. Return apartment_id.

    Uses INSERT OR IGNORE so existing rows are never overwritten.
    Caller may commit after a full batch — this function does NOT commit.

    Args:
        conn: Open sqlite3.Connection.
        lawd_cd: 5-digit district code.
        apt_nm: Apartment complex name (from trade/rent aptNm).
        umd_nm: Legal dong name (from trade/rent umdNm).
        **kwargs: Optional fields: jibun, road_nm, build_year.

    Returns:
        Integer apartment id (> 0).
    """
    conn.execute(
        "INSERT OR IGNORE INTO apartments (lawd_cd, apt_nm, umd_nm, jibun, road_nm, build_year) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            lawd_cd,
            apt_nm,
            umd_nm,
            kwargs.get("jibun"),
            kwargs.get("road_nm"),
            kwargs.get("build_year"),
        ),
    )
    row = conn.execute(
        "SELECT id FROM apartments WHERE lawd_cd=? AND apt_nm=? AND umd_nm=?",
        (lawd_cd, apt_nm, umd_nm),
    ).fetchone()
    return row[0]


def insert_monthly_prices(conn: sqlite3.Connection, apartment_id: int, rows: list) -> int:
    """
    Insert aggregated monthly_prices rows, skipping any already present.

    Deduplication is done at the application level on
    (apartment_id, deal_type, deal_ym, exclu_use_ar) because monthly_prices
    has no UNIQUE constraint.

    Args:
        conn: Open sqlite3.Connection.
        apartment_id: FK to apartments.id.
        rows: List of dicts, each containing:
            deal_type, deal_ym, exclu_use_ar, price_min, price_max, price_avg,
            deal_count, deposit_min, deposit_max, deposit_avg.

    Returns:
        Count of newly inserted rows (0 if all already exist).
    """
    inserted = 0
    for row in rows:
        exists = conn.execute(
            "SELECT 1 FROM monthly_prices "
            "WHERE apartment_id=? AND deal_type=? AND deal_ym=? AND exclu_use_ar=?",
            (apartment_id, row["deal_type"], row["deal_ym"], row["exclu_use_ar"]),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO monthly_prices "
                "(apartment_id, deal_type, deal_ym, exclu_use_ar, "
                " price_min, price_max, price_avg, deal_count, "
                " deposit_min, deposit_max, deposit_avg) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    apartment_id,
                    row["deal_type"],
                    row["deal_ym"],
                    row["exclu_use_ar"],
                    row.get("price_min"),
                    row.get("price_max"),
                    row.get("price_avg"),
                    row["deal_count"],
                    row.get("deposit_min"),
                    row.get("deposit_max"),
                    row.get("deposit_avg"),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def upsert_building_info(conn: sqlite3.Connection, apartment_id: int, bldg: dict) -> None:
    """
    Insert or replace building_info for an apartment.

    Uses INSERT OR REPLACE because building_info has UNIQUE(apartment_id).
    If bldg contains a non-None build_year, also updates apartments.build_year
    since HouseInfo bldYr is more authoritative than the trade-response buildYear.

    Args:
        conn: Open sqlite3.Connection.
        apartment_id: FK to apartments.id.
        bldg: Dict with keys: build_year, total_households, floor_area_ratio,
              building_coverage_ratio, total_parking.
    """
    conn.execute(
        "INSERT OR REPLACE INTO building_info "
        "(apartment_id, build_year, total_households, floor_area_ratio, "
        " building_coverage_ratio, total_parking) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            apartment_id,
            bldg.get("build_year"),
            bldg.get("total_households"),
            bldg.get("floor_area_ratio"),
            bldg.get("building_coverage_ratio"),
            bldg.get("total_parking"),
        ),
    )
    # HouseInfo build_year is authoritative — propagate to apartments table
    build_year = bldg.get("build_year")
    if build_year is not None:
        conn.execute(
            "UPDATE apartments SET build_year=? WHERE id=?",
            (build_year, apartment_id),
        )
    conn.commit()
