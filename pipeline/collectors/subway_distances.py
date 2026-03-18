"""
Subway walking distance collector.

For each apartment (with latitude/longitude populated), finds all subway stations
within 1.5km straight-line distance, calls TMAP Pedestrian API for actual walking
distance, and stores results in subway_distances table.

Caching: Rows already in subway_distances are skipped (SUBW-03).
Rate limiting: asyncio.sleep(1.0) after each TMAP call (1,000/day quota).
Pre-filter: haversine > 1500m → INSERT with walk_distance_m=NULL (no TMAP call).
Storage: walk_distance_m = TMAP result if ≤ 1000m, else NULL (SUBW-02).
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

import httpx
from loguru import logger

from pipeline.clients.tmap import TmapClient
from pipeline.graph.station_loader import (
    STRAIGHT_LINE_CUTOFF_M,
    build_subway_graph,
    haversine_m,
)

_DEFAULT_XLSX = Path(__file__).parent.parent / "data" / "stations.xlsx"


def _load_stations_from_graph(G) -> list[dict]:
    """Extract unique station records from graph nodes for distance iteration."""
    seen: set[tuple] = set()
    stations: list[dict] = []
    for node, data in G.nodes(data=True):
        if data.get("lat") and data.get("lon") and data["lat"] != 0.0:
            key = (data["station_name"], data["line_name"])
            if key not in seen:
                seen.add(key)
                stations.append({
                    "name": data["station_name"],
                    "line": data["line_name"],
                    "lat": data["lat"],
                    "lon": data["lon"],
                })
    return stations


async def collect_subway_distances_for_apartment(
    conn: sqlite3.Connection,
    client: httpx.AsyncClient,
    tmap: TmapClient,
    apt_id: int,
    apt_lat: float,
    apt_lon: float,
    stations: list[dict],
) -> int:
    """
    Collect walking distances from one apartment to all nearby stations.

    Args:
        conn: Open sqlite3.Connection.
        client: Open httpx.AsyncClient.
        tmap: TmapClient instance.
        apt_id: apartments.id for this apartment.
        apt_lat: Apartment latitude (WGS84).
        apt_lon: Apartment longitude (WGS84).
        stations: List of {name, line, lat, lon} dicts (all known stations).

    Returns:
        Number of NEW subway_distances rows inserted (cache hits excluded).
    """
    inserted = 0
    for stn in stations:
        # SUBW-03: Check cache before any work
        cached = conn.execute(
            "SELECT 1 FROM subway_distances WHERE apartment_id=? AND station_name=? AND line_name=?",
            (apt_id, stn["name"], stn["line"]),
        ).fetchone()
        if cached:
            continue

        # Haversine pre-filter: skip TMAP call if clearly out of range
        straight_m = haversine_m(apt_lat, apt_lon, stn["lat"], stn["lon"])
        if straight_m > STRAIGHT_LINE_CUTOFF_M:
            conn.execute(
                "INSERT OR IGNORE INTO subway_distances "
                "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?,?,?,NULL)",
                (apt_id, stn["name"], stn["line"]),
            )
            conn.commit()
            continue

        # TMAP API call — count against daily quota
        walk_m = await tmap.walk_distance_m(
            client,
            apt_lon, apt_lat,       # from_lon, from_lat (TMAP: X=lon, Y=lat)
            stn["lon"], stn["lat"], # to_lon, to_lat
        )
        # SUBW-02: store NULL if >1000m actual walk; store meters if ≤1000m
        walk_stored = walk_m if (walk_m is not None and walk_m <= 1000) else None
        conn.execute(
            "INSERT OR IGNORE INTO subway_distances "
            "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?,?,?,?)",
            (apt_id, stn["name"], stn["line"], walk_stored),
        )
        conn.commit()
        inserted += 1
        await asyncio.sleep(1.0)  # Rate limit: 1,000 req/day

    return inserted


def collect_all_subway_distances(
    conn: sqlite3.Connection,
    xlsx_path: str | None = None,
) -> dict:
    """
    Collect subway walking distances for all geocoded apartments.

    Skips apartments with NULL latitude/longitude.
    Idempotent: already-cached rows are skipped.
    Requires TMAP_APP_KEY environment variable.

    Args:
        conn: Open sqlite3.Connection (migrate_db already called).
        xlsx_path: Path to stations.xlsx. Defaults to pipeline/data/stations.xlsx.

    Returns:
        Summary dict with keys: apartments (int), inserted (int).
    """
    app_key = os.getenv("TMAP_APP_KEY", "")
    if not app_key:
        raise RuntimeError("TMAP_APP_KEY environment variable not set")

    path = xlsx_path or str(_DEFAULT_XLSX)
    G = build_subway_graph(path)
    stations = _load_stations_from_graph(G)
    logger.info(f"Loaded {len(stations)} unique stations from graph")

    tmap = TmapClient(app_key)
    apts = conn.execute(
        "SELECT id, apt_nm, latitude, longitude FROM apartments WHERE latitude IS NOT NULL"
    ).fetchall()

    summary = {"apartments": len(apts), "inserted": 0}

    async def _run() -> None:
        async with httpx.AsyncClient() as http_client:
            for apt in apts:
                n = await collect_subway_distances_for_apartment(
                    conn, http_client, tmap,
                    apt["id"], apt["latitude"], apt["longitude"],
                    stations,
                )
                summary["inserted"] += n
                if n > 0:
                    logger.info(f"  {apt['apt_nm']}: {n} new distances")

    asyncio.run(_run())
    logger.info(f"Subway distances complete: {summary['inserted']} rows inserted")
    return summary
