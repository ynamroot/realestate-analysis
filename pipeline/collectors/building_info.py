"""HouseInfo API collector — fetches building metadata from MOLIT RTMSDataSvcAptBldMgm endpoint."""
from __future__ import annotations

import asyncio
import sqlite3
import xml.etree.ElementTree as ET

import httpx
from loguru import logger

from pipeline.clients.molit import MolitClient
from pipeline.config.regions import PIPELINE_REGIONS
from pipeline.storage.repository import upsert_apartment, upsert_building_info
from pipeline.utils.idempotency import is_collected, mark_collected

HOUSEINFO_ENDPOINT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptBldMgm/"
    "getRTMSDataSvcAptBldMgm"
)

_STRIP_SUFFIXES = ["아파트", "APT", "apt"]


def _normalize_apt_name(name: str) -> str:
    """Strip common suffixes and normalize to lowercase for fuzzy matching."""
    n = name.strip()
    for suffix in _STRIP_SUFFIXES:
        if n.endswith(suffix):
            n = n[: -len(suffix)]
    return n.replace(" ", "").lower()


def _safe_int(s: str) -> int | None:
    try:
        return int(s.strip()) if s.strip() else None
    except ValueError:
        return None


def _safe_float(s: str) -> float | None:
    try:
        return float(s.strip()) if s.strip() else None
    except ValueError:
        return None


async def collect_building_info(
    conn: sqlite3.Connection,
    client: httpx.AsyncClient,
    molit: MolitClient,
    lawd_cd: str,
) -> int:
    """
    Fetch building info for all apartments in one district.

    Returns count of building_info rows inserted/replaced.
    Idempotency: uses deal_ym='000000', data_type='building' sentinel.

    Args:
        conn: Open sqlite3.Connection.
        client: An open httpx.AsyncClient (caller manages lifecycle).
        molit: MolitClient instance (provides safe_key for URL construction).
        lawd_cd: 5-digit district code, e.g. "11680".

    Returns:
        Number of building_info rows inserted or replaced.
    """
    if is_collected(conn, lawd_cd, "000000", "building"):
        logger.debug(f"Building info already collected for {lawd_cd} — skipping")
        return 0

    all_items: list[dict] = []
    page = 1
    page_size = 1000

    while True:
        # serviceKey embedded in URL string — do NOT move to params={}
        url = (
            f"{HOUSEINFO_ENDPOINT}?serviceKey={molit.safe_key}"
            f"&LAWD_CD={lawd_cd}&numOfRows={page_size}&pageNo={page}"
        )
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()

        # Parse XML — same pattern as MolitClient._parse_items
        root = ET.fromstring(resp.text)
        items = [
            {child.tag: (child.text or "").strip() for child in item}
            for item in root.findall(".//item")
        ]
        all_items.extend(items)

        if len(items) < page_size:
            break
        page += 1

    # Load existing apartments for this district for name matching
    existing = conn.execute(
        "SELECT id, apt_nm, umd_nm FROM apartments WHERE lawd_cd=?", (lawd_cd,)
    ).fetchall()
    # Build normalized name -> (id, umd_nm) lookup
    name_index: dict[str, tuple] = {
        _normalize_apt_name(row["apt_nm"]): (row["id"], row["umd_nm"])
        for row in existing
    }

    inserted = 0
    for item in all_items:
        buld_nm = item.get("buldNm", "").strip()
        umd_nm = item.get("umdNm", "").strip()

        # Try exact normalized match first
        norm = _normalize_apt_name(buld_nm)
        match = name_index.get(norm)

        # Fallback: prefix match (e.g. "은마" matches "은마1단지" normalized)
        if match is None:
            for key, val in name_index.items():
                if norm and (key.startswith(norm) or norm.startswith(key)):
                    match = val
                    break

        if match is None:
            # No match — insert apartment from HouseInfo data, then upsert building_info
            apt_id = upsert_apartment(conn, lawd_cd, buld_nm, umd_nm)
        else:
            apt_id = match[0]

        bldg = {
            "build_year": _safe_int(item.get("bldYr", "")),
            "total_households": _safe_int(item.get("hhldCnt", "")),
            "floor_area_ratio": _safe_float(item.get("vlRat", "")),
            "building_coverage_ratio": _safe_float(item.get("bcRat", "")),
            "total_parking": _safe_int(item.get("pkngCnt", "")),
        }
        upsert_building_info(conn, apt_id, bldg)
        inserted += 1

    mark_collected(conn, lawd_cd, "000000", "building", record_count=inserted)
    logger.info(f"Building info collected for {lawd_cd}: {inserted} rows")
    return inserted


def collect_all_building_info(
    conn: sqlite3.Connection,
    molit: MolitClient,
) -> dict:
    """
    Run building info collection for all PIPELINE_REGIONS.

    Synchronous entry point — uses asyncio.run() internally.
    Not suitable for calling from within an already-running async context.

    Args:
        conn: Open sqlite3.Connection.
        molit: MolitClient instance.

    Returns:
        Summary dict with keys: total (int), regions (int).
    """
    summary: dict = {"total": 0}

    async def _run() -> None:
        async with httpx.AsyncClient() as client:
            for name, lawd_cd in PIPELINE_REGIONS.items():
                logger.info(f"Collecting building info: {name} ({lawd_cd})")
                n = await collect_building_info(conn, client, molit, lawd_cd)
                summary["total"] += n

    asyncio.run(_run())
    summary["regions"] = len(PIPELINE_REGIONS)
    return summary
