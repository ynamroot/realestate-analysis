"""Subway distance collector — stub. Implemented in Phase 3 Wave 2."""
from __future__ import annotations
import sqlite3
import httpx

async def collect_subway_distances_for_apartment(
    conn: sqlite3.Connection, client: httpx.AsyncClient, app_key: str,
    apt_id: int, apt_lat: float, apt_lon: float, stations: list[dict],
) -> int:
    raise NotImplementedError("Implemented in Wave 2")

def collect_all_subway_distances(conn: sqlite3.Connection) -> dict:
    raise NotImplementedError("Implemented in Wave 2")
