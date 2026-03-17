---
phase: 02-molit-data-collection
plan: "02"
subsystem: pipeline/processors
tags: [normalization, aggregation, pure-functions, molit, price-data]
dependency_graph:
  requires: [02-01]
  provides: [02-03, 02-04, 02-05]
  affects: [pipeline/collectors/trade_rent.py]
tech_stack:
  added: []
  patterns: [pure-functions, defaultdict-groupby, datetime-month-arithmetic]
key_files:
  created:
    - pipeline/processors/normalizer.py
  modified: []
key_decisions:
  - "Normalizer functions copied verbatim from 02-RESEARCH.md patterns — no deviations needed"
  - "XPASS status is acceptable: tests marked xfail(strict=False) now unexpectedly pass, confirming correctness"
  - "Pre-existing test failures (test_fastmcp_server, test_mcp_endpoints) are out-of-scope async plugin issues unrelated to this plan"
metrics:
  duration: "90s"
  completed: "2026-03-17T23:13:55Z"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 02 Plan 02: Normalizer Implementation Summary

**One-liner:** Pure normalization/aggregation module for MOLIT trade/rent data — strips commas, zero-pads months, groups by apartment+area+period into min/max/avg price rows.

## What Was Built

`pipeline/processors/normalizer.py` — 120-line pure-function module with 6 exported symbols:

- `_safe_int(s)` / `_safe_float(s)` — null-safe type converters (private helpers)
- `get_month_range(start_ym)` — iterates YYYYMM from start to previous calendar month (avoids MOLIT 1-2 month submission lag)
- `normalize_trade_item(item)` — converts raw MOLIT XML dict to typed Python: strips commas from dealAmount, zero-pads dealMonth, floats excluUseAr
- `normalize_rent_item(item)` — same pattern for rent items; strips commas from deposit and monthlyRent
- `aggregate_monthly(items, deal_type)` — groups normalized items by `(apt_nm, umd_nm, deal_ym, exclu_use_ar)`, computes min/max/avg/count; trade rows get price_* fields, rent rows get deposit_* fields, other set is None

## Test Results

All 7 normalizer xfail stubs from Plan 01 now XPASS:

| Test | Status |
|------|--------|
| test_normalize_trade_deal_amount | XPASS |
| test_normalize_trade_exclu_use_ar | XPASS |
| test_normalize_trade_deal_month_padding | XPASS |
| test_normalize_rent_deposit | XPASS |
| test_aggregate_monthly_grouping | XPASS |
| test_aggregate_monthly_stats | XPASS |
| test_month_range_bounds | XPASS |

Full suite: 9 passed, 7 xpassed, 5 xfailed, 2 pre-existing failures (async plugin issue in unrelated test files).

## Commits

| Hash | Message |
|------|---------|
| e4288f7 | feat(02-02): implement pipeline/processors/normalizer.py |

## Deviations from Plan

None — plan executed exactly as written. Implementations copied verbatim from RESEARCH.md Patterns 1, 2, 3.

## Out-of-Scope Issues Noted

Pre-existing failures in `tests/test_fastmcp.py::test_fastmcp_server` and `tests/test_mcp.py::test_mcp_endpoints` require `pytest-asyncio` plugin. These failures existed before this plan and are not caused by normalizer changes. Deferred for separate fix.

## Self-Check: PASSED

- pipeline/processors/normalizer.py: FOUND
- Commit e4288f7: FOUND
