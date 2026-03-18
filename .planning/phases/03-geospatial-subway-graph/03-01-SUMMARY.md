---
phase: 03-geospatial-subway-graph
plan: "01"
subsystem: pipeline/graph
tags: [tdd, scaffold, schema-migration, subway-graph, stubs]
dependency_graph:
  requires: []
  provides:
    - pipeline/graph package (importable)
    - pipeline/graph/station_loader.py stubs
    - pipeline/collectors/subway_distances.py stubs
    - pipeline/collectors/commute_stops.py stubs
    - pipeline/storage/schema.py latitude/longitude columns + migrate_db()
    - tests/test_pipeline_phase3.py (10 xfail test stubs)
  affects:
    - pipeline/storage/schema.py
    - requirements.txt
tech_stack:
  added:
    - networkx>=3.0 (subway graph BFS)
  patterns:
    - xfail-stub TDD pattern (same as Phase 2)
    - ALTER TABLE migration function (migrate_db) for additive schema changes
    - Empty __init__.py package marker for pipeline/graph/
key_files:
  created:
    - pipeline/graph/__init__.py
    - pipeline/graph/station_loader.py
    - pipeline/collectors/subway_distances.py
    - pipeline/collectors/commute_stops.py
    - tests/test_pipeline_phase3.py
  modified:
    - pipeline/storage/schema.py
    - requirements.txt
decisions:
  - "build_subway_graph_from_df() stub added alongside build_subway_graph() because tests use DataFrame input pattern — aligns with Wave 1 implementation contract"
  - "networkx added to requirements.txt immediately to avoid import errors in stub modules"
  - "migrate_db() uses ALTER TABLE with silent exception handling — safe for repeated calls on already-migrated DBs"
metrics:
  duration: "2m 13s"
  completed: "2026-03-18T02:59:07Z"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
---

# Phase 3 Plan 01: Wave 0 TDD Scaffold — Test Stubs + Module Stubs Summary

Phase 3 Wave 0 scaffold: 10 xfail test stubs covering SUBW/COMM requirements, pipeline/graph/ package with NotImplementedError stubs, and apartments schema migration adding latitude/longitude columns with migrate_db().

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Schema migration + graph package markers + module stubs | 483a36b | pipeline/storage/schema.py, pipeline/graph/__init__.py, pipeline/graph/station_loader.py, pipeline/collectors/subway_distances.py, pipeline/collectors/commute_stops.py, requirements.txt |
| 2 | Test scaffold — 10 xfail stubs for Phase 3 requirements | a765cca | tests/test_pipeline_phase3.py |

## Verification Results

```
python -c "from pipeline.graph.station_loader import build_subway_graph, haversine_m, min_stops; from pipeline.storage.schema import migrate_db; print('OK')"
# OK

pytest tests/test_pipeline_phase3.py -q
# xxXXxxxxXx [100%]
# 7 xfailed, 3 xpassed in 1.24s

grep -n "latitude REAL" pipeline/storage/schema.py
# 37: latitude REAL,

grep -n "def migrate_db" pipeline/storage/schema.py
# 123: def migrate_db(conn: sqlite3.Connection) -> None:
```

## Decisions Made

1. **build_subway_graph_from_df() added to stub**: Tests reference `build_subway_graph_from_df(df)` with DataFrame input. Added this function alongside `build_subway_graph(xlsx_path)` to match the test contract for Wave 1 implementation.

2. **networkx installed immediately**: The stub modules import networkx at module level. Installing it upfront (and adding to requirements.txt) avoids ImportError for all downstream users.

3. **migrate_db() silent exception pattern**: Uses `try/except Exception: pass` to silently handle "column already exists" errors from repeated ALTER TABLE calls — idiomatic for SQLite migration helpers.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- pipeline/graph/__init__.py: FOUND
- pipeline/graph/station_loader.py: FOUND
- pipeline/collectors/subway_distances.py: FOUND
- pipeline/collectors/commute_stops.py: FOUND
- tests/test_pipeline_phase3.py: FOUND
- Commit 483a36b: FOUND
- Commit a765cca: FOUND
- pytest exits 0: CONFIRMED (7 xfailed, 3 xpassed)
