"""
Apartment geocoding collector.

Populates apartments.latitude and apartments.longitude using Kakao Geocoding API.
Idempotent: skips apartments where latitude IS NOT NULL.
Rate: no enforced sleep (Kakao quota is 300k/day — no throttle needed for ~300 apartments).

Usage (sync entry point for CLI):
    from pipeline.collectors.geocode import geocode_all_apartments
    conn = init_db("realestate.db")
    migrate_db(conn)
    summary = geocode_all_apartments(conn)
"""
from __future__ import annotations

import asyncio
import os
import sqlite3

import httpx
from loguru import logger

from pipeline.clients.kakao_geo import KakaoGeoClient
from pipeline.storage.schema import migrate_db


def _build_address(row: sqlite3.Row) -> str:
    """Build address string for geocoding from apartment row fields."""
    umd_nm = row["umd_nm"] or ""
    jibun = row["jibun"] or ""
    road_nm = row["road_nm"] or ""
    if jibun:
        return f"{umd_nm} {jibun}".strip()
    if road_nm:
        return road_nm.strip()
    return umd_nm.strip()


async def geocode_apartment(
    conn: sqlite3.Connection,
    client: httpx.AsyncClient,
    kakao: KakaoGeoClient,
    apt_id: int,
    address: str,
) -> bool:
    """
    Geocode one apartment and update its latitude/longitude.

    Returns True if coordinates were written, False on no-result.
    """
    result = await kakao.geocode(client, address)
    if result is None:
        logger.warning(f"Geocode failed for apt_id={apt_id}: {address!r}")
        return False
    lat, lon = result
    conn.execute(
        "UPDATE apartments SET latitude=?, longitude=? WHERE id=?",
        (lat, lon, apt_id),
    )
    conn.commit()
    return True


def geocode_all_apartments(conn: sqlite3.Connection) -> dict:
    """
    Geocode all apartments where latitude IS NULL.

    Idempotent: apartments already geocoded are skipped.
    Requires KAKAO_REST_API_KEY environment variable.

    Args:
        conn: Open sqlite3.Connection (migrate_db() called internally).

    Returns:
        Summary dict with keys: total (int), geocoded (int), failed (int).
    """
    migrate_db(conn)  # Ensure latitude/longitude columns exist

    api_key = os.getenv("KAKAO_REST_API_KEY", "")
    if not api_key:
        raise RuntimeError("KAKAO_REST_API_KEY environment variable not set")

    kakao = KakaoGeoClient(api_key)
    rows = conn.execute(
        "SELECT id, apt_nm, umd_nm, jibun, road_nm FROM apartments WHERE latitude IS NULL"
    ).fetchall()

    summary = {"total": len(rows), "geocoded": 0, "failed": 0}
    if not rows:
        logger.info("No apartments need geocoding — all have coordinates")
        return summary

    async def _run() -> None:
        async with httpx.AsyncClient() as client:
            for row in rows:
                address = _build_address(row)
                ok = await geocode_apartment(conn, client, kakao, row["id"], address)
                if ok:
                    summary["geocoded"] += 1
                else:
                    summary["failed"] += 1

    asyncio.run(_run())
    logger.info(
        f"Geocoding complete: {summary['geocoded']}/{summary['total']} succeeded, "
        f"{summary['failed']} failed"
    )
    return summary
