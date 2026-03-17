---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17T06:25:15Z
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` with `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_pipeline_foundation.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline_foundation.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | FOUND-01 | unit | `pytest tests/test_pipeline_foundation.py::test_init_db_creates_tables -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | FOUND-01 | unit | `pytest tests/test_pipeline_foundation.py::test_table_names -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | FOUND-02 | unit | `pytest tests/test_pipeline_foundation.py::test_molit_url_encoding -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | FOUND-02 | unit | `pytest tests/test_pipeline_foundation.py::test_result_code_detection -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | FOUND-02 | unit | `pytest tests/test_pipeline_foundation.py::test_pagination_stops -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | FOUND-03 | unit | `pytest tests/test_pipeline_foundation.py::test_lawd_cd_format -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | FOUND-03 | unit | `pytest tests/test_pipeline_foundation.py::test_required_regions_present -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 1 | FOUND-04 | unit | `pytest tests/test_pipeline_foundation.py::test_idempotency_check -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 1 | FOUND-04 | unit | `pytest tests/test_pipeline_foundation.py::test_idempotency_no_duplicate -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_foundation.py` — stubs for FOUND-01 through FOUND-04 (all 9 test cases above)
- [ ] `tests/conftest.py` — shared `tmp_db` fixture returning an in-memory or temp-file sqlite3 connection

*No framework install gap — pytest already configured in pyproject.toml*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MOLIT API returns HTTP 200 without 401 using real serviceKey | FOUND-02 | Requires live API key and network | Set `MOLIT_API_KEY` in `.env`, run `python -c "import asyncio; from pipeline.clients.molit import MolitClient; import httpx; c=MolitClient(os.getenv('MOLIT_API_KEY')); asyncio.run(c.fetch_all(httpx.AsyncClient(), '11680', '202401'))"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
