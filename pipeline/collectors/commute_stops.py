"""
Commute stop BFS collector.

For each apartment, computes minimum stop counts to GBD/CBD/YBD using BFS on
the subway graph. Uses all stations within 1km walking distance as potential
starting points (not just single nearest — see Pitfall 6 in 03-RESEARCH.md).

Source: BFS via nx.shortest_path_length (networkx 3.x). Transfer edges weight=0.

Design: collect_commute_stops() is pure (no network calls).
Build graph once and reuse via collect_all_commute_stops() wrapper.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import networkx as nx
from loguru import logger

from pipeline.graph.station_loader import (
    CBD_STATIONS,
    GBD_STATIONS,
    YBD_STATIONS,
    build_subway_graph,
    min_stops,
)

_DEFAULT_XLSX = Path(__file__).parent.parent / "data" / "stations.xlsx"


def collect_commute_stops(
    conn: sqlite3.Connection,
    G: nx.Graph,
    apt_id: int,
) -> bool:
    """
    Compute and store commute stop counts for one apartment.

    Reads subway_distances to find all walk-accessible stations (walk_distance_m IS NOT NULL).
    Runs BFS from each accessible station to GBD/CBD/YBD targets.
    Stores minimum across all starting stations.

    Args:
        conn: Open sqlite3.Connection.
        G: Subway graph from build_subway_graph().
        apt_id: apartments.id.

    Returns:
        True if row was inserted/replaced, False if skipped (already exists or no nearby stations).
    """
    # Idempotency: skip if already computed
    existing = conn.execute(
        "SELECT 1 FROM commute_stops WHERE apartment_id=?", (apt_id,)
    ).fetchone()
    if existing:
        return False

    # Get all walk-accessible stations for this apartment
    nearby = conn.execute(
        "SELECT station_name FROM subway_distances "
        "WHERE apartment_id=? AND walk_distance_m IS NOT NULL",
        (apt_id,),
    ).fetchall()

    if not nearby:
        logger.debug(f"apt_id={apt_id}: no walk-accessible stations, skipping commute_stops")
        return False

    station_names = [row[0] for row in nearby]

    # BFS from each nearby station to each business district — take minimum
    best_gbd: int | None = None
    best_cbd: int | None = None
    best_ybd: int | None = None
    best_gbd_station: str = station_names[0]

    for stn_name in station_names:
        g = min_stops(G, stn_name, GBD_STATIONS)
        c = min_stops(G, stn_name, CBD_STATIONS)
        y = min_stops(G, stn_name, YBD_STATIONS)

        if g is not None and (best_gbd is None or g < best_gbd):
            best_gbd = g
            best_gbd_station = stn_name
        if c is not None and (best_cbd is None or c < best_cbd):
            best_cbd = c
        if y is not None and (best_ybd is None or y < best_ybd):
            best_ybd = y

    conn.execute(
        "INSERT OR REPLACE INTO commute_stops "
        "(apartment_id, nearest_station, stops_to_gbd, stops_to_cbd, stops_to_ybd) "
        "VALUES (?, ?, ?, ?, ?)",
        (apt_id, best_gbd_station, best_gbd, best_cbd, best_ybd),
    )
    conn.commit()
    return True


def collect_all_commute_stops(
    conn: sqlite3.Connection,
    xlsx_path: str | None = None,
) -> dict:
    """
    Compute commute stops for all apartments that have subway_distances data.

    Idempotent: apartments with existing commute_stops rows are skipped.
    Does not require any API calls — pure BFS computation.

    Args:
        conn: Open sqlite3.Connection.
        xlsx_path: Path to stations.xlsx. Defaults to pipeline/data/stations.xlsx.

    Returns:
        Summary dict with keys: total (int), computed (int), skipped (int).
    """
    path = xlsx_path or str(_DEFAULT_XLSX)
    G = build_subway_graph(path)
    logger.info("Subway graph loaded for BFS computation")

    apt_ids = conn.execute(
        "SELECT DISTINCT apartment_id FROM subway_distances"
    ).fetchall()

    summary = {"total": len(apt_ids), "computed": 0, "skipped": 0}

    for row in apt_ids:
        apt_id = row[0]
        ok = collect_commute_stops(conn, G, apt_id)
        if ok:
            summary["computed"] += 1
        else:
            summary["skipped"] += 1

    logger.info(
        f"Commute stops complete: {summary['computed']} computed, "
        f"{summary['skipped']} skipped"
    )
    return summary
