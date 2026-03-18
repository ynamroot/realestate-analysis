"""Subway graph builder — stub. Implemented in Phase 3 Wave 1."""
from __future__ import annotations
import networkx as nx

GBD_STATIONS = ["강남", "역삼", "선릉", "삼성"]
CBD_STATIONS = ["광화문", "종각", "을지로입구", "시청"]
YBD_STATIONS = ["여의도", "국회의사당", "여의나루"]

def build_subway_graph(xlsx_path: str) -> nx.Graph:
    raise NotImplementedError("Implemented in Wave 1")

def build_subway_graph_from_df(df) -> nx.Graph:
    raise NotImplementedError("Implemented in Wave 1")

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    raise NotImplementedError("Implemented in Wave 1")

def min_stops(G: nx.Graph, from_station: str, to_stations: list[str]) -> int | None:
    raise NotImplementedError("Implemented in Wave 1")
