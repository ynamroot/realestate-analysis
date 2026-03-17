---
phase: 01-foundation
plan: 04
subsystem: pipeline/clients
tags: [molit, api-client, xml-parsing, pagination, url-encoding]
dependency_graph:
  requires: [01-02]
  provides: [pipeline.clients.molit]
  affects: [Phase 2 data collection]
tech_stack:
  added: []
  patterns: [xml.etree.ElementTree, urllib.parse.quote/unquote, httpx.AsyncClient]
key_files:
  created:
    - pipeline/clients/molit.py
  modified: []
decisions:
  - "serviceKey embedded directly in URL string — never via params={} to avoid httpx double-encoding"
  - "HTTP 200 does not mean success — always call _check_result_code() before parsing items"
  - "_check_result_code accepts resultCode 00, 0000, 000 as success; all other values are errors"
  - "Pagination stops when len(items) < page_size — handles both last page and empty response"
metrics:
  duration: "2 minutes"
  completed: 2026-03-17T06:56:00Z
  tasks_completed: 1
  files_created: 1
---

# Phase 1 Plan 04: MOLIT API Client Summary

**One-liner:** MolitClient with URL-embed serviceKey encoding, XML result-code detection, and paginated fetch via httpx.AsyncClient.

## What Was Built

`pipeline/clients/molit.py` — the HTTP layer for fetching MOLIT open data portal transactions. Provides:

- `MolitClient` — async client class. `__init__` pre-encodes the raw API key via `quote(unquote(raw_key), safe='')` to avoid httpx double-encoding. `fetch_all()` loops pages until fewer items than `page_size` are returned.
- `_check_result_code(xml_text)` — detects HTTP-200 error responses by inspecting `<resultCode>` in the XML body. Returns `(True, "")` for codes `00`, `0000`, `000`; returns `(False, "Code {code}: {msg}")` for all others; returns `(False, "XML parse failure")` on `ET.ParseError`.
- `_parse_items(xml_text)` — extracts all `<item>` elements from the XML response as a list of dicts with whitespace-stripped text values.

## Tests Made GREEN

All 3 MOLIT tests (FOUND-02) and the full 9-test phase gate now pass:

- `test_molit_url_encoding` — verifies `safe_key == quote(unquote(raw_key), safe="")`
- `test_result_code_detection` — verifies `(False, msg)` for code `30`; `(True, "")` for code `00`
- `test_pagination_stops` — verifies exactly 2 HTTP GET calls with `page_size=5` when page 1 returns 5 items and page 2 returns 1 item; total 6 items returned
- All 9 tests in `tests/test_pipeline_foundation.py` GREEN (full phase gate)

## Deviations from Plan

**1. [Rule 3 - Blocking] `pytest` command vs `python -m pytest`**
- **Found during:** Task 1 verification
- **Issue:** Plain `pytest` command failed with `ModuleNotFoundError: No module named 'pipeline'` because the working directory is not in `sys.path` by default. The `pip install -e .` approach was blocked by a `pyproject.toml` scripts format error (invalid entrypoint format for `start`/`dev` scripts).
- **Fix:** Used `python -m pytest` which adds the CWD to `sys.path`, making the `pipeline` package importable. This is consistent with how Plan 01-02 tests were run.
- **Files modified:** None — existing test runner pattern carried forward.
- **Commit:** a25e792

## Self-Check: PASSED

- `pipeline/clients/molit.py` — FOUND
- Commit `a25e792` — FOUND
- All 9 tests GREEN — CONFIRMED
