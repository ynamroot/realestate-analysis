---
phase: 02-molit-data-collection
plan: 03
subsystem: pipeline/storage
tags: [sqlite, repository, upsert, deduplication, phase2]
dependency_graph:
  requires: [02-01]
  provides: [pipeline/storage/repository.py]
  affects: [02-04, 02-05]
tech_stack:
  added: []
  patterns: [INSERT OR IGNORE + SELECT for stable id, application-level dedup before INSERT, INSERT OR REPLACE on UNIQUE FK]
key_files:
  created:
    - pipeline/storage/repository.py
  modified: []
decisions:
  - "upsert_apartment does not commit — caller owns the transaction boundary for batch efficiency"
  - "insert_monthly_prices commits after all rows in the batch to match RESEARCH anti-pattern avoidance"
  - "upsert_building_info propagates authoritative build_year to apartments table (UPDATE apartments SET build_year WHERE id)"
  - "INSERT OR REPLACE on UNIQUE(apartment_id) is the correct building_info upsert pattern"
metrics:
  duration: "2m"
  completed: 2026-03-17T23:16:20Z
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_covered: [PRICE-01, PRICE-02, BLDG-01, BLDG-02]
---

# Phase 2 Plan 3: Storage Repository Summary

**One-liner:** SQLite persistence layer with INSERT OR IGNORE apartment upsert, application-level monthly_prices deduplication, and INSERT OR REPLACE building_info upsert with authoritative build_year propagation.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Implement pipeline/storage/repository.py | eff29e0 | pipeline/storage/repository.py (created) |

## Verification Results

```
pytest tests/test_pipeline_phase2.py::test_upsert_apartment_new
       tests/test_pipeline_phase2.py::test_upsert_apartment_idempotent
       tests/test_pipeline_phase2.py::test_insert_monthly_prices_no_dup
       tests/test_pipeline_phase2.py::test_upsert_building_info
       tests/test_pipeline_phase2.py::test_upsert_building_info_replace -v

5 xpassed in 0.05s
```

All 5 repository tests changed from XFAIL to XPASS.

Full suite: 12 xpassed, 9 passed, 2 pre-existing failures in unrelated async tests (test_fastmcp.py, test_mcp.py — missing pytest-asyncio setup, out of scope).

## Decisions Made

1. **No commit in upsert_apartment** — caller owns the transaction boundary; committing per apartment inside a batch loop would cause ~10,000x WAL checkpoint overhead per RESEARCH pitfall 5.
2. **Commit in insert_monthly_prices** — the function is called per-apartment-per-batch; committing at batch end is the correct granularity.
3. **build_year propagation** — `upsert_building_info` also runs `UPDATE apartments SET build_year WHERE id` when HouseInfo provides a non-None `build_year`, per RESEARCH anti-pattern avoidance. HouseInfo is the authoritative source.
4. **No additional columns in INSERT OR IGNORE** — upsert_apartment only populates `jibun`, `road_nm`, `build_year` from kwargs; the remaining columns (`total_households`, `floor_area_ratio`, etc.) are populated by Phase 3 building_info collector.

## Deviations from Plan

None — plan executed exactly as written. Repository functions copied verbatim from RESEARCH.md patterns with the additional `build_year` propagation step specified in the task action block.

## Self-Check: PASSED

- `pipeline/storage/repository.py` exists: FOUND
- Commit `eff29e0` exists: FOUND
- 3 function signatures verified via grep: FOUND
- 5 tests XPASS: VERIFIED
