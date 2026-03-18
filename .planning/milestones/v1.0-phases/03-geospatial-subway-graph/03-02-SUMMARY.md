---
phase: 03-geospatial-subway-graph
plan: 02
subsystem: pipeline/clients, pipeline/graph
tags: [tmap, subway-graph, haversine, bfs, networkx, wave1]
dependency_graph:
  requires: [03-01]
  provides: [pipeline/clients/tmap.py, pipeline/graph/station_loader.py]
  affects: [03-03, 03-04, 03-05]
tech_stack:
  added: [networkx, httpx-async-client-pattern]
  patterns: [pure-function-parser, compound-key-nodes, transfer-weight-zero]
key_files:
  created:
    - pipeline/clients/tmap.py
  modified:
    - pipeline/graph/station_loader.py
decisions:
  - "tmap_walk_distance_from_response iterates features to find SP pointType — not features[0] directly"
  - "Compound node key '{station_name}_{line_name}' prevents transfer-aware BFS collapse"
  - "Transfer edges use weight=0 (Korean transit counts stops ridden, not transfers)"
  - "min_stops uses nx.shortest_path_length with Dijkstra — handles mixed weight=0/1 graph correctly"
metrics:
  duration: "1m 56s"
  completed: "2026-03-18T03:02:51Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 3 Plan 2: TMAP Client + Subway Graph Builder Summary

**One-liner:** TMAP pedestrian API async client with SP-feature parser, and subway graph builder with haversine distance, compound-key nodes, weight-0 transfer edges, and BFS min_stops via NetworkX.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | TMAP Pedestrian API client | 1cc24da | pipeline/clients/tmap.py (created) |
| 2 | Subway graph builder + haversine + BFS min_stops | 3335b5b | pipeline/graph/station_loader.py (replaced stubs) |

## Test Results

All 7 target tests pass (XPASS — were previously xfail):
- `test_tmap_walk_distance_parse` — XPASS
- `test_tmap_walk_distance_empty` — XPASS
- `test_build_subway_graph` — XPASS
- `test_subway_graph_transfer_edges` — XPASS
- `test_min_stops_bfs` — XPASS
- `test_min_stops_no_path` — XPASS
- `test_haversine_m` — XPASS

Remaining 3 tests (SUBW-02, SUBW-03, COMM-05) still xfail — expected Wave 3 collector work.

Full suite: `pytest tests/test_pipeline_phase3.py -q` → 10 xpassed (all pass).

## Decisions Made

1. **SP-feature iteration over features[0]**: `tmap_walk_distance_from_response` iterates all features looking for `pointType == "SP"` rather than blindly using `features[0]`. The API can return geometry features before the SP summary feature.

2. **Compound node key prevents BFS collapse**: Using `"{station_name}_{line_name}"` as graph node key ensures 강남 on Line 2 and 강남 on Bundang Line are distinct nodes. This is required for transfer-aware path finding.

3. **Transfer edges weight=0**: Korean transit pricing counts stations ridden, not transfers made. A transfer at the same physical station costs 0 stops toward the commute distance.

4. **nx.shortest_path_length for BFS**: NetworkX handles mixed-weight graphs correctly — weight=0 transfer edges don't inflate hop counts.

5. **build_subway_graph_from_df as testable pure function**: Separating the DataFrame processing function from the XLSX-loading wrapper enables unit testing without requiring the actual data file on disk.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `pipeline/clients/tmap.py` exists and contains `tmap_walk_distance_from_response`, `TmapClient`, `TMAP_PEDESTRIAN_URL`, `"startX": from_lon`
- [x] `pipeline/graph/station_loader.py` exists and contains `haversine_m`, `build_subway_graph_from_df`, `build_subway_graph`, `min_stops`, `GBD_STATIONS`, `weight=0`
- [x] Commits 1cc24da and 3335b5b exist in git log
- [x] 7 target tests XPASS, 3 remaining xfail as expected
- [x] Import verification: `python -c "from pipeline.clients.tmap import ...; from pipeline.graph.station_loader import ...; print('OK')"` exits 0
