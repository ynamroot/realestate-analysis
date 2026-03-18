---
phase: 05-subway-pipeline-fixes
verified: 2026-03-18T08:00:53Z
status: passed
score: 5/5 must-haves verified
---

# Phase 5: Subway Pipeline Fixes Verification Report

**Phase Goal:** CLI geocoding 누락과 subway_distances UNIQUE 제약조건 불일치를 수정하여, `pipeline collect --data-type all` 실행 시 지하철 거리와 출퇴근 정거장 수가 실제로 계산·저장되고, Phase 3 검증 기록이 존재한다
**Verified:** 2026-03-18T08:00:53Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pipeline collect --data-type geocode` dispatches to geocode_all_apartments() | VERIFIED | `pipeline/cli/main.py` lines 83-96: `if data_type in ("geocode", "subway", "all")` block imports and calls `geocode_all_apartments(conn)`; `test_collect_geocode_dispatch` XPASS |
| 2 | subway_distances has UNIQUE(apartment_id, station_name, line_name) after migrate_db() | VERIFIED | `init_db(":memory:")` DDL confirmed: `UNIQUE(apartment_id, station_name, line_name)`; `test_migrate_subway_unique` XPASS; schema check script returned OK |
| 3 | migrate_db() detects old 2-column constraint via `_needs_subway_unique_migration()` and skips if already migrated | VERIFIED | `pipeline/storage/schema.py` lines 125-167: `_needs_subway_unique_migration()` checks for `"station_name, line_name"` in DDL (not just column name); idempotent — returns False if already migrated |
| 4 | `pipeline collect --data-type subway` runs geocoding BEFORE subway distances | VERIFIED | Lines 83-108 in `pipeline/cli/main.py`: geocode block (lines 83-96) appears before subway block (lines 98-108) in source order; `test_collect_subway_runs_geocode_first` XPASS confirms call order |
| 5 | Phase 3 VERIFICATION.md exists with status: passed | VERIFIED | `.planning/phases/03-geospatial-subway-graph/03-VERIFICATION.md` exists, frontmatter contains `status: passed` and `score: 8/8 must-haves verified` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_pipeline_phase5.py` | 4 pytest tests covering SUBW-02 multiline, CLI geocode dispatch, subway-runs-geocode-first, and migrate_db idempotency | VERIFIED | 91 lines, 4 `def test_` functions, all 4 `@pytest.mark.xfail`; all 4 XPASS in live run |
| `pipeline/storage/schema.py` | migrate_db() extended with `_needs_subway_unique_migration()` helper and 3-step SQLite table-recreate migration | VERIFIED | `_needs_subway_unique_migration()` at lines 125-135; migration executescript at lines 149-167; `UNIQUE(apartment_id, station_name, line_name)` present |
| `pipeline/cli/main.py` | collect() dispatch block with geocode as recognised data_type, geocoding runs before subway step | VERIFIED | Help text updated to include `geocode`; geocode block at lines 83-96 precedes subway block at lines 98-108 |
| `.planning/phases/03-geospatial-subway-graph/03-VERIFICATION.md` | Formal Phase 3 verification record with status: passed | VERIFIED | File exists, frontmatter `status: passed`, `score: 8/8 must-haves verified`, 8 SATISFIED requirements in coverage table |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pipeline/cli/main.py:collect()` | `pipeline.collectors.geocode.geocode_all_apartments` | `data_type in ('geocode', 'subway', 'all')` dispatch block | WIRED | Line 94 imports and line 95 calls `geocode_all_apartments(conn)`; test mock confirms invocation |
| `pipeline/storage/schema.py:migrate_db()` | `subway_distances_new` table | `_needs_subway_unique_migration()` sqlite_master DDL check then 3-step table recreate | WIRED | `_needs_subway_unique_migration()` called at line 148; `subway_distances_new` appears at CREATE (151), INSERT (160), DROP old (164), ALTER RENAME (165) |
| `pipeline/cli/main.py:collect()` | geocode dispatch BEFORE subway dispatch | geocode if-block appears before subway if-block in source order | WIRED | Geocode block lines 83-96; subway block lines 98-108; `test_collect_subway_runs_geocode_first` verifies runtime call order as geocode→subway |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SUBW-01 | 05-01 | TMAP pedestrian API walk distance — CLI must geocode first so apartments have coordinates | SATISFIED | Geocode dispatch block wired before subway dispatch in `collect()`; prevents 0-row silent failure |
| SUBW-02 | 05-01 | Line-separated rows — subway_distances UNIQUE must be 3-column `(apartment_id, station_name, line_name)` | SATISFIED | `migrate_db()` upgrades to 3-column UNIQUE; `test_subway_distances_multiline` XPASS confirms 강남역 2호선 + 분당선 store as 2 separate rows |
| SUBW-03 | 05-01 | Cache check skips TMAP for same (apt_id, station_name, line_name) — requires 3-column UNIQUE to function correctly | SATISFIED | 3-column UNIQUE now matches the 3-column cache SELECT key used by `subway_distances.py` collector; `test_collect_subway_runs_geocode_first` XPASS |
| COMM-05 | 05-01 | commute_stops INSERT OR REPLACE stores BFS results — geocode prerequisite ensures non-zero input | SATISFIED | Geocode runs before subway/commute in `collect()` so `WHERE latitude IS NOT NULL` yields actual rows; warning emitted when KAKAO key absent |

All 4 Phase 5 requirements are SATISFIED.

### Anti-Patterns Found

No anti-patterns detected in modified files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None | — | — |

### Human Verification Required

No items require human verification. All truths are verifiable through static analysis and automated tests.

The following items are noted as context-dependent but not blocking:

1. **Live API run** — `pipeline collect --data-type all` with real KAKAO and TMAP keys. The wiring is confirmed correct by mocked tests; a live run would confirm API credentials and data throughput.
   - Expected: geocoding populates apartments.latitude/longitude, subway distances stored with 3-column UNIQUE rows, commute_stops populated.
   - Why optional: The gap being fixed was structural (wrong wiring, wrong constraint) — not API-credential-dependent. Wiring is now correct.

### Test Suite Results

```
pytest tests/test_pipeline_phase5.py -v
4 xpassed in 1.32s

pytest tests/ --ignore=tests/test_fastmcp.py --ignore=tests/test_mcp.py -q
24 passed, 26 xpassed in 1.40s
```

All 4 Phase 5 tests: 4 xpassed (0 failures, 0 xfailed).
Full pipeline suite: 24 passed + 26 xpassed. No regressions.

Pre-existing failures in `test_fastmcp.py` and `test_mcp.py` (async event loop issues) are excluded — confirmed pre-existing before Phase 5 changes per 05-01-SUMMARY.md.

### Gaps Summary

No gaps. All 5 observable truths verified. Phase goal achieved.

---

_Verified: 2026-03-18T08:00:53Z_
_Verifier: Claude (gsd-verifier)_
