---
phase: 02-molit-data-collection
plan: 05
subsystem: pipeline/collectors
tags: [building-info, molit, houseinfo, idempotency, name-normalization]
dependency_graph:
  requires: [02-03]
  provides: [collect_building_info, collect_all_building_info]
  affects: [building_info table, apartments.build_year]
tech_stack:
  added: []
  patterns:
    - HouseInfo URL constructed with serviceKey embedded (not params={})
    - Idempotency sentinel deal_ym='000000' data_type='building'
    - buldNm normalized before matching against apartments.apt_nm (exact + prefix fallback)
key_files:
  created:
    - pipeline/collectors/building_info.py
  modified: []
decisions:
  - "HouseInfo endpoint URL embeds serviceKey directly (same pattern as MolitClient) to avoid httpx double-encoding"
  - "Idempotency uses deal_ym='000000' sentinel — consistent with Plan 03 decision documented in STATE.md"
  - "Name matching: exact normalized match first, then prefix fallback; unmatched complexes are inserted as new apartments"
  - "collect_all_building_info is synchronous entry point using asyncio.run() — not for use inside async context"
metrics:
  duration: 59s
  completed: 2026-03-17T23:22:12Z
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 02 Plan 05: HouseInfo Building Info Collector Summary

**One-liner:** HouseInfo RTMSDataSvcAptBldMgm collector with buldNm normalization, idempotency sentinel (000000/building), and upsert into building_info linked by apartment_id FK.

## What Was Built

`pipeline/collectors/building_info.py` implementing the MOLIT HouseInfo API collection loop for building metadata.

### Functions Exported

- **`collect_building_info(conn, client, molit, lawd_cd) -> int`** (async): Fetches all building metadata for a single district. Checks idempotency sentinel before making any HTTP calls. Paginates until `len(items) < page_size`. Matches API `buldNm` to existing `apartments.apt_nm` via normalized name lookup (exact then prefix fallback). Calls `upsert_building_info` for each item. Marks collected on completion.

- **`collect_all_building_info(conn, molit) -> dict`** (sync): Iterates over all 29 `PIPELINE_REGIONS`, calls `collect_building_info` for each. Returns `{"total": N, "regions": 29}` summary.

### Key Design Details

1. **URL construction**: `f"{HOUSEINFO_ENDPOINT}?serviceKey={molit.safe_key}&LAWD_CD={lawd_cd}&numOfRows={page_size}&pageNo={page}"` — no DEAL_YMD parameter (HouseInfo returns all complexes for district regardless of date).

2. **Idempotency**: `is_collected(conn, lawd_cd, "000000", "building")` / `mark_collected(conn, lawd_cd, "000000", "building", record_count=inserted)` — reuses existing idempotency infrastructure with a special sentinel deal_ym.

3. **Name normalization**: `_normalize_apt_name` strips `["아파트", "APT", "apt"]` suffixes, removes spaces, lowercases. Exact match tried first; prefix match fallback for complexes like "은마1단지" when API returns "은마".

4. **No-match handling**: When buldNm doesn't match any existing apartment, the complex is inserted via `upsert_apartment` before `upsert_building_info` — ensures no orphaned building_info rows.

## Verification Results

All plan verification checks passed:
- `from pipeline.collectors.building_info import collect_building_info, collect_all_building_info` — imports OK
- Both `def collect_building_info` and `def collect_all_building_info` present
- `HOUSEINFO_ENDPOINT` contains `getRTMSDataSvcAptBldMgm`
- `"000000"` sentinel confirmed in `is_collected` and `mark_collected` calls
- `_normalize_apt_name` used in both index building and item matching
- `pytest tests/ -q` — 9 passed, 12 xpassed, 2 pre-existing failures (async test framework, unrelated)

## Deviations from Plan

None — plan executed exactly as written. The `_safe_int` and `_safe_float` helpers were defined before `collect_building_info` in the file (moved up for forward-reference clarity), which is a minor ordering choice consistent with the plan's intent.

## Self-Check

- [x] `pipeline/collectors/building_info.py` exists and is 172 lines (above 80 min_lines)
- [x] Commit `beaae82` exists
- [x] Both exported functions present
- [x] All key_links confirmed: imports from repository, idempotency, and molit.safe_key usage all present

## Self-Check: PASSED
