---
phase: 3
slug: geospatial-subway-graph
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18T02:08:51Z
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml (Wave 0 installs) |
| **Quick run command** | `pytest tests/phase03/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/phase03/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-XX-01 | TBD | 0 | SUBW-01 | unit stub | `pytest tests/phase03/test_subway.py -q` | ❌ W0 | ⬜ pending |
| 03-XX-02 | TBD | 0 | COMM-01 | unit stub | `pytest tests/phase03/test_commute.py -q` | ❌ W0 | ⬜ pending |
| 03-XX-03 | TBD | 1 | SUBW-01,02 | unit | `pytest tests/phase03/test_subway.py -q` | ✅ | ⬜ pending |
| 03-XX-04 | TBD | 1 | SUBW-03 | unit | `pytest tests/phase03/test_cache.py -q` | ✅ | ⬜ pending |
| 03-XX-05 | TBD | 2 | COMM-01 | unit | `pytest tests/phase03/test_graph.py -q` | ✅ | ⬜ pending |
| 03-XX-06 | TBD | 2 | COMM-02,03,04,05 | unit | `pytest tests/phase03/test_commute.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/phase03/test_subway.py` — stubs for SUBW-01, SUBW-02, SUBW-03
- [ ] `tests/phase03/test_commute.py` — stubs for COMM-01 through COMM-05
- [ ] `tests/phase03/conftest.py` — shared fixtures (mock TMAP response, mock stations data)
- [ ] `tests/phase03/__init__.py` — package marker

*Existing pytest infrastructure from Phase 1-2 covers the framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TMAP API returns correct walking distance for real address | SUBW-01 | Requires live TMAP API key and real apartment coordinates | Run `pipeline collect-distances --apartment-id 1` and verify distance in meters matches Maps UI |
| Naver/TMAP rate limit not exceeded during full collection | SUBW-03 | Rate limits only manifest during bulk runs | Run full collection on 1 region, check logs for 429 errors |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
