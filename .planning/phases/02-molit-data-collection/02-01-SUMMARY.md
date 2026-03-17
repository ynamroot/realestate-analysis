---
phase: 02-molit-data-collection
plan: 01
subsystem: pipeline/testing
tags: [test-scaffold, xfail, wave-0, tdd, normalizer, repository]
dependency_graph:
  requires: [01-04-PLAN.md]
  provides: [tests/test_pipeline_phase2.py, pipeline/collectors/__init__.py, pipeline/processors/__init__.py]
  affects: [02-02-PLAN.md, 02-03-PLAN.md]
tech_stack:
  added: []
  patterns: [pytest xfail stubs, package markers]
key_files:
  created:
    - tests/test_pipeline_phase2.py
    - pipeline/collectors/__init__.py
    - pipeline/processors/__init__.py
  modified:
    - pyproject.toml
decisions:
  - "Module-level import of pipeline.storage.schema.init_db in test file is safe because schema.py already exists from Phase 1 — only Wave-1 modules are guarded by xfail"
  - "pythonpath=['.'] added to pyproject.toml so bare pytest command resolves pipeline/ package (pre-existing missing config — Rule 3 auto-fix)"
metrics:
  duration: "2 minutes"
  completed: "2026-03-17T23:10:41Z"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 2 Plan 01: Wave 0 Test Scaffold Summary

**One-liner:** 12 xfail pytest stubs covering PRICE-01/02/03/04 and BLDG-01/02 contracts, plus collectors/processors package markers, so Wave 1 implementation can turn stubs green.

## What Was Built

- `pipeline/collectors/__init__.py` — package marker for per-district fetching loops (Wave 1)
- `pipeline/processors/__init__.py` — package marker for normalization and aggregation (Wave 1)
- `tests/test_pipeline_phase2.py` — 12 xfail test stubs against the exact function signatures defined in RESEARCH.md

## Test Coverage (12 stubs)

| Test | Requirement | Target function |
|------|-------------|-----------------|
| test_normalize_trade_deal_amount | PRICE-04 | normalize_trade_item |
| test_normalize_trade_exclu_use_ar | PRICE-04 | normalize_trade_item |
| test_normalize_trade_deal_month_padding | PRICE-04 | normalize_trade_item |
| test_normalize_rent_deposit | PRICE-04 | normalize_rent_item |
| test_aggregate_monthly_grouping | PRICE-03 | aggregate_monthly |
| test_aggregate_monthly_stats | PRICE-03 | aggregate_monthly |
| test_month_range_bounds | PRICE-01/02 | get_month_range |
| test_upsert_apartment_new | PRICE-01 | upsert_apartment |
| test_upsert_apartment_idempotent | PRICE-01 | upsert_apartment |
| test_insert_monthly_prices_no_dup | PRICE-01 | insert_monthly_prices |
| test_upsert_building_info | BLDG-01 | upsert_building_info |
| test_upsert_building_info_replace | BLDG-02 | upsert_building_info |

## Verification Results

```
pytest tests/test_pipeline_phase2.py -q  → 12 xfailed in 0.21s  (exit 0)
pytest tests/ -q                         → 9 passed, 12 xfailed, 2 pre-existing fails
python -c "import pipeline.collectors; import pipeline.processors" → OK
grep -c "def test_" tests/test_pipeline_phase2.py → 12
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing pythonpath in pytest config**
- **Found during:** Task 2 verification
- **Issue:** `pytest tests/test_pipeline_phase2.py` exited with collection error — `ModuleNotFoundError: No module named 'pipeline'` — because pytest's working directory wasn't on sys.path. The same issue affected foundation tests with bare `pytest`.
- **Fix:** Added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml`. Foundation tests also now pass with bare `pytest` (previously required `python -m pytest`).
- **Files modified:** `pyproject.toml`
- **Commit:** 5d08a03

## Commits

| Hash | Message |
|------|---------|
| 2910627 | feat(02-01): add collectors and processors package __init__.py markers |
| 5d08a03 | feat(02-01): add 12 xfail test stubs for Phase 2 normalizer and repository |

## Self-Check: PASSED

All created files exist on disk and all commit hashes verified in git log.
