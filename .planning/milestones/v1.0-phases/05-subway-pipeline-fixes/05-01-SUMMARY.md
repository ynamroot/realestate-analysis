---
phase: 05-subway-pipeline-fixes
plan: "01"
subsystem: subway-pipeline-gap-closure
status: complete
completed_at: 2026-03-18T07:56:37Z
tags: [schema-migration, sqlite, unique-constraint, cli-dispatch, geocoding, subway, verification]
dependency_graph:
  requires: [03-04, 04-03]
  provides: [migrate_db-3col-unique, cli-geocode-dispatch, 03-VERIFICATION.md]
  affects: [pipeline/storage/schema.py, pipeline/cli/main.py]
tech_stack:
  added: []
  patterns: [sqlite-table-recreate-migration, cli-prerequisite-dispatch, xfail-scaffold]
key_files:
  created:
    - tests/test_pipeline_phase5.py
    - .planning/phases/03-geospatial-subway-graph/03-VERIFICATION.md
  modified:
    - pipeline/storage/schema.py
    - pipeline/cli/main.py
decisions:
  - "_needs_subway_unique_migration() checks for 'station_name, line_name' in DDL — not just 'line_name' (which appears as a column name too)"
  - "3-step table-recreate migration uses conn.executescript() with explicit BEGIN/COMMIT inside script — no conn.commit() after"
  - "geocode dispatch block inserted BEFORE subway dispatch block in collect() — source order guarantees execution order"
  - "geocode prerequisite warning printed to stderr when KAKAO_REST_API_KEY missing during subway/all collect"
  - "test_fastmcp.py and test_mcp.py pre-existing async failures excluded from regression check — confirmed pre-existing before Phase 5 changes"
metrics:
  duration: "316s (~5m)"
  completed_date: "2026-03-18"
  tasks_completed: 3
  files_modified: 4
requirements:
  - SUBW-01
  - SUBW-02
  - SUBW-03
  - COMM-05
---

# Phase 5 Plan 01: Subway Pipeline Gap Closure Summary

## One-liner

3-column UNIQUE migration for subway_distances + geocode dispatch wired before subway step in CLI + Phase 3 formal verification record.

## What Was Built

### Task 1: Phase 5 test scaffold (4 xfail tests)

Created `tests/test_pipeline_phase5.py` with 4 xfail tests covering all three gap-closure targets:
- `test_migrate_subway_unique` — verifies 3-column UNIQUE in DDL after init_db
- `test_subway_distances_multiline` — verifies 강남역 2호선 + 분당선 store as 2 separate rows
- `test_collect_geocode_dispatch` — verifies `collect --data-type geocode` dispatches to geocode_all_apartments
- `test_collect_subway_runs_geocode_first` — verifies geocode runs before subway in call order

### Task 2: Schema migration + CLI geocode dispatch

**pipeline/storage/schema.py:**
- Added `_needs_subway_unique_migration()` helper: checks DDL for `station_name, line_name` pattern in the UNIQUE constraint (not just column name presence)
- Extended `migrate_db()` with 3-step table-recreate: CREATE `subway_distances_new` with 3-column UNIQUE, INSERT OR IGNORE data from old table, DROP old, ALTER RENAME new

**pipeline/cli/main.py:**
- Added geocode dispatch block: `if data_type in ("geocode", "subway", "all")` before the existing subway block
- Imports and calls `geocode_all_apartments(conn)` from `pipeline.collectors.geocode`
- Warning printed when KAKAO_REST_API_KEY not set and data_type is subway/all (explains 0-row silent failure mode)
- Updated `data_type` option help text to include `geocode`

### Task 3: Phase 3 VERIFICATION.md

Created `.planning/phases/03-geospatial-subway-graph/03-VERIFICATION.md`:
- 8/8 requirements SATISFIED: SUBW-01, SUBW-02, SUBW-03, COMM-01, COMM-02, COMM-03, COMM-04, COMM-05
- Evidence table with 10 xpassed tests from 03-01 through 03-04 SUMMARY files
- Note on SUBW-02: schema UNIQUE was 2-column during Phase 3 (fixed here in Phase 5)

## Test Results

```
pytest tests/test_pipeline_phase5.py -v
4 xpassed in 1.12s
```

All 4 Phase 5 tests: 4 xpassed (0 failures, 0 xfailed).

Full pipeline suite (excluding pre-existing async failures in test_fastmcp.py / test_mcp.py):
```
pytest tests/ --ignore=tests/test_fastmcp.py --ignore=tests/test_mcp.py -q
24 passed, 26 xpassed in 1.37s
```

No regressions in Phase 1–4 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _needs_subway_unique_migration() false negative**
- **Found during:** Task 2 verification (2 of 4 tests still xfailed after initial implementation)
- **Issue:** The helper checked `"line_name" not in ddl` but `line_name` appears as a column name in the DDL even when the UNIQUE constraint is still 2-column. The check returned `False` (no migration needed) incorrectly.
- **Fix:** Changed check to `"station_name, line_name" not in ddl` — this pattern only appears inside `UNIQUE(apartment_id, station_name, line_name)`, not as a column definition.
- **Files modified:** `pipeline/storage/schema.py`
- **Commit:** included in 0ea1c9e

## Self-Check: PASSED
