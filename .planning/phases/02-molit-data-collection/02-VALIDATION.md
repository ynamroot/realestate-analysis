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
| 2-01-01 | 01 | 1 | PRICE-01 | unit | `pytest tests/test_pipeline.py::test_trade_pipeline -v` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | PRICE-02 | unit | `pytest tests/test_pipeline.py::test_rent_pipeline -v` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 2 | PRICE-03 | unit | `pytest tests/test_pipeline.py::test_all_regions -v` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 2 | PRICE-04 | unit | `pytest tests/test_pipeline.py::test_normalization -v` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | BLD-01 | unit | `pytest tests/test_building.py::test_building_fetch -v` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 2 | BLD-02 | unit | `pytest tests/test_building.py::test_building_match -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline.py` — stubs for PRICE-01, PRICE-02, PRICE-03, PRICE-04
- [ ] `tests/test_building.py` — stubs for BLD-01, BLD-02
- [ ] `tests/conftest.py` — shared fixtures (mock MolitClient, in-memory SQLite DB)

*Wave 0 creates test stubs before main implementation waves.*

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
