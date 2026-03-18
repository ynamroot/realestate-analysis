---
phase: 03-geospatial-subway-graph
plan: "04"
subsystem: subway-collectors
status: complete
completed_at: 2026-03-18T05:19:54Z
tags: [subway-distances, commute-stops, tmap, bfs, idempotent, caching]
dependency_graph:
  requires: [03-01, 03-02, 03-03]
  provides: [collect_all_subway_distances, collect_all_commute_stops]
  affects: []
tech_stack:
  added: []
  patterns: [cache-check-before-api, haversine-prefilter, rate-limit-sleep, bfs-all-nearby, insert-or-replace]
key_files:
  created: []
  modified:
    - pipeline/collectors/subway_distances.py
    - pipeline/collectors/commute_stops.py
decisions:
  - "Cache check uses (apartment_id, station_name, line_name) triple — matches UNIQUE constraint exactly"
  - "Haversine > 1500m inserts NULL without TMAP call (avoids quota waste)"
  - "walk_stored = None when TMAP walk_m > 1000m (1km practical walk threshold)"
  - "asyncio.sleep(1.0) only after real TMAP calls, not after cache hits or haversine skips"
  - "commute_stops BFS iterates ALL nearby stations with walk_distance_m IS NOT NULL (not just nearest)"
  - "nearest_station = station achieving minimum stops_to_gbd"
  - "collect_all_subway_distances loads graph once, passes stations list to per-apartment coroutine"
  - "collect_commute_stops signature takes apt_id explicitly — caller controls which apartment to compute"
test_results:
  total: 10
  passed: 10
  xpassed: 10
  failed: 0
  command: "pytest tests/test_pipeline_phase3.py -v"
requirements_satisfied:
  - SUBW-01
  - SUBW-02
  - SUBW-03
  - COMM-02
  - COMM-03
  - COMM-04
  - COMM-05
duration: "~5m"
tasks_completed: 2
files_modified: 2
---

# Plan 03-04 Summary — Subway Collectors

## What Was Built

Two final data-producing collectors for Phase 3:

### `pipeline/collectors/subway_distances.py`
- `collect_subway_distances_for_apartment()` — async, per-apartment TMAP walking distance collection
- `collect_all_subway_distances()` — sync wrapper, loads graph once, iterates all geocoded apartments
- Cache check: `SELECT 1 ... WHERE apartment_id=? AND station_name=? AND line_name=?` before any work
- Haversine pre-filter: stations > 1500m get NULL inserted without TMAP call
- Rate limiting: `asyncio.sleep(1.0)` after each real TMAP call
- 1km threshold: TMAP result > 1000m stored as NULL

### `pipeline/collectors/commute_stops.py`
- `collect_commute_stops()` — BFS for one apartment using all walk-accessible stations
- `collect_all_commute_stops()` — batch wrapper, builds graph once, iterates all apartments with subway data
- Uses `walk_distance_m IS NOT NULL` rows as BFS starting points (not just nearest station)
- Stores `nearest_station` = station achieving minimum `stops_to_gbd`
- `INSERT OR REPLACE` with `UNIQUE(apartment_id)` constraint

## Test Results

All 10 Phase 3 tests: **10 xpassed** (0 failures)

```
tests/test_pipeline_phase3.py::test_tmap_walk_distance_parse     XPASS
tests/test_pipeline_phase3.py::test_tmap_walk_distance_empty     XPASS
tests/test_pipeline_phase3.py::test_subway_distances_null_over_1km XPASS
tests/test_pipeline_phase3.py::test_subway_distances_cache_hit   XPASS
tests/test_pipeline_phase3.py::test_build_subway_graph           XPASS
tests/test_pipeline_phase3.py::test_subway_graph_transfer_edges  XPASS
tests/test_pipeline_phase3.py::test_min_stops_bfs                XPASS
tests/test_pipeline_phase3.py::test_min_stops_no_path            XPASS
tests/test_pipeline_phase3.py::test_commute_stops_upsert         XPASS
tests/test_pipeline_phase3.py::test_haversine_m                  XPASS
```

## Phase 3 Complete

All 4 plans executed. Phase 3 (geospatial subway graph) is fully implemented:
- 03-01: Schema + DB migration (subway_distances, commute_stops tables)
- 03-02: TMAP client + subway graph builder (BFS, haversine)
- 03-03: Kakao geocoder + stations.xlsx ingest
- 03-04: Subway distance collector + commute stop BFS collector ← this plan
