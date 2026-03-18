---
phase: 02-molit-data-collection
plan: 04
subsystem: database
tags: [molit, sqlite, httpx, asyncio, idempotency, pipeline]

# Dependency graph
requires:
  - phase: 02-molit-data-collection/02-01
    provides: "MolitClient.fetch_all, is_collected, mark_collected, PIPELINE_REGIONS"
  - phase: 02-molit-data-collection/02-02
    provides: "normalize_trade_item, normalize_rent_item, aggregate_monthly, get_month_range"
  - phase: 02-molit-data-collection/02-03
    provides: "upsert_apartment, insert_monthly_prices"
provides:
  - "District-level collection loop: collect_district (async, idempotent per month/district/deal_type)"
  - "Full-region entry point: collect_all_regions (sync, 29 regions × 2 deal_types)"
  - "pipeline/collectors/trade_rent.py with complete orchestration logic"
affects: [phase-03-transit, phase-04-building, any CLI or script that triggers data collection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.run() wraps async collection inside sync entry point — safe for CLI, not for running async contexts"
    - "Idempotency check (is_collected) before any API call to avoid redundant fetches"
    - "mark_collected called after all rows for a (lawd_cd, deal_ym) are inserted — never before"
    - "jibun/road_nm passed as None to upsert_apartment from aggregated rows; trade normalizer returns those from raw items but aggregate_monthly groups do not carry them through"

key-files:
  created:
    - pipeline/collectors/trade_rent.py
  modified: []

key-decisions:
  - "jibun and road_nm passed as None to upsert_apartment from aggregated data — informational fields not needed for correctness; avoids key lookup into raw item groups"
  - "Pre-existing test failures in test_fastmcp.py and test_mcp.py (missing pytest-asyncio) confirmed as out-of-scope — not caused by this plan"

patterns-established:
  - "collect_district: async, per-district, per-deal_type loop with per-month idempotency skip"
  - "collect_all_regions: sync entry point using asyncio.run(), iterates PIPELINE_REGIONS × deal_types"

requirements-completed: [PRICE-01, PRICE-02, PRICE-03, PRICE-04]

# Metrics
duration: 3min
completed: 2026-03-17
---

# Phase 2 Plan 4: Trade/Rent Collection Loop Summary

**Async district collection loop (collect_district) with per-month idempotency, wiring MolitClient + normalizer + repository into a full 29-region × 2-deal-type orchestration (collect_all_regions)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-17T23:17:06Z
- **Completed:** 2026-03-17T23:19:03Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `pipeline/collectors/trade_rent.py` connecting all Phase 1 and Phase 2 foundations
- `collect_district` skips already-collected months via `is_collected`, fetches and normalizes, aggregates, upserts apartments, inserts prices, then calls `mark_collected`
- `collect_all_regions` provides a sync CLI entry point over all 29 PIPELINE_REGIONS × both deal_types
- All pipeline tests pass (9 passed, 12 xpassed); 2 pre-existing unrelated test failures confirmed out-of-scope

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement pipeline/collectors/trade_rent.py** - `39137e0` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `pipeline/collectors/trade_rent.py` — Core collection orchestration: collect_district + collect_all_regions

## Decisions Made
- `jibun` and `road_nm` passed as `None` to `upsert_apartment` from aggregated rows — `aggregate_monthly` groups items and drops per-item fields like jibun; these are informational only and the apartment can be re-enriched from trade data or building info later
- Pre-existing failures in `test_fastmcp.py` and `test_mcp.py` confirmed as out-of-scope (missing `pytest-asyncio` plugin, unrelated to pipeline)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] loguru not installed in environment**
- **Found during:** Task 1 (import verification)
- **Issue:** `from loguru import logger` raised `ModuleNotFoundError` — loguru was used by molit.py and the plan but not present in the active environment
- **Fix:** Ran `pip install loguru -q`
- **Files modified:** None (environment only)
- **Verification:** Import succeeded after install
- **Committed in:** 39137e0 (implicit — environment fix, no file change)

---

**Total deviations:** 1 auto-fixed (1 blocking — missing dependency)
**Impact on plan:** Minimal. loguru was already a declared dependency used by prior modules. No scope creep.

## Issues Encountered
- None beyond the blocking loguru install

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `pipeline/collectors/trade_rent.py` is complete and ready for use
- `collect_all_regions(conn, molit)` is the primary entry point for triggering full data collection
- Phase 2 Wave 2 complete — ready for Wave 3 (building info collection, plan 05)

---
*Phase: 02-molit-data-collection*
*Completed: 2026-03-17*
