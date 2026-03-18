---
phase: 5
slug: subway-pipeline-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18T07:37:07Z
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_pipeline_phase5.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline_phase5.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | SUBW-01, SUBW-02, SUBW-03, COMM-05 | stub | `pytest tests/test_pipeline_phase5.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | SUBW-02 | migration | `pytest tests/test_pipeline_phase5.py::test_unique_constraint_migration -x -q` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | SUBW-01 | integration | `pytest tests/test_pipeline_phase5.py::test_geocode_cli_dispatch -x -q` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | SUBW-03 | integration | `pytest tests/test_pipeline_phase5.py::test_multiline_station_storage -x -q` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | COMM-05 | integration | `pytest tests/test_pipeline_phase5.py::test_commute_stops_bfs -x -q` | ❌ W0 | ⬜ pending |
| 05-01-06 | 01 | 2 | SUBW-01,02,03,COMM-05 | process | manual | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_phase5.py` — stubs for SUBW-01, SUBW-02, SUBW-03, COMM-05
- [ ] Existing `tests/conftest.py` — shared fixtures (already exists from Phase 3)

*Framework pytest already installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Phase 3 VERIFICATION.md written with status: passed | COMM-05 (process gate) | File creation with specific content is process, not unit logic | Run `cat .planning/phases/03-*/03-VERIFICATION.md` and verify `status: passed` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
