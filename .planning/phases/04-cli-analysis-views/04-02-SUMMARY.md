---
phase: 04-cli-analysis-views
plan: 02
subsystem: pipeline/storage
tags: [sqlite, view, schema, analysis, jeonse]
dependency_graph:
  requires: [04-01]
  provides: [apartment_analysis-VIEW, create_views-function]
  affects: [pipeline/storage/schema.py]
tech_stack:
  added: []
  patterns: [DROP-VIEW-IF-EXISTS + CREATE-VIEW, pre-aggregated LEFT JOIN subquery, NULL-safe CASE WHEN]
key_files:
  created: []
  modified:
    - pipeline/storage/schema.py
decisions:
  - "create_views() appended after migrate_db() and called from init_db() so VIEW is always up-to-date on every DB open"
  - "DROP VIEW IF EXISTS + CREATE VIEW (not IF NOT EXISTS) used to guarantee definition stays current across schema.py edits"
  - "monthly_prices pre-aggregated via GROUP BY (apartment_id, deal_ym) in subquery before JOIN to prevent one-row-per-size-band duplicates"
  - "jeonse_ratio_pct uses CASE WHEN for NULL-safety when trade price is NULL or zero"
metrics:
  duration: "1m 24s"
  completed: "2026-03-18T05:58:13Z"
  tasks_completed: 1
  files_modified: 1
---

# Phase 04 Plan 02: Add apartment_analysis SQLite VIEW Summary

**One-liner:** apartment_analysis VIEW with pre-aggregated trade/rent subqueries and NULL-safe jeonse_ratio_pct, wired into init_db() via create_views().

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add create_views() to schema.py and call from init_db() | bf94075 | pipeline/storage/schema.py |

## What Was Built

Added `create_views(conn: sqlite3.Connection) -> None` to `pipeline/storage/schema.py`. The function:

1. Drops and recreates the `apartment_analysis` SQLite VIEW on every call
2. Pre-aggregates `monthly_prices` rows using `GROUP BY (apartment_id, deal_ym)` in LEFT JOIN subqueries to prevent one row per size band
3. Selects the latest trade and rent month per apartment using `MAX(deal_ym)` correlated subquery
4. Computes `jeonse_ratio_pct` as `ROUND(deposit_avg / trade_price_avg * 100, 1)` with a `CASE WHEN` guard for NULL and zero trade price
5. Left-joins `commute_stops` for business district accessibility columns

`init_db()` now calls `create_views(conn)` before returning, so the VIEW is always present on every fresh DB open.

## Verification

All 4 CLI-04 VIEW tests pass:
- `test_create_views` — VIEW exists in sqlite_master after create_views()
- `test_apartment_analysis_empty` — returns [] on empty DB, no error
- `test_jeonse_ratio_calculation` — 70000/100000*100 = 70.0 (±0.5)
- `test_view_no_duplicates` — 2 size bands (59.0, 84.0) → exactly 1 VIEW row

Full phase 4 suite: 15/15 passed. Full pipeline test suite: 24/24 passed (2 pre-existing async test failures in unrelated test_fastmcp.py and test_mcp.py remain unchanged).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `pipeline/storage/schema.py` exists and contains `def create_views`
- `bf94075` commit exists in git log
- VIEW confirmed present via `init_db(':memory:')` verification command
