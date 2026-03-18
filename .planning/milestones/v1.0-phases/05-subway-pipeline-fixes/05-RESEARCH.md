# Phase 5: Subway Pipeline Fixes — Research

**Researched:** 2026-03-18T07:34:41Z
**Domain:** Python SQLite schema migration + CLI dispatch wiring + Phase 3 verification
**Confidence:** HIGH — all gaps are diagnosed from actual source code; no speculation required

---

## Summary

Phase 5 is a targeted gap-closure phase. The v1.0 milestone audit identified two critical integration
defects and one missing verification record. The defects prevent any subway or commute data from ever
being written to the database in a standard `pipeline collect` run.

**Defect 1 (Geocoding not in CLI):** `geocode_all_apartments()` exists in
`pipeline/collectors/geocode.py` and is fully implemented. It is never called from
`pipeline/cli/main.py::collect()`. The subway collector queries
`WHERE latitude IS NOT NULL`, so with zero geocoded apartments, subway and commute
collection silently processes 0 rows. Fix: add `geocode` as a recognised `data_type` value
in the `collect()` dispatch block and wire it into the `subway`/`all` path.

**Defect 2 (UNIQUE constraint mismatch):** `pipeline/storage/schema.py` line 83 defines
`UNIQUE(apartment_id, station_name)` (2 columns) but the collector inserts per
`(apartment_id, station_name, line_name)` (3 columns). For any multi-line station (강남 =
Line 2 + Bundang, 신도림 = Line 1 + 2, etc.) the second insert is silently dropped by
`INSERT OR IGNORE`. Fix: change the constraint to `UNIQUE(apartment_id, station_name, line_name)`
and ship a `migrate_db()` migration that recreates the table.

**Defect 3 (Phase 3 VERIFICATION.md missing):** No `03-VERIFICATION.md` exists. All 8 Phase 3
requirements (SUBW-01..03, COMM-01..05) are unverified by the formal verifier. Fix: create
`03-VERIFICATION.md` after the two code fixes are confirmed working.

**Primary recommendation:** All three fixes fit in a single plan (05-01-PLAN.md). Fix the schema
migration first, then wire geocoding into CLI, then write the Phase 3 verification document.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUBW-01 | Naver Maps API (도보 경로) — apartments within 1km have walk distance in subway_distances | Schema UNIQUE fix enables correct multi-line storage; geocoding wiring provides populated coordinates |
| SUBW-02 | Line-separated rows in subway_distances (강남 → 2호선 + 분당선 each 1 row) | Requires UNIQUE(apartment_id, station_name, line_name) — 3-column constraint |
| SUBW-03 | Naver API response caching — same apartment not re-requested | Cache SELECT already uses 3-column key; fixing UNIQUE makes it consistent |
| COMM-05 | commute_stops BFS results stored | Depends on subway_distances having data (blocked by geocoding gap) |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new dependencies needed)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| sqlite3 | stdlib | DB schema migration | ALTER TABLE + recreate for UNIQUE change |
| pytest | 7.x | Test execution | Existing infrastructure |
| typer | >=0.12.0 | CLI dispatch | Already wired; only dispatch logic needs change |
| pipeline.collectors.geocode | project | geocode_all_apartments() | Fully implemented, just not called from CLI |
| pipeline.storage.schema | project | migrate_db() + init_db() | Must be extended with subway_distances migration |

### No New Dependencies

Phase 5 introduces zero new packages. All required code already exists — this phase only fixes
wiring and schema.

**Installation:**
```bash
# Nothing new to install — existing requirements.txt is sufficient
pip install -e .
```

---

## Architecture Patterns

### Pattern 1: SQLite UNIQUE Constraint Migration

SQLite does not support `ALTER TABLE ... DROP CONSTRAINT` or `ALTER TABLE ... ADD UNIQUE`.
The only way to change a UNIQUE constraint on an existing table is to recreate the table.

**Standard pattern (SQLite):**
```sql
-- Step 1: Create replacement table with correct constraint
CREATE TABLE IF NOT EXISTS subway_distances_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartments(id),
    station_name TEXT NOT NULL,
    line_name TEXT,
    walk_distance_m INTEGER,
    fetched_at TEXT DEFAULT (datetime('now')),
    UNIQUE(apartment_id, station_name, line_name)   -- 3 columns (was 2)
);

-- Step 2: Copy existing data (INSERT OR IGNORE handles any pre-existing dups)
INSERT OR IGNORE INTO subway_distances_new
    (id, apartment_id, station_name, line_name, walk_distance_m, fetched_at)
SELECT id, apartment_id, station_name, line_name, walk_distance_m, fetched_at
FROM subway_distances;

-- Step 3: Drop old table and rename
DROP TABLE subway_distances;
ALTER TABLE subway_distances_new RENAME TO subway_distances;
```

**Important:** This must run inside a transaction and be idempotent. The migrate_db() function
must detect whether the old 2-column constraint is still active and skip if already migrated.

**Idempotency detection:**
```python
# Check if constraint is already 3-column (migration already ran)
# SQLite stores CREATE TABLE DDL in sqlite_master
ddl = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='subway_distances'"
).fetchone()
if ddl and "station_name, line_name" in ddl[0]:
    return  # Already migrated
```

Confidence: HIGH — verified against SQLite official documentation behavior.

### Pattern 2: CLI data_type Dispatch Extension

Current `pipeline/cli/main.py::collect()` accepts `data_type` values:
`trade | rent | building | subway | all`

The `geocode` value is absent. The dispatch block must be extended:

```python
# Add after building dispatch, before subway dispatch:
if data_type in ("geocode", "subway", "all"):
    kakao_key = os.getenv("KAKAO_REST_API_KEY")
    if not kakao_key:
        typer.echo("KAKAO_REST_API_KEY not set — geocoding skipped.", err=True)
    else:
        from pipeline.collectors.geocode import geocode_all_apartments
        result = geocode_all_apartments(conn)
        typer.echo(f"Geocoding: {result}")
```

This ensures:
- `--data-type geocode` runs only geocoding
- `--data-type subway` runs geocoding then subway distances then commute stops
- `--data-type all` runs the full chain including geocoding

Confidence: HIGH — cli/main.py code reviewed directly; `geocode_all_apartments` signature confirmed.

### Pattern 3: Phase 3 VERIFICATION.md

The Phase 3 verification document must follow the same format as the existing
`01-VERIFICATION.md`, `02-VERIFICATION.md`, and `04-VERIFICATION.md` files.

Required frontmatter:
```yaml
---
phase: 03-geospatial-subway-graph
verified: {ISO timestamp}
status: passed
score: N/N must-haves verified
---
```

The document must cover: SUBW-01, SUBW-02, SUBW-03, COMM-01, COMM-02, COMM-03, COMM-04, COMM-05
(8 requirements). Evidence can come from the existing 03-04-SUMMARY.md and test results.

Confidence: HIGH — existing VERIFICATION.md files reviewed; format is consistent.

### Anti-Patterns to Avoid

- **Do not use `ALTER TABLE subway_distances ADD UNIQUE`**: SQLite does not support this syntax.
  Must use the table-recreate pattern.
- **Do not change `INSERT OR IGNORE` to `INSERT OR REPLACE` in subway_distances.py**: The collector
  already uses `INSERT OR IGNORE` which is correct with the 3-column key.
- **Do not add geocoding as a standalone `elif` that breaks `all`**: The `subway`/`all` path must
  include geocoding as a prerequisite step, not a separate branch.
- **Do not call `asyncio.run()` twice in the same CLI call**: Each collector already wraps
  `asyncio.run()` internally. The CLI `collect()` function is sync — calling two async-wrapping
  collectors sequentially is correct and safe.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UNIQUE constraint change | Custom migration framework | SQLite table-recreate pattern (3-step) | SQLite has no ALTER UNIQUE; table-recreate is the standard idiom |
| Geocoding integration | New geocode module | `geocode_all_apartments()` from pipeline/collectors/geocode.py | Already fully implemented; just needs CLI dispatch |
| Cache key consistency | New cache layer | Fix UNIQUE to match existing 3-column cache SELECT | Cache SELECT already uses 3-column key; schema was wrong |
| Phase 3 verification | Re-running all Phase 3 code | Write 03-VERIFICATION.md from evidence in 03-04-SUMMARY.md + test results | All evidence already exists; verifier just needs a document |

---

## Common Pitfalls

### Pitfall 1: migrate_db() Non-Idempotency
**What goes wrong:** If `migrate_db()` runs the subway_distances table recreation every time
`init_db()` is called, it wipes existing data on each DB open.
**Why it happens:** The recreation drops the old table before checking if migration was needed.
**How to avoid:** Check `sqlite_master` DDL before running migration. If `UNIQUE(apartment_id,
station_name, line_name)` already appears in the DDL string, skip the migration entirely.
**Warning signs:** DB has zero subway_distances rows after second init_db() call.

### Pitfall 2: geocode dispatch order in `all` path
**What goes wrong:** If subway distances run before geocoding, `WHERE latitude IS NOT NULL`
still returns 0 rows.
**Why it happens:** The `all` dispatch block processes in source-code order. If subway block
appears before geocode block, geocoding never runs first.
**How to avoid:** Geocoding dispatch must appear BEFORE subway dispatch in the `if data_type in
("subway", "all")` block — or add geocoding as an explicit prerequisite step inside the subway
block when `data_type == "all"`.
**Warning signs:** `Collecting 0 apartments for subway distances` in logs after `--data-type all`.

### Pitfall 3: KAKAO_REST_API_KEY not set → silent skip swallows downstream errors
**What goes wrong:** If `KAKAO_REST_API_KEY` is missing and we silently skip geocoding, the
subway step runs but processes 0 apartments — with no visible error about why.
**Why it happens:** The audit pattern for MOLIT_API_KEY follows a warn-and-skip pattern.
**How to avoid:** For `--data-type all`, print a clear warning that skipping geocoding will
cause subway collection to process 0 apartments. Do not silently skip.

### Pitfall 4: test_subway_distances_cache_hit uses old 2-column cache check
**What goes wrong:** After fixing UNIQUE to 3-column, the test's `SELECT 1 FROM
subway_distances WHERE apartment_id=? AND station_name='선릉'` (without line_name) may
still pass — but the cache check in the collector uses the 3-column key.
**Why it happens:** The test was written against the old 2-column semantics.
**How to avoid:** Update test if needed to verify 3-column cache behaviour; at minimum
ensure tests still pass with the new schema.

---

## Code Examples

### SQLite UNIQUE migration — idempotency check

```python
# Source: sqlite3 stdlib, sqlite_master introspection
def _needs_subway_unique_migration(conn: sqlite3.Connection) -> bool:
    """Return True if subway_distances still has the old 2-column UNIQUE constraint."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='subway_distances'"
    ).fetchone()
    if row is None:
        return False  # Table doesn't exist yet — CREATE TABLE handles it
    ddl: str = row[0]
    # Old constraint: UNIQUE(apartment_id, station_name)
    # New constraint: UNIQUE(apartment_id, station_name, line_name)
    return "line_name" not in ddl  # 2-column constraint present; needs migration
```

### CLI geocode dispatch addition (exact diff context)

Current `pipeline/cli/main.py` line 83:
```python
if data_type in ("subway", "all"):
    tmap_key = os.getenv("TMAP_APP_KEY")
```

New pattern:
```python
if data_type in ("geocode", "subway", "all"):
    kakao_key = os.getenv("KAKAO_REST_API_KEY")
    if not kakao_key:
        typer.echo("KAKAO_REST_API_KEY not set — geocoding skipped.", err=True)
    else:
        from pipeline.collectors.geocode import geocode_all_apartments
        result = geocode_all_apartments(conn)
        typer.echo(f"Geocoding: {result}")

if data_type in ("subway", "all"):
    tmap_key = os.getenv("TMAP_APP_KEY")
    ...
```

### migrate_db() extension pattern

```python
# Source: pipeline/storage/schema.py migrate_db() — existing pattern
def migrate_db(conn: sqlite3.Connection) -> None:
    """Add columns and fix constraints introduced after initial schema. Safe to call multiple times."""
    # Existing: lat/lon column additions
    for col, typedef in [("latitude", "REAL"), ("longitude", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE apartments ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass

    # New: Fix subway_distances UNIQUE(apartment_id, station_name) → UNIQUE(apartment_id, station_name, line_name)
    if _needs_subway_unique_migration(conn):
        conn.executescript("""
            BEGIN;
            CREATE TABLE IF NOT EXISTS subway_distances_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apartment_id INTEGER NOT NULL REFERENCES apartments(id),
                station_name TEXT NOT NULL,
                line_name TEXT,
                walk_distance_m INTEGER,
                fetched_at TEXT DEFAULT (datetime('now')),
                UNIQUE(apartment_id, station_name, line_name)
            );
            INSERT OR IGNORE INTO subway_distances_new
                (id, apartment_id, station_name, line_name, walk_distance_m, fetched_at)
            SELECT id, apartment_id, station_name, line_name, walk_distance_m, fetched_at
            FROM subway_distances;
            DROP TABLE subway_distances;
            ALTER TABLE subway_distances_new RENAME TO subway_distances;
            COMMIT;
        """)
```

---

## State of the Art

| Old State | Current Required State | Impact |
|-----------|----------------------|--------|
| `UNIQUE(apartment_id, station_name)` — 2 columns | `UNIQUE(apartment_id, station_name, line_name)` — 3 columns | Multi-line stations (강남 etc.) store both lines correctly |
| geocode not in CLI collect() | `data_type in ("geocode", "subway", "all")` dispatches geocode | Full E2E pipeline works without manual geocoding step |
| No 03-VERIFICATION.md | 03-VERIFICATION.md with status: passed | Phase 3 requirements formally verified |

---

## Open Questions

1. **Does the existing realestate.db on disk have data in subway_distances?**
   - What we know: Live DB exists (`realestate.db` in git status). If it has subway_distances rows
     with the old 2-column constraint, the migration must preserve them.
   - What's unclear: Whether any real data was collected (requires real API keys to have been run).
   - Recommendation: The migration uses `INSERT OR IGNORE` when copying data, so even with duplicate
     (apt_id, station_name) pairs from the old schema, the migration is safe. No special case needed.

2. **Should `--data-type geocode` be a separate subcommand or a data_type option?**
   - What we know: Current CLI uses `--data-type` for all collection types. The audit description
     says "add geocode as a data_type option or auto-run before subway step."
   - Recommendation: Add as `data_type` option, consistent with existing pattern. No new subcommand
     needed. This satisfies the success criteria: `pipeline collect --data-type geocode`.

3. **Does the Phase 3 VERIFICATION.md need a human checkpoint?**
   - What we know: Phase 4 VERIFICATION.md was created by the automated verifier with one human
     checkpoint for CLI commands. Phase 3 is code-only (no terminal interaction).
   - Recommendation: No human checkpoint required. The verifier can confirm all evidence from
     existing test results (10/10 xpassed in 03-04-SUMMARY.md) and code inspection.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_pipeline_phase3.py tests/test_pipeline_phase4.py -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUBW-01 | subway_distances stores walk_distance_m per (apt, station, line) | unit | `pytest tests/test_pipeline_phase3.py::test_subway_distances_null_over_1km -v` | ✅ |
| SUBW-02 | Multi-line station rows: 2 rows for 강남 (2호선 + 분당선) | unit | `pytest tests/test_pipeline_phase5.py::test_subway_distances_multiline -v` | ❌ Wave 0 |
| SUBW-03 | Cache hit: same (apt_id, station, line) not re-inserted | unit | `pytest tests/test_pipeline_phase3.py::test_subway_distances_cache_hit -v` | ✅ |
| COMM-05 | commute_stops populated after subway_distances has data | unit | `pytest tests/test_pipeline_phase3.py::test_commute_stops_upsert -v` | ✅ |
| CLI geocode | `collect --data-type geocode` dispatches geocode_all_apartments | unit | `pytest tests/test_pipeline_phase5.py::test_collect_geocode_dispatch -v` | ❌ Wave 0 |
| CLI subway chain | `collect --data-type subway` runs geocode then subway | unit | `pytest tests/test_pipeline_phase5.py::test_collect_subway_runs_geocode_first -v` | ❌ Wave 0 |
| Schema migration | migrate_db() produces 3-column UNIQUE on subway_distances | unit | `pytest tests/test_pipeline_phase5.py::test_migrate_subway_unique -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline_phase3.py tests/test_pipeline_phase5.py -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_phase5.py` — covers SUBW-02 multiline, CLI geocode dispatch, schema migration
- [ ] No additional fixtures needed — existing `init_db(":memory:")` pattern from phase3/phase4 tests is sufficient

---

## Sources

### Primary (HIGH confidence)
- `pipeline/storage/schema.py` lines 76–84 — exact UNIQUE constraint text confirmed by direct code read
- `pipeline/cli/main.py` lines 47–96 — full collect() dispatch block confirmed; `geocode` absent confirmed
- `pipeline/collectors/geocode.py` — `geocode_all_apartments()` fully implemented; KAKAO_REST_API_KEY required
- `pipeline/collectors/subway_distances.py` lines 77–82 — cache SELECT uses 3-column key confirmed
- `.planning/v1.0-MILESTONE-AUDIT.md` — audit diagnosis used as primary gap specification

### Secondary (MEDIUM confidence)
- SQLite official docs: `ALTER TABLE` does not support constraint changes → table recreate pattern required
- `.planning/phases/03-geospatial-subway-graph/03-04-SUMMARY.md` — all 10 Phase 3 tests xpassed confirmed

### Tertiary (LOW confidence — none applicable)
- No LOW-confidence findings. All claims verified against source code in repository.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all files directly read
- Architecture patterns: HIGH — schema DDL and CLI dispatch verified line-by-line
- Pitfalls: HIGH — derived from actual code behavior, not speculation
- SQLite migration pattern: HIGH — table recreate is the documented approach for UNIQUE changes

**Research date:** 2026-03-18T07:34:41Z
**Valid until:** 2026-04-18 (stable — codebase is local, not a changing upstream dependency)
