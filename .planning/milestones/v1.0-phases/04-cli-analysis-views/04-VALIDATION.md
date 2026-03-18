---
phase: 4
slug: cli-analysis-views
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18T05:38:10Z
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_cli.py -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_cli.py -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | CLI-01 | unit | `pytest tests/test_cli.py::test_collect_command -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | CLI-02 | unit | `pytest tests/test_cli.py::test_export_command -x -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | CLI-03 | unit | `pytest tests/test_cli.py::test_status_command -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | CLI-04 | integration | `pytest tests/test_views.py::test_apartment_analysis_view -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cli.py` — stubs for CLI-01, CLI-02, CLI-03 (collect, export, status commands)
- [ ] `tests/test_views.py` — stubs for CLI-04 (apartment_analysis VIEW)
- [ ] `tests/conftest.py` — shared fixtures (in-memory SQLite DB, sample data)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Excel opens CSV without Korean garbling | CLI-02 | Requires Windows Excel to open file | Run `pipeline export --output test.csv`, open in Excel, verify Korean characters display correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
