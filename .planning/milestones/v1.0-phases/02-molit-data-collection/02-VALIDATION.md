---
phase: 2
slug: molit-data-collection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17T07:36:25Z
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | PRICE-03, PRICE-04 | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_trade_deal_amount tests/test_pipeline_phase2.py::test_normalize_trade_exclu_use_ar tests/test_pipeline_phase2.py::test_normalize_trade_deal_month_padding -v` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 0 | PRICE-04 | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_rent_deposit tests/test_pipeline_phase2.py::test_aggregate_monthly_grouping tests/test_pipeline_phase2.py::test_aggregate_monthly_stats tests/test_pipeline_phase2.py::test_month_range_bounds -v` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 0 | PRICE-01, PRICE-02 | unit | `pytest tests/test_pipeline_phase2.py::test_upsert_apartment_new tests/test_pipeline_phase2.py::test_upsert_apartment_idempotent tests/test_pipeline_phase2.py::test_insert_monthly_prices_no_dup -v` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 0 | BLDG-01, BLDG-02 | unit | `pytest tests/test_pipeline_phase2.py::test_upsert_building_info tests/test_pipeline_phase2.py::test_upsert_building_info_replace -v` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | PRICE-03, PRICE-04 | unit | `pytest tests/test_pipeline_phase2.py -k "normalize or aggregate" -v` | ✅ created W0 | ⬜ pending |
| 2-03-01 | 03 | 1 | PRICE-01, PRICE-02, BLDG-01, BLDG-02 | unit | `pytest tests/test_pipeline_phase2.py -k "upsert or insert" -v` | ✅ created W0 | ⬜ pending |
| 2-04-01 | 04 | 2 | PRICE-01, PRICE-02, PRICE-03, PRICE-04 | import | `python -c "from pipeline.collectors.trade_rent import collect_district, collect_all_regions; print('imports OK')"` | ❌ W0 | ⬜ pending |
| 2-05-01 | 05 | 2 | BLDG-01, BLDG-02 | import | `python -c "from pipeline.collectors.building_info import collect_building_info, collect_all_building_info; print('imports OK')"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Note: Plans 02-04 and 02-05 use import-check verify (collector functions require live network via MolitClient). Behavioral coverage is by proxy via normalizer/repository tests.*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_phase2.py` — 12 xfail stubs covering all Phase 2 requirements:
  - `test_normalize_trade_deal_amount`, `test_normalize_trade_exclu_use_ar`, `test_normalize_trade_deal_month_padding`
  - `test_normalize_rent_deposit`, `test_aggregate_monthly_grouping`, `test_aggregate_monthly_stats`, `test_month_range_bounds`
  - `test_upsert_apartment_new`, `test_upsert_apartment_idempotent`, `test_insert_monthly_prices_no_dup`
  - `test_upsert_building_info`, `test_upsert_building_info_replace`
- [ ] `pipeline/collectors/__init__.py` — package marker
- [ ] `pipeline/processors/__init__.py` — package marker

*Wave 0 (Plan 02-01) creates all test stubs before implementation waves.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live API response shape | PRICE-01 | Real MOLIT API call needed | Run `python -m app.pipeline.run --region 11110 --year 2024 --month 01 --dry-run` and verify JSON shape |
| HouseInfo endpoint params | BLD-01 | No DEAL_YMD param uncertainty | Call `RTMSDataSvcAptBldMgm` with a known LAWD_CD and verify response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
