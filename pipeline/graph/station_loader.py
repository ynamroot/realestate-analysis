"""
Subway graph construction and BFS stop count utilities.

Data source: 전국도시철도역사정보표준데이터 (data.go.kr/15013205)
XLSX columns used: 역사명, 노선명, 역위도, 역경도, 환승역구분, 환승노선명

Graph model:
  - Node key: "{station_name}_{line_name}" e.g. "강남_2호선"
  - Node attributes: station_name (str), line_name (str), lat (float), lon (float)
  - Sequential edges: weight=1 (riding one stop)
  - Transfer edges: weight=0 (same physical station, different lines)
    Rationale: Korean transit convention counts stations ridden, not transfers.

ANTI-PATTERN: Do NOT use station_name alone as node key.
  "강남" on Line 2 and "강남" on Bundang Line would become the same node,
  making transfer-aware BFS impossible.
"""
from __future__ import annotations

import math

import networkx as nx
import pandas as pd

GBD_STATIONS = ["강남", "역삼", "선릉", "삼성"]
CBD_STATIONS = ["광화문", "종각", "을지로입구", "시청"]
YBD_STATIONS = ["여의도", "국회의사당", "여의나루"]

STRAIGHT_LINE_CUTOFF_M = 1500  # Haversine pre-filter threshold


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return great-circle distance in meters between two WGS84 points.

    Args:
        lat1, lon1: First point (latitude, longitude).
        lat2, lon2: Second point (latitude, longitude).

    Returns:
        Distance in meters.
    """
    R = 6_371_000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_subway_graph_from_df(df: pd.DataFrame) -> nx.Graph:
    """
    Build undirected subway graph from a DataFrame with columns:
      역사명, 노선명, 역위도, 역경도, 환승역구분, 환승노선명

    Node key: "{역사명}_{노선명}" e.g. "강남_2호선"
    Node attributes: station_name, line_name, lat (float), lon (float)
    Sequential edges: weight=1 between consecutive stations on the same line.
    Transfer edges: weight=0 between nodes sharing the same 역사명.

    Args:
        df: DataFrame with 전국도시철도역사정보표준데이터 columns.

    Returns:
        nx.Graph with all stations and connections.
    """
    G: nx.Graph = nx.Graph()

    # Add nodes and sequential edges per line
    for line, group in df.groupby("노선명"):
        stations = group["역사명"].tolist()
        lats = group["역위도"].tolist()
        lons = group["역경도"].tolist()

        for i, stn in enumerate(stations):
            node = f"{stn}_{line}"
            try:
                lat = float(lats[i])
                lon = float(lons[i])
            except (ValueError, TypeError):
                lat, lon = 0.0, 0.0
            G.add_node(node, station_name=str(stn), line_name=str(line), lat=lat, lon=lon)
            if i > 0:
                prev_node = f"{stations[i - 1]}_{line}"
                G.add_edge(prev_node, node, weight=1)

    # Add transfer edges: same 역사명, different 노선명 → weight=0
    by_name: dict[str, list[str]] = {}
    for node, data in G.nodes(data=True):
        by_name.setdefault(data["station_name"], []).append(node)
    for name, nodes in by_name.items():
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                G.add_edge(nodes[i], nodes[j], weight=0)

    return G


def build_subway_graph(xlsx_path: str) -> nx.Graph:
    """
    Load 전국도시철도역사정보표준데이터 XLSX and build subway graph.

    Expected XLSX columns: 역사명, 노선명, 역위도, 역경도, 환승역구분, 환승노선명
    Downloads from data.go.kr/15013205.

    Args:
        xlsx_path: Path to the XLSX file on disk.

    Returns:
        nx.Graph (see build_subway_graph_from_df for structure).
    """
    df = pd.read_excel(xlsx_path, dtype=str)
    return build_subway_graph_from_df(df)


def min_stops(G: nx.Graph, from_station: str, to_stations: list[str]) -> int | None:
    """
    Return minimum stop count from from_station to any station in to_stations.

    Handles multi-line stations by checking all line-specific nodes for both
    source and target. Uses nx.shortest_path_length() which runs BFS on
    unweighted graphs (or weighted BFS via Dijkstra when weights differ).

    Args:
        G: Subway graph from build_subway_graph_from_df().
        from_station: Station name (역사명), e.g. "잠실".
        to_stations: List of target station names, e.g. ["강남", "역삼", "선릉", "삼성"].

    Returns:
        Minimum hop count as int, or None if no path exists.
    """
    src_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == from_station]
    if not src_nodes:
        return None

    best: int | None = None
    for tgt_name in to_stations:
        tgt_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == tgt_name]
        for src in src_nodes:
            for tgt in tgt_nodes:
                try:
                    d = nx.shortest_path_length(G, source=src, target=tgt)
                    if best is None or d < best:
                        best = d
                except nx.NetworkXNoPath:
                    continue
    return best
