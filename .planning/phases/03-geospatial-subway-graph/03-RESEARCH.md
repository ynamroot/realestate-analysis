# Phase 3: Geospatial + Subway Graph - Research

**Researched:** 2026-03-18T02:04:47Z
**Domain:** Naver/TMAP walking distance API, Seoul subway GTFS data, networkx BFS graph, apartment geocoding
**Confidence:** MEDIUM (API quotas verified, endpoint structure verified, GTFS data source confirmed; GTX-A GTFS coverage LOW)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUBW-01 | Naver Maps API(도보 경로)로 각 아파트에서 반경 1km 이내 지하철역 거리 수집 | TMAP Pedestrian API confirmed: POST `https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1` — returns `totalDistance` in meters; Naver Maps walking API free quota ended 2025-07-01; TMAP is the recommended alternative |
| SUBW-02 | 호선별로 분리하여 subway_distances 테이블 적재 (1km 초과 시 null) | Schema already exists in schema.py with `UNIQUE(apartment_id, station_name)` — one row per (apartment, station); line_name column stores 호선; walk_distance_m is NULL when >1km |
| SUBW-03 | Naver API 응답 캐싱 — 동일 아파트 재요청 방지 (rate limit 1 req/sec) | Cache via `SELECT 1 FROM subway_distances WHERE apartment_id=? AND station_name=?` before calling TMAP; insert on miss; `asyncio.sleep(1.0)` between calls to respect 1,000 req/day limit |
| COMM-01 | 전국 지하철 노선 그래프 내장 (서울 GTFS 기반, GTX-A 포함) — networkx BFS | 전국도시철도역사정보표준데이터 (data.go.kr 15013205, updated 2024-12-31) provides station lat/lon + transfer info in XLSX; networkx.Graph() with `shortest_path_length()` for BFS stop count |
| COMM-02 | GBD 대표역(강남/역삼/선릉/삼성)까지 최단 정거장 수 (환승 포함) | BFS from nearest_station node → min over [강남, 역삼, 선릉, 삼성] targets using `nx.shortest_path_length(G, source, target)` |
| COMM-03 | CBD 대표역(광화문/종각/을지로입구/시청)까지 최단 정거장 수 (환승 포함) | Same BFS pattern → min over [광화문, 종각, 을지로입구, 시청] |
| COMM-04 | YBD 대표역(여의도/국회의사당/여의나루)까지 최단 정거장 수 (환승 포함) | Same BFS pattern → min over [여의도, 국회의사당, 여의나루] |
| COMM-05 | commute_stops 테이블에 업무지구별 최단값 적재 | Schema already exists with `UNIQUE(apartment_id)` — INSERT OR REPLACE per apartment |
</phase_requirements>

---

## Summary

Phase 3 has two independent sub-problems: (1) fetching walking distances from each apartment to nearby subway stations via an external API, and (2) computing BFS stop counts to three business districts using an in-memory networkx graph built from public station data.

**Critical finding on Naver Maps API:** The Naver Cloud Platform Maps API free quota was terminated on 2025-07-01. All Maps API usage is now 100% paid. This makes Naver unsuitable for a batch pipeline that calls 300+ apartments × ~5 stations = 1,500+ routes. The recommended replacement is the **TMAP Pedestrian API** (SK Telecom), which has a confirmed free quota of 1,000 requests/day and a well-documented REST endpoint. The STATE.md research flag about Naver Direction5 is now resolved: switch to TMAP.

**GTX-A data gap:** The primary public data source (`전국도시철도역사정보표준데이터`, data.go.kr/15013205, last updated 2024-12-31) contains station lat/lon and transfer info but GTX-A coverage is uncertain. GTX-A Phase 1 (수서-동탄) opened 2024-03-30 and Phase 2 (운정중앙-서울역) opened 2024-12-28, but the dataset may not yet include these stations. The planner must treat GTX-A as a manual supplement.

**Apartment geocoding gap:** The `apartments` table has no `latitude`/`longitude` columns. Walking distance calculation requires apartment coordinates. Phase 3 must either (a) geocode apartments using address fields (`umd_nm`, `jibun`, `road_nm`) via the MOLIT Geocoder API or Kakao/TMAP geocoding, or (b) get coordinates from the MOLIT trade API response (some records include `lat`/`lng` fields). This is a design decision for the planner.

**Primary recommendation:** (1) Use TMAP Pedestrian API for walking distances. (2) Add `latitude REAL, longitude REAL` columns to `apartments` table and geocode using MOLIT Geocoder API or Kakao geocoding. (3) Build the subway graph from `전국도시철도역사정보표준데이터` XLSX with manual GTX-A supplement. (4) Use `nx.shortest_path_length()` (BFS for unweighted graph) for stop counts.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.25.2 | Async HTTP calls to TMAP Pedestrian API | Already in codebase; same pattern as MolitClient |
| networkx | >=3.0 | Subway graph, BFS shortest_path_length | Standard graph library; confirmed for transit modeling; pure Python |
| openpyxl | >=3.1.0 | Read 전국도시철도역사정보표준데이터 XLSX | networkx graph data source is XLSX format; openpyxl is pandas dependency |
| pandas | >=2.0 | Read XLSX station data, process rows | Already in project for analysis; cleaner than openpyxl direct |
| sqlite3 | stdlib | subway_distances + commute_stops upserts | Already in codebase from Phase 1/2 |
| asyncio | stdlib | Rate-limiting sleep between TMAP calls | Same asyncio.run() pattern as Phase 2 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math | stdlib | Haversine formula for 1km pre-filter | Avoid API calls for stations >1km (straight-line) before TMAP walk call |
| loguru | >=0.7.2 | Progress logging during slow API batch | Already in codebase |
| python-dotenv | >=1.0.0 | Load TMAP_APP_KEY from .env | Already in codebase |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TMAP Pedestrian API | Naver Maps Direction API | Naver free quota ended 2025-07-01; 100% paid now; TMAP has 1,000/day free |
| TMAP Pedestrian API | Straight-line Haversine only | Haversine underestimates walk distance by 20-40% in dense urban grid; inaccurate for "1km 이내" threshold |
| TMAP Pedestrian API | OSM + Valhalla/OSRM self-hosted | Requires self-hosted routing server; overkill for batch pipeline |
| networkx BFS | Manual BFS loop | `nx.shortest_path_length()` is already BFS for unweighted graphs; no hand-rolling needed |
| pandas read_excel | openpyxl direct | pandas.read_excel is cleaner; both use openpyxl internally |

**Installation:**

```bash
pip install networkx>=3.0 pandas openpyxl
# httpx, python-dotenv, loguru already installed
```

---

## Architecture Patterns

### Recommended Module Structure

```
pipeline/
├── clients/
│   └── tmap.py            # TmapClient — async POST to pedestrian endpoint
├── collectors/
│   ├── subway_distances.py # collect_subway_distances() — per apartment, per station
│   └── commute_stops.py   # collect_commute_stops() — BFS from nearest station
├── graph/
│   ├── __init__.py
│   ├── station_loader.py  # load_station_graph() — reads XLSX, builds nx.Graph
│   └── subway_graph.gml   # (optional) pre-built graph cached to disk
└── data/
    └── stations.xlsx      # 전국도시철도역사정보표준데이터 (downloaded manually from data.go.kr/15013205)
```

All new modules inside `pipeline/` — consistent with Phase 1/2 layout.

### Pattern 1: TMAP Pedestrian API Call

**What:** POST to `https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1` with apartment and station coordinates; parse `totalDistance` from response features.

**When to use:** For each (apartment, station) pair where straight-line distance <= 1.5km (pre-filter with haversine).

```python
# Source: skopenapi.readme.io reference confirmed (MEDIUM confidence)
import httpx

TMAP_PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"

async def get_walk_distance_m(
    client: httpx.AsyncClient,
    app_key: str,
    start_x: float,  # longitude
    start_y: float,  # latitude
    end_x: float,
    end_y: float,
) -> int | None:
    """
    Call TMAP Pedestrian API. Returns total walking distance in meters, or None on failure.

    NOTE: startX/endX = longitude, startY/endY = latitude (WGS84GEO).
    NOTE: totalDistance is in the first feature's properties (pointType='SP').
    """
    headers = {
        "appKey": app_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "startX": start_x,
        "startY": start_y,
        "endX": end_x,
        "endY": end_y,
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "startName": "start",
        "endName": "end",
    }
    resp = await client.post(TMAP_PEDESTRIAN_URL, headers=headers, json=body, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    # totalDistance is in properties of first feature (SP point)
    features = data.get("features", [])
    for feat in features:
        props = feat.get("properties", {})
        if props.get("pointType") == "SP":
            return int(props.get("totalDistance", 0)) or None
    return None
```

### Pattern 2: Haversine Pre-Filter (1.5km Cutoff)

**What:** Before calling TMAP, compute straight-line distance. Skip API call if > 1.5km (walk distance will always exceed 1km if straight-line > 1.5km).

**When to use:** Every (apartment, station) pair before TMAP call. Avoids wasting quota on stations clearly out of range.

```python
# Source: math stdlib — standard haversine formula
import math

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in meters between two WGS84 points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# Pre-filter: skip TMAP call if straight-line > 1500m
# Walk distance is typically 1.2-1.4x straight-line in Seoul's grid
STRAIGHT_LINE_CUTOFF_M = 1500
```

### Pattern 3: Subway Graph Construction with networkx

**What:** Load 전국도시철도역사정보표준데이터 XLSX into a networkx.Graph where each node is a (station_name, line_name) pair and edges connect sequential stations on the same line, plus zero-cost transfer edges between nodes sharing the same station_name.

**When to use:** Once at startup; graph is module-level singleton (no re-loading per apartment).

```python
# Source: networkx 3.x docs + transit graph modeling research (MEDIUM confidence)
import networkx as nx
import pandas as pd

def build_subway_graph(xlsx_path: str) -> nx.Graph:
    """
    Build an undirected subway graph from 전국도시철도역사정보표준데이터 XLSX.

    Node key: "{station_name}_{line_name}" (e.g., "강남_2호선")
    Node attributes: station_name, line_name, lat, lon
    Edges:
      - Sequential on same line: weight=1 (one stop)
      - Transfer (same physical station, different lines): weight=0
        (or weight=1 if planner prefers to count transfers as a stop)

    Returns:
        nx.Graph with all stations and connections.
    """
    df = pd.read_excel(xlsx_path, dtype=str)
    # Column mapping (from 전국도시철도역사정보표준데이터 confirmed fields):
    # 역사명, 노선명, 역위도, 역경도, 환승역구분, 환승노선명
    G = nx.Graph()

    # Group by line, sort by station sequence, add edges
    for line, group in df.groupby("노선명"):
        stations = group["역사명"].tolist()
        for i, stn in enumerate(stations):
            node = f"{stn}_{line}"
            G.add_node(node, station_name=stn, line_name=line)
            if i > 0:
                prev_node = f"{stations[i-1]}_{line}"
                G.add_edge(prev_node, node, weight=1)

    # Add transfer edges: same station_name across different lines
    by_name: dict[str, list[str]] = {}
    for node, data in G.nodes(data=True):
        by_name.setdefault(data["station_name"], []).append(node)
    for name, nodes in by_name.items():
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                G.add_edge(nodes[i], nodes[j], weight=0)  # transfer = 0 stops

    return G
```

### Pattern 4: BFS Stop Count to Business Districts

**What:** For a given apartment's nearest station, find the minimum stop count to any of the target stations for each business district.

```python
# Source: networkx docs — shortest_path_length is BFS for unweighted graphs (HIGH confidence)
import networkx as nx

GBD_STATIONS = ["강남", "역삼", "선릉", "삼성"]
CBD_STATIONS = ["광화문", "종각", "을지로입구", "시청"]
YBD_STATIONS = ["여의도", "국회의사당", "여의나루"]

def stops_to_district(
    G: nx.Graph,
    nearest_station: str,  # e.g., "잠실"
    district_stations: list[str],
) -> int | None:
    """
    Return minimum stop count from nearest_station to any district target.

    Uses nx.shortest_path_length which runs BFS on unweighted graph.
    Returns None if no path found (disconnected graph).
    """
    min_stops = None
    # Resolve all nodes for the nearest station (may be on multiple lines)
    source_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == nearest_station]
    if not source_nodes:
        return None

    for target_name in district_stations:
        target_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == target_name]
        for src in source_nodes:
            for tgt in target_nodes:
                try:
                    d = nx.shortest_path_length(G, source=src, target=tgt)
                    if min_stops is None or d < min_stops:
                        min_stops = d
                except nx.NetworkXNoPath:
                    continue
    return min_stops
```

### Pattern 5: Rate-Limited Subway Distance Collection Loop

**What:** For each apartment, find its nearest stations (haversine pre-filter), call TMAP API, cache results.

```python
# Source: project research — same idempotency pattern as Phase 2 collectors
import asyncio
import sqlite3
import httpx
from pipeline.storage.schema import init_db

async def collect_subway_distances_for_apartment(
    conn: sqlite3.Connection,
    client: httpx.AsyncClient,
    app_key: str,
    apt_id: int,
    apt_lat: float,
    apt_lon: float,
    stations: list[dict],  # [{name, line, lat, lon}]
) -> int:
    """
    Collect walking distances from one apartment to all nearby stations.

    Returns number of subway_distances rows inserted.
    Skips stations already cached in DB.
    Sleeps 1.0s after each TMAP call to respect 1,000/day quota.
    """
    inserted = 0
    for stn in stations:
        # Check cache first (SUBW-03)
        cached = conn.execute(
            "SELECT 1 FROM subway_distances WHERE apartment_id=? AND station_name=?",
            (apt_id, stn["name"]),
        ).fetchone()
        if cached:
            continue

        # Haversine pre-filter
        dist_straight = haversine_m(apt_lat, apt_lon, stn["lat"], stn["lon"])
        if dist_straight > STRAIGHT_LINE_CUTOFF_M:
            # Record as NULL (out of range — no API call needed)
            conn.execute(
                "INSERT OR IGNORE INTO subway_distances "
                "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?,?,?,NULL)",
                (apt_id, stn["name"], stn["line"]),
            )
            conn.commit()
            continue

        walk_m = await get_walk_distance_m(client, app_key, apt_lon, apt_lat, stn["lon"], stn["lat"])
        walk_m_stored = walk_m if walk_m is not None and walk_m <= 1000 else None
        conn.execute(
            "INSERT OR IGNORE INTO subway_distances "
            "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?,?,?,?)",
            (apt_id, stn["name"], stn["line"], walk_m_stored),
        )
        conn.commit()
        inserted += 1
        await asyncio.sleep(1.0)  # 1 req/sec — TMAP 1,000/day limit

    return inserted
```

### Anti-Patterns to Avoid

- **Calling TMAP for every station without haversine pre-filter:** 300 apartments × 50 nearby stations = 15,000 API calls per run, exhausting the 1,000/day quota in 1 apartment. Always pre-filter with haversine at 1.5km.
- **Single node per station (ignoring lines):** BFS on a graph where "강남" is one node loses transfer cost information. Node key must be "{station_name}_{line_name}".
- **Transfer edges with weight=1:** Adding weight=1 to transfer edges means transferring costs a stop. The requirement is "최단 정거장 수 (환승 포함)" — transfers are free in terms of stop count; use weight=0 for transfer edges.
- **Missing apartment coordinates:** The `apartments` table has no lat/lon. Phase 3 must geocode apartments before collecting distances. This must be addressed in Wave 0 (schema migration or separate geocoding step).
- **Re-building the graph per apartment:** Build networkx graph once at module level; reuse for all apartments. Loading XLSX per apartment would be catastrophically slow (~1,000 rows × 300 apartments = 300,000 XLSX reads).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Walking distance | Straight-line haversine only | TMAP Pedestrian API → `totalDistance` | Haversine underestimates by 20-40% in urban grid; fails the "실제 도보거리" requirement |
| BFS stop count | Manual BFS loop with deque | `nx.shortest_path_length(G, src, tgt)` | networkx already uses BFS for unweighted graphs; handles disconnected graphs with NetworkXNoPath |
| Transit graph from scratch | Hard-code all edges manually | Build from 전국도시철도역사정보표준데이터 XLSX | 600+ stations; manual coding is unmaintainable and error-prone |
| API rate limiting | Complex token bucket | `asyncio.sleep(1.0)` between calls | 1,000/day = ~0.012/sec; 1 second sleep is sufficient and simple |
| Apartment coordinates | Custom geocoder | MOLIT Geocoder API (data.go.kr/15101106) or Kakao geocoding | Handles Korean jibun/road addresses; government API is free up to 40,000/day |

---

## Common Pitfalls

### Pitfall 1: TMAP Coordinate Order (X=longitude, Y=latitude)

**What goes wrong:** Passing (latitude, longitude) as (startX, startY) returns a route on the wrong continent.

**Why it happens:** TMAP uses X=longitude, Y=latitude — opposite of the common (lat, lon) convention. The API does not validate coordinate range.

**How to avoid:** Always pass `startX=longitude, startY=latitude, endX=longitude, endY=latitude`. The Korean coordinate range is approximately lon 126-130, lat 34-38.

**Warning signs:** API returns a route but totalDistance is in the thousands of km.

### Pitfall 2: Missing Apartment Coordinates — Geocoding Required

**What goes wrong:** The `apartments` table has no lat/lon. Phase 3 cannot compute distances without apartment coordinates.

**Why it happens:** Phase 1/2 collected MOLIT transaction data which includes `umd_nm`, `jibun`, `road_nm` but not coordinates.

**How to avoid:** Add `latitude REAL, longitude REAL` columns to `apartments` (schema migration or in init_db if running fresh), then geocode using MOLIT Geocoder API or Kakao geocoding in Wave 0 of Phase 3 before distance collection.

**Warning signs:** `SELECT latitude FROM apartments LIMIT 1` returns NULL for all rows.

### Pitfall 3: Graph Node Naming Collision on Transfer Stations

**What goes wrong:** Using only `station_name` as graph node key means "강남" on Line 2 and "강남" on Bundang Line are the same node. BFS cannot find paths requiring line transfers correctly.

**Why it happens:** Multi-line stations share the same name. A single node cannot represent both line memberships simultaneously.

**How to avoid:** Use compound key `f"{station_name}_{line_name}"` as node identifier. Add zero-weight transfer edges between nodes sharing the same `station_name`.

**Warning signs:** BFS path from 인덕원 to 강남 always uses only one line, ignoring faster transfers.

### Pitfall 4: TMAP Free Quota Exhaustion (1,000 req/day)

**What goes wrong:** Full collection run (300 apartments × 5 avg stations × 2 runs) = 3,000 calls, blowing the free quota.

**Why it happens:** 300 apartments × ~5 stations within 1.5km haversine = ~1,500 calls per full run. With retries or multiple runs, quota exceeded.

**How to avoid:** (1) Haversine pre-filter reduces calls to true candidates. (2) DB-level cache (`SELECT` before calling) means re-runs are free. (3) If quota is exceeded, the pipeline resumes next day since cached rows persist.

**Warning signs:** TMAP returns HTTP 429 or quota-exceeded error body.

### Pitfall 5: GTX-A Stations Not in Public XLSX

**What goes wrong:** GTX-A 수서-동탄 and 운정중앙-서울역 sections opened in 2024 but may not appear in `전국도시철도역사정보표준데이터` XLSX depending on when it was last synced.

**Why it happens:** Dataset last updated 2024-12-31; GTX-A Phase 2 opened 2024-12-28 — only 3 days before the data snapshot. Station records may have missed the batch update.

**How to avoid:** Download the XLSX and inspect for GTX-A entries. If missing, hardcode GTX-A station data as a supplement dict in `station_loader.py` with confirmed coordinates from the GTX-A official website (`gtx-a.com`).

**Warning signs:** Searching XLSX for "GTX" or "광역급행" returns 0 rows.

### Pitfall 6: Nearest Station for commute_stops May Not Be Unique

**What goes wrong:** An apartment equidistant from two stations on different lines may have two "nearest stations." BFS from the wrong nearest station produces incorrect stop counts.

**Why it happens:** `commute_stops.nearest_station` is a single text field; but apartments near interchange stations may be served by multiple lines.

**How to avoid:** For each apartment, compute BFS stop counts starting from ALL stations within 1km (not just the single nearest). Take the minimum across all starting stations.

---

## Code Examples

### TMAP Pedestrian API — Full Async Call

```python
# Source: skopenapi.readme.io confirmed endpoint and response structure (MEDIUM confidence)
import httpx

TMAP_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"

async def tmap_walk_distance(
    client: httpx.AsyncClient,
    app_key: str,
    from_lon: float, from_lat: float,
    to_lon: float, to_lat: float,
) -> int | None:
    """Return walking distance in meters or None on API error/no-route."""
    resp = await client.post(
        TMAP_URL,
        headers={"appKey": app_key, "Content-Type": "application/json"},
        json={
            "startX": from_lon, "startY": from_lat,
            "endX": to_lon,   "endY": to_lat,
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "startName": "s", "endName": "e",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    for feat in resp.json().get("features", []):
        props = feat.get("properties", {})
        if props.get("pointType") == "SP":
            return int(props.get("totalDistance", 0)) or None
    return None
```

### networkx BFS — Stop Count Between Stations

```python
# Source: networkx 3.x docs — shortest_path_length uses BFS for unweighted graphs (HIGH confidence)
import networkx as nx

def min_stops(G: nx.Graph, from_station: str, to_stations: list[str]) -> int | None:
    """
    Find minimum stop count from from_station to any of to_stations.
    Handles multi-line stations by checking all line-specific nodes.
    """
    src_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == from_station]
    best = None
    for tgt_name in to_stations:
        tgt_nodes = [n for n in G.nodes if G.nodes[n]["station_name"] == tgt_name]
        for s in src_nodes:
            for t in tgt_nodes:
                try:
                    d = nx.shortest_path_length(G, s, t)
                    if best is None or d < best:
                        best = d
                except nx.NetworkXNoPath:
                    continue
    return best
```

### Haversine Pre-Filter

```python
# Source: math stdlib — standard formula (HIGH confidence)
import math

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(df/2)**2 + math.cos(f1)*math.cos(f2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))
```

### Apartment Coordinates — Schema Migration

```sql
-- Run once before Phase 3 collection starts
-- (init_db already creates tables; this adds missing columns to existing DB)
ALTER TABLE apartments ADD COLUMN latitude REAL;
ALTER TABLE apartments ADD COLUMN longitude REAL;
```

### Station Data XLSX — Key Column Names (전국도시철도역사정보표준데이터)

```python
# Source: data.go.kr/15013205 field documentation (MEDIUM confidence)
# Confirmed columns: 역번호, 역사명, 노선번호, 노선명, 영문역사명,
#   한자역사명, 환승역구분, 환승노선번호, 환승노선명, 역위도, 역경도,
#   운영기관명, 역사도로명주소, 역사전화번호, 데이터기준일자
STATION_XLSX_COLUMNS = {
    "역사명": "station_name",
    "노선명": "line_name",
    "역위도": "latitude",     # WGS84
    "역경도": "longitude",    # WGS84
    "환승역구분": "is_transfer",
    "환승노선명": "transfer_lines",  # comma-separated line names
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Naver Maps Direction API (무료) | TMAP Pedestrian API | 2025-07-01 (Naver ended free quota) | TMAP replaces Naver for walking routes; same REST pattern |
| Hard-coded 35 station stub (realestate_csv.py) | networkx BFS from XLSX | Phase 3 | Accurate stop counts; maintainable; covers all lines |
| No apartment coordinates | `apartments.latitude/longitude` + geocoding | Phase 3 | Required for distance calculation |
| Naver API (무료 20만건/일) was available | TMAP 1,000/day free tier | 2025-07-01 | Rate limit is now 1 req/sec; caching is mandatory |

**Deprecated/outdated:**
- Naver Maps Direction5 for walking: free quota ended 2025-07-01; do not use unless budget allows paid NCP usage.
- `metro-network` Python library (github.com/ho9science/metro-network): last updated 2017; does not include GTX lines; build graph from scratch instead.

---

## Open Questions

1. **Apartment Geocoding Strategy**
   - What we know: `apartments.jibun`, `umd_nm`, `road_nm` fields exist but coordinates do not. MOLIT Geocoder API (data.go.kr/15101106) provides 40,000 free geocoding calls/day. Kakao Geocoding API is an alternative.
   - What's unclear: Whether the MOLIT Geocoder API returns accurate coordinates for all 29 districts (some older jibun addresses may fail). Whether `road_nm` field is populated in most records.
   - Recommendation: Use MOLIT Geocoder API as primary (government, free, 40k/day). Fall back to Kakao for addresses that fail MOLIT geocoding. This needs a dedicated Wave 0/1 geocoding step before distance collection can begin.

2. **GTX-A Station Coverage in XLSX**
   - What we know: GTX-A Phase 1 (수서-동탄, 5 stations) opened 2024-03-30. Phase 2 (운정중앙-서울역, 5 stations) opened 2024-12-28. Dataset last updated 2024-12-31.
   - What's unclear: Whether GTX-A stations were added to `전국도시철도역사정보표준데이터` in the 2024-12-31 snapshot.
   - Recommendation: Download XLSX first in Wave 0 and inspect. If GTX-A missing, supplement with a hardcoded dict of ~10 stations with official coordinates from gtx-a.com.

3. **Transfer Stop Count Convention**
   - What we know: The requirement says "환승 포함 최단 정거장 수." This is ambiguous about whether transferring itself counts as a stop.
   - What's unclear: Does a transfer count as 0 extra stops (just the stations you travel through) or 1 extra stop (transfer node counted)?
   - Recommendation: Use weight=0 for transfer edges. The standard Korean transit convention counts only the stations you ride through, not the transfer action itself.

4. **commute_stops.nearest_station field semantics**
   - What we know: `nearest_station` TEXT NOT NULL — stores the station name used for BFS calculation.
   - What's unclear: If multiple stations are equidistant from the apartment, which one to store?
   - Recommendation: Store the station that gives the minimum stop count to GBD (most commonly used metric). If tie, store alphabetically first. Or — better — run BFS from all stations within 1km and store only the final minimum values; set `nearest_station` to the station that achieved the GBD minimum.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `pytest tests/test_pipeline_phase3.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUBW-01 | `tmap_walk_distance()` parses `totalDistance` from mock response | unit (mock HTTP) | `pytest tests/test_pipeline_phase3.py::test_tmap_walk_distance_parse -x` | Wave 0 |
| SUBW-01 | `tmap_walk_distance()` returns None on empty features | unit | `pytest tests/test_pipeline_phase3.py::test_tmap_walk_distance_empty -x` | Wave 0 |
| SUBW-02 | `subway_distances` INSERT stores NULL when walk_distance > 1000m | unit (in-memory DB) | `pytest tests/test_pipeline_phase3.py::test_subway_distances_null_over_1km -x` | Wave 0 |
| SUBW-03 | Second call for same (apartment_id, station_name) skips TMAP and returns cached row | unit (in-memory DB) | `pytest tests/test_pipeline_phase3.py::test_subway_distances_cache_hit -x` | Wave 0 |
| COMM-01 | `build_subway_graph()` creates nodes and edges for a 3-station test XLSX | unit | `pytest tests/test_pipeline_phase3.py::test_build_subway_graph -x` | Wave 0 |
| COMM-01 | Transfer edges connect same-name stations on different lines with weight=0 | unit | `pytest tests/test_pipeline_phase3.py::test_subway_graph_transfer_edges -x` | Wave 0 |
| COMM-02/03/04 | `min_stops(G, "잠실", ["강남", "역삼"])` returns correct BFS stop count on test graph | unit | `pytest tests/test_pipeline_phase3.py::test_min_stops_bfs -x` | Wave 0 |
| COMM-02/03/04 | `min_stops()` returns None when no path exists | unit | `pytest tests/test_pipeline_phase3.py::test_min_stops_no_path -x` | Wave 0 |
| COMM-05 | `commute_stops` INSERT OR REPLACE stores correct stops_to_gbd value | unit (in-memory DB) | `pytest tests/test_pipeline_phase3.py::test_commute_stops_upsert -x` | Wave 0 |
| SUBW-01 | `haversine_m()` returns ~3.14km for known Seoul coordinate pair | unit | `pytest tests/test_pipeline_phase3.py::test_haversine_m -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_pipeline_phase3.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_phase3.py` — all 10 tests above (pure function + in-memory DB + mock HTTP)
- [ ] `pipeline/graph/__init__.py` — package marker
- [ ] `pipeline/clients/tmap.py` — stub (import-safe); xfail tests against it
- [ ] `pipeline/data/stations.xlsx` — manual download from data.go.kr/15013205; required before Wave 1 graph builder can run
- [ ] Schema migration: `ALTER TABLE apartments ADD COLUMN latitude REAL; ALTER TABLE apartments ADD COLUMN longitude REAL;`

---

## Sources

### Primary (HIGH confidence)

- `pipeline/storage/schema.py` — exact `subway_distances` and `commute_stops` table schemas confirmed
- `pipeline/clients/molit.py`, `pipeline/collectors/building_info.py` — async httpx pattern, asyncio.run() wrapper, idempotency pattern to reuse
- `skopenapi.readme.io/reference/경로안내-샘플예제` — TMAP Pedestrian API endpoint URL, parameter structure, response `totalDistance` field confirmed
- NetworkX 3.6.1 docs (`networkx.org/documentation/stable`) — `shortest_path_length()` is BFS for unweighted graphs; `nx.NetworkXNoPath` exception
- `data.go.kr/15013205` — 전국도시철도역사정보표준데이터 field list confirmed (역사명, 노선명, 역위도, 역경도, 환승역구분)
- `math` stdlib — haversine formula is standard; no external library needed

### Secondary (MEDIUM confidence)

- TMAP free quota 1,000/day: `openapi.sk.com/products/calc?svcSeq=4&menuSeq=5` (referenced in search; not directly confirmed from current pricing page)
- Naver Maps free quota termination: `fin-ncloud.com/support/notice/all/1644` — confirmed 2025-07-01 free quota ended
- TMAP response JSON structure: `skopenapi.readme.io` sample confirmed `features[0].properties.totalDistance`
- GTX-A station list: `gtx-a.com` confirmed 5 stations per section × 2 sections; data.go.kr coverage uncertain

### Tertiary (LOW confidence)

- Transfer edge weight convention (0 vs 1): based on standard Korean transit counting; not explicitly verified from official source — flag for planner decision
- GTX-A in `전국도시철도역사정보표준데이터` XLSX: search results suggest it exists but 2024-12-28 opening vs 2024-12-31 snapshot is borderline; must verify by downloading

---

## Metadata

**Confidence breakdown:**
- TMAP API endpoint and parameters: MEDIUM — confirmed from sample page; free quota amount from secondary source
- networkx BFS pattern: HIGH — official networkx docs confirmed; standard unweighted shortest path = BFS
- Station data source (전국도시철도역사정보표준데이터): MEDIUM — field list confirmed; GTX-A coverage LOW
- Apartment geocoding requirement: HIGH — `apartments` table confirmed to have no lat/lon; geocoding step is mandatory
- Transfer edge weight convention: LOW — standard practice assumption; needs planner decision

**Research date:** 2026-03-18T02:04:47Z
**Valid until:** 2026-04-18 (TMAP API stable; station data refreshed quarterly; networkx API stable)
