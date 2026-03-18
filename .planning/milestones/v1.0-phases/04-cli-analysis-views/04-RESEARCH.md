# Phase 4: CLI + Analysis Views - Research

**Researched:** 2026-03-18T05:32:44Z
**Domain:** Typer CLI, SQLite CREATE VIEW, pandas CSV export, pipeline orchestration
**Confidence:** HIGH (Typer official docs confirmed; SQLite VIEW patterns from official SQLite docs; pandas encoding from multiple verified sources)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | Typer 기반 CLI — `collect`, `export`, `status` 서브커맨드 | `typer 0.24.1` is the latest stable release; `@app.command()` decorator registers each subcommand; `[project.scripts]` in pyproject.toml exposes `pipeline` as installed CLI command |
| CLI-02 | 수집 대상(지역, 기간, 데이터 유형) 옵션 선택 가능 | `typer.Option()` with `Optional[str]` handles `--region`, `--start`, `--data-type`; type annotations auto-validate input; existing `PIPELINE_REGIONS`, `SEOUL_REGIONS`, `get_month_range()` handle region/period filtering |
| CLI-03 | pandas `read_sql()` + `to_csv(encoding='utf-8-sig')` 엑셀 호환 CSV 내보내기 | `pd.read_sql("SELECT * FROM apartment_analysis", conn)` reads the VIEW into DataFrame; `df.to_csv(path, encoding='utf-8-sig', index=False)` writes BOM-prefixed UTF-8 that Excel opens correctly without mojibake |
| CLI-04 | 분석용 SQLite VIEW — 아파트별 최신 시세, 전세가율, 업무지구 접근성 통합 뷰 | `CREATE VIEW IF NOT EXISTS apartment_analysis AS` pattern; latest trade/rent prices via correlated MAX(deal_ym) subqueries; 전세가율 = deposit_avg / price_avg * 100; LEFT JOINs to subway_distances and commute_stops for transit fields |
</phase_requirements>

---

## Summary

Phase 4 is the "last mile" of the pipeline: exposing what was built in Phases 1–3 through a clean CLI interface and a consolidated SQL VIEW. The domain splits into three independent sub-problems that can be planned as parallel waves: (1) the Typer CLI app with `collect`/`export`/`status` subcommands, (2) the `apartment_analysis` SQLite VIEW, and (3) the pandas CSV export logic.

All Phase 1–3 infrastructure is complete and verified. The CLI does not need to implement collection logic itself — it calls `collect_all_regions()`, `collect_all_building_info()`, and `collect_all_subway_distances()` from existing modules. The CLI's job is to wire options to these existing functions and present output. This makes Phase 4 relatively thin: the planner should budget 3–4 tasks, not more.

The most technically nuanced part is the `apartment_analysis` VIEW SQL. Getting the "latest" trade and rent prices requires a correlated subquery pattern (NOT a JOIN to MAX(deal_ym) — the JOIN approach fails when the same apartment has different max months per deal_type). The VIEW must be created idempotently inside `init_db()` or as a separate `create_views()` call in schema.py, following the existing `CREATE TABLE IF NOT EXISTS` pattern.

**Primary recommendation:** Use Typer 0.12+ with `@app.command()` subcommands, add `pipeline = "pipeline.cli.main:app"` to `[project.scripts]` in pyproject.toml, create the VIEW in schema.py alongside existing tables, and use `pd.read_sql()` + `to_csv(encoding='utf-8-sig')` for the export command.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.1 (latest) | CLI framework with subcommands, options, auto-help | Based on Click; type hint driven; no manual argparse; already project style |
| pandas | >=2.0 | `read_sql()` → DataFrame, `to_csv(encoding='utf-8-sig')` | Already in project; single-line VIEW → CSV pipeline |
| sqlite3 | stdlib | Connection to realestate.db for VIEW definition and `status` query | Already in codebase from Phase 1/2 |
| rich | >=13.0 (typer dep) | Terminal table formatting for `status` output | Auto-installed as typer dependency; `typer.echo()` and `rich.table` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0.0 | Load `TMAP_APP_KEY`, `KAKAO_REST_API_KEY` from .env for `collect` command | Already in codebase; CLI must load env before calling collectors |
| loguru | >=0.7.2 | Progress logging during collect runs | Already in codebase; collectors already emit loguru messages |
| pathlib | stdlib | Path handling for `--output` file path in `export` command | Cleaner than os.path for cross-platform CLI path handling |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | Click directly | Typer IS Click; Typer adds type hint magic and auto-help; prefer Typer for new code |
| Typer | argparse | argparse is stdlib but verbose; Typer is 3x less code for same functionality |
| `pd.read_sql()` | Direct sqlite3 cursor + csv.writer | `read_sql()` handles type inference and column names automatically; csv.writer requires manual header management |
| SQLite VIEW in schema.py | Separate migration file | Project has no migration framework; schema.py already uses `CREATE TABLE IF NOT EXISTS`; adding `CREATE VIEW IF NOT EXISTS` to same file is consistent |

**Installation:**

```bash
pip install typer>=0.12.0 pandas
# pandas already installed in project; typer is the only new dependency
```

---

## Architecture Patterns

### Recommended Module Structure

```
pipeline/
├── cli/
│   ├── __init__.py
│   └── main.py          # typer app with collect/export/status subcommands
├── storage/
│   └── schema.py        # ADD: create_views() called from init_db() or standalone
└── ...                  # (all other modules already exist from Phases 1-3)
```

The CLI module is the only new directory. All other changes are additive modifications to existing files.

### Pattern 1: Typer App with Subcommands

**What:** Single `app = typer.Typer()` instance; each subcommand is decorated with `@app.command()`. App is registered as `pipeline` console script.

**When to use:** This is the standard Typer pattern for multi-command CLIs. No sub-app nesting needed since `collect`, `export`, `status` are all at the same level.

```python
# Source: typer.tiangolo.com/tutorial/commands/ (HIGH confidence)
import typer
from typing import Optional

app = typer.Typer(no_args_is_help=True, help="부동산 데이터 수집 파이프라인")

@app.command()
def collect(
    region: Optional[str] = typer.Option(None, help="지역 필터 (예: seoul, 강남구). 미지정 시 전체 29개 지역"),
    start: str = typer.Option("200601", help="수집 시작 월 YYYYMM"),
    data_type: Optional[str] = typer.Option(None, help="trade | rent | building | all (기본값: all)"),
):
    """아파트 실거래가 + 건물정보 + 지하철 거리 수집"""
    ...

@app.command()
def export(
    output: str = typer.Option("output.csv", help="출력 CSV 파일 경로"),
    query: Optional[str] = typer.Option(None, help="커스텀 SQL (기본값: SELECT * FROM apartment_analysis)"),
):
    """분석 VIEW를 UTF-8 BOM CSV로 내보내기"""
    ...

@app.command()
def status():
    """지역별 수집 현황 (마지막 수집 월, 레코드 수) 출력"""
    ...

if __name__ == "__main__":
    app()
```

**pyproject.toml addition:**

```toml
[project.scripts]
pipeline = "pipeline.cli.main:app"
```

### Pattern 2: apartment_analysis SQLite VIEW

**What:** A `CREATE VIEW IF NOT EXISTS apartment_analysis` that JOINs apartments, latest monthly_prices (both trade and rent), building_info, subway_distances (nearest), and commute_stops into a single flat row per apartment.

**Critical SQL detail — latest price per deal_type:** Use a correlated subquery (`WHERE mp.deal_ym = (SELECT MAX(...) WHERE ...)`), NOT a JOIN to a GROUP BY subquery. The GROUP BY approach returns wrong results when trade and rent have different max months for the same apartment.

**전세가율 formula:** `CAST(latest_deposit_avg AS REAL) / NULLIF(latest_price_avg, 0) * 100` — handles NULL and division-by-zero safely.

```sql
-- Source: SQLite official docs (windowfunctions.html, lang_corefunc.html) — HIGH confidence
-- Pattern: correlated MAX subquery for latest-row-per-group (SQLite 3.25+)
CREATE VIEW IF NOT EXISTS apartment_analysis AS
SELECT
    a.id                        AS apartment_id,
    a.lawd_cd,
    a.apt_nm,
    a.umd_nm,
    a.build_year,
    a.total_households,
    a.latitude,
    a.longitude,

    -- 최신 매매가 (trade)
    t.deal_ym                   AS latest_trade_ym,
    t.price_avg                 AS latest_trade_price_avg,
    t.price_min                 AS latest_trade_price_min,
    t.price_max                 AS latest_trade_price_max,
    t.deal_count                AS latest_trade_deal_count,

    -- 최신 전세가 (rent)
    r.deal_ym                   AS latest_rent_ym,
    r.deposit_avg               AS latest_rent_deposit_avg,

    -- 전세가율 (%)
    CASE
        WHEN t.price_avg IS NOT NULL AND t.price_avg > 0 AND r.deposit_avg IS NOT NULL
        THEN ROUND(CAST(r.deposit_avg AS REAL) / t.price_avg * 100, 1)
        ELSE NULL
    END                         AS jeonse_ratio_pct,

    -- 업무지구 접근성 (commute_stops)
    cs.nearest_station,
    cs.stops_to_gbd,
    cs.stops_to_cbd,
    cs.stops_to_ybd,

    -- 최근접 지하철역 도보거리 (subway_distances - 최단 walk)
    (
        SELECT sd.station_name || ' (' || sd.line_name || ')'
        FROM subway_distances sd
        WHERE sd.apartment_id = a.id
          AND sd.walk_distance_m IS NOT NULL
        ORDER BY sd.walk_distance_m
        LIMIT 1
    )                           AS nearest_subway_label,
    (
        SELECT sd.walk_distance_m
        FROM subway_distances sd
        WHERE sd.apartment_id = a.id
          AND sd.walk_distance_m IS NOT NULL
        ORDER BY sd.walk_distance_m
        LIMIT 1
    )                           AS nearest_subway_walk_m

FROM apartments a

-- 최신 매매가: correlated subquery로 MAX(deal_ym) 선택
LEFT JOIN monthly_prices t
    ON t.apartment_id = a.id
   AND t.deal_type = 'trade'
   AND t.deal_ym = (
       SELECT MAX(mp2.deal_ym)
       FROM monthly_prices mp2
       WHERE mp2.apartment_id = a.id
         AND mp2.deal_type = 'trade'
   )

-- 최신 전세가: 동일 패턴
LEFT JOIN monthly_prices r
    ON r.apartment_id = a.id
   AND r.deal_type = 'rent'
   AND r.deal_ym = (
       SELECT MAX(mp3.deal_ym)
       FROM monthly_prices mp3
       WHERE mp3.apartment_id = a.id
         AND mp3.deal_type = 'rent'
   )

LEFT JOIN commute_stops cs ON cs.apartment_id = a.id;
```

### Pattern 3: pandas CSV Export

**What:** `pd.read_sql(sql, conn)` reads the VIEW (or any SQL) into a DataFrame; `df.to_csv(path, encoding='utf-8-sig', index=False)` writes BOM-prefixed UTF-8.

**Why utf-8-sig matters:** Excel on Windows/Mac detects the BOM (U+FEFF) and auto-selects UTF-8, preventing Korean character mojibake. Without the BOM, Excel defaults to the system code page (EUC-KR on Korean Windows, cp1252 on Western), corrupting Korean characters.

```python
# Source: pandas official docs + verified from multiple sources (HIGH confidence)
import pandas as pd
import sqlite3

def export_to_csv(conn: sqlite3.Connection, output_path: str, sql: str | None = None) -> int:
    """
    Export query result to UTF-8 BOM CSV for Excel compatibility.

    Args:
        conn: Open sqlite3 connection.
        output_path: Destination CSV path.
        sql: Custom SQL query. Defaults to SELECT * FROM apartment_analysis.

    Returns:
        Row count exported.
    """
    query = sql or "SELECT * FROM apartment_analysis"
    df = pd.read_sql(query, conn)
    df.to_csv(output_path, encoding="utf-8-sig", index=False)
    return len(df)
```

### Pattern 4: status Command — Collection Log Summary

**What:** Query `collection_log` grouped by `lawd_cd` and `data_type` to show last collected month and row count per region.

```python
# Source: existing collection_log schema + sqlite3 stdlib (HIGH confidence)
STATUS_SQL = """
SELECT
    cl.lawd_cd,
    cl.data_type,
    MAX(cl.deal_ym)     AS last_ym,
    SUM(cl.record_count) AS total_records
FROM collection_log cl
GROUP BY cl.lawd_cd, cl.data_type
ORDER BY cl.lawd_cd, cl.data_type
"""
```

### Pattern 5: DB Connection in CLI Commands

**What:** Each CLI command opens its own connection to `realestate.db`, calls `init_db()` to ensure schema/views exist, then runs its logic.

```python
# Source: existing project pattern (schema.py, collectors) — HIGH confidence
from pipeline.storage.schema import DB_PATH, init_db

def _get_conn() -> sqlite3.Connection:
    conn = init_db(DB_PATH)  # idempotent — safe to call on every CLI invocation
    return conn
```

### Anti-Patterns to Avoid

- **Calling `asyncio.run()` twice in the same process:** The `collect` command must call `collect_all_regions()` and `collect_all_building_info()` sequentially (each uses `asyncio.run()` internally). Do not nest them — each must complete before the next starts.
- **Creating VIEW in `collect` subcommand only:** VIEW must be created in `init_db()` or `create_views()` so `export` and pandas users can query it without running `collect` first.
- **Using `encoding='utf-8'` instead of `encoding='utf-8-sig'`:** Plain utf-8 works in text editors but Excel ignores the encoding declaration in the CSV and defaults to system code page. The BOM is required.
- **JOIN to GROUP BY subquery for latest price:** `LEFT JOIN (SELECT apartment_id, MAX(deal_ym) FROM monthly_prices WHERE deal_type='trade' GROUP BY apartment_id) mx ON ...` fails when an apartment has multiple size-band rows for the same max month — produces duplicate VIEW rows. Correlated subquery with `WHERE deal_ym = (SELECT MAX(...))` is correct.
- **Hardcoding DB path in CLI:** Use `DB_PATH` from `pipeline.storage.schema` — already the project's single source of truth for the database path.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | argparse or sys.argv parsing | `typer.Option()` / `typer.Argument()` | Typer handles type coercion, help generation, shell completion automatically |
| CSV encoding for Korean Excel | Custom BOM prepend or codec setup | `df.to_csv(path, encoding='utf-8-sig')` | pandas handles the BOM byte sequence (EF BB BF) correctly and cross-platform |
| "Latest price" query | Python loop over all prices | Correlated SQL subquery in VIEW | The DB handles this in a single pass; Python loop would require loading all monthly_prices into memory |
| Status table formatting | Manual string padding | `typer.echo()` with Rich markup OR simple f-string table | Rich is already installed as typer dependency; use `rich.table.Table` for aligned columns |
| Region name → LAWD_CD mapping | New lookup table | `PIPELINE_REGIONS` dict in `pipeline.config.regions` | Already contains all 29 districts with correct codes; CLI `--region` filter should match against this dict's keys |

**Key insight:** Phase 4 is a thin orchestration layer. Almost every capability already exists in Phase 1–3 modules. The planner should avoid duplicating logic that is already implemented and tested.

---

## Common Pitfalls

### Pitfall 1: VIEW Created After DB Open — "no such table" Error

**What goes wrong:** If `create_views()` is called before `init_db()` (or not called at all), `SELECT * FROM apartment_analysis` raises `sqlite3.OperationalError: no such table: apartment_analysis`.

**Why it happens:** SQLite VIEWs are stored as named schema objects. They must be created in the same DB file that the user is querying. A fresh `realestate.db` only has the 6 tables from Phase 1 schema.

**How to avoid:** Call `create_views()` from within `init_db()` (add it at the end of the existing `executescript`), OR as a dedicated call at the top of each CLI command after `init_db()`. The former is simpler and ensures the VIEW always exists.

**Warning signs:** `pd.read_sql("SELECT * FROM apartment_analysis", conn)` raises OperationalError.

### Pitfall 2: asyncio.run() Cannot Be Called From Inside an Async Context

**What goes wrong:** If `collect` is wired as an `async def` Typer command (or called from a running event loop), `asyncio.run()` inside `collect_all_regions()` raises `RuntimeError: This event loop is already running`.

**Why it happens:** `collect_all_regions()` uses `asyncio.run()` as its sync entry point. Typer commands are synchronous by default. If a developer wraps the command as `async def`, Typer (via Click) does not automatically create an event loop — the `asyncio.run()` inside collectors will conflict.

**How to avoid:** Keep CLI command functions as plain `def` (not `async def`). The existing `collect_all_regions()` / `collect_all_building_info()` / `collect_all_subway_distances()` are already synchronous entry points with internal `asyncio.run()`.

**Warning signs:** `RuntimeError: This event loop is already running` when running `pipeline collect`.

### Pitfall 3: --region Option Does Not Match PIPELINE_REGIONS Keys

**What goes wrong:** User runs `pipeline collect --region seoul` but `PIPELINE_REGIONS` has no "seoul" key — the collect command silently processes zero regions or raises a KeyError.

**Why it happens:** `PIPELINE_REGIONS` uses Korean district names ("강남구", "과천시", etc.). A shorthand "seoul" or "gangnam" filter needs a separate resolution step.

**How to avoid:** Implement `--region` as a shorthand filter: `"seoul"` → filter `PIPELINE_REGIONS` to keys in `SEOUL_REGIONS`; `"gyeonggi"` → `GYEONGGI_REGIONS`; an exact Korean name like "강남구" → look up directly; unrecognized value → print error and exit with `typer.Exit(1)`. The success criterion uses `--region seoul` as an example — SEOUL_REGIONS is already defined in `pipeline.config.regions`.

**Warning signs:** `pipeline collect --region seoul` produces "Collecting 0 regions" with no error.

### Pitfall 4: VIEW Produces Duplicate Rows When Multiple exclu_use_ar Values Exist

**What goes wrong:** The `monthly_prices` table stores one row per `(apartment_id, deal_type, deal_ym, exclu_use_ar)` — multiple size bands per month. A VIEW JOIN on MAX(deal_ym) alone will match ALL size-band rows for that month, producing N duplicate VIEW rows per apartment.

**Why it happens:** The VIEW requires "latest price" but the table stores disaggregated size bands. The VIEW must aggregate or pick a representative row (e.g., the most common size band or the average across bands).

**How to avoid:** In the VIEW's correlated subquery, also GROUP BY or use a secondary correlated subquery to aggregate across size bands for the max month:
```sql
-- Aggregate trade prices for latest month across all size bands
LEFT JOIN (
    SELECT apartment_id,
           deal_ym,
           AVG(price_avg)   AS price_avg,
           MIN(price_min)   AS price_min,
           MAX(price_max)   AS price_max,
           SUM(deal_count)  AS deal_count
    FROM monthly_prices
    WHERE deal_type = 'trade'
    GROUP BY apartment_id, deal_ym
) t_agg ON t_agg.apartment_id = a.id
       AND t_agg.deal_ym = (
           SELECT MAX(deal_ym) FROM monthly_prices
           WHERE apartment_id = a.id AND deal_type = 'trade'
       )
```
This JOIN approach with pre-aggregation is cleaner than the correlated subquery shown in Pattern 2 when size bands exist. **The planner must choose one pattern and be consistent.**

**Warning signs:** `SELECT COUNT(*) FROM apartment_analysis` > `SELECT COUNT(*) FROM apartments`.

### Pitfall 5: pandas read_sql Requires Connection Object, Not Just Path

**What goes wrong:** `pd.read_sql(sql, "realestate.db")` raises `AttributeError: 'str' object has no attribute 'cursor'`.

**Why it happens:** `pd.read_sql` first argument is `sql`, second is `con` which must be a DBAPI2 connection or SQLAlchemy engine — not a file path string.

**How to avoid:** Always pass an open `sqlite3.Connection` object: `pd.read_sql(sql, conn)` where `conn = init_db(DB_PATH)`.

---

## Code Examples

Verified patterns from official sources:

### Typer App Registration in pyproject.toml

```toml
# Source: typer.tiangolo.com/tutorial/package/ (HIGH confidence)
[project.scripts]
pipeline = "pipeline.cli.main:app"
```

After `pip install -e .`, users run `pipeline collect ...` directly from the terminal.

### Full Typer collect Command Skeleton

```python
# Source: typer.tiangolo.com/tutorial/commands/ + typer.tiangolo.com/tutorial/options/ (HIGH confidence)
import typer
from typing import Optional
from dotenv import load_dotenv
from pipeline.storage.schema import DB_PATH, init_db
from pipeline.config.regions import PIPELINE_REGIONS, SEOUL_REGIONS, GYEONGGI_REGIONS

app = typer.Typer(no_args_is_help=True)

def _resolve_regions(region: Optional[str]) -> dict[str, str]:
    """Map --region shorthand to LAWD_CD dict."""
    if region is None:
        return PIPELINE_REGIONS
    if region.lower() == "seoul":
        return SEOUL_REGIONS
    if region.lower() == "gyeonggi":
        return GYEONGGI_REGIONS
    if region in PIPELINE_REGIONS:
        return {region: PIPELINE_REGIONS[region]}
    typer.echo(f"Unknown region: {region}. Use 'seoul', 'gyeonggi', or a Korean district name.", err=True)
    raise typer.Exit(1)

@app.command()
def collect(
    region: Optional[str] = typer.Option(None, help="seoul | gyeonggi | 강남구 | ... (기본값: 전체)"),
    start: str = typer.Option("200601", help="수집 시작 월 YYYYMM"),
    data_type: str = typer.Option("all", help="trade | rent | building | subway | all"),
):
    load_dotenv()
    conn = init_db(DB_PATH)
    regions = _resolve_regions(region)
    typer.echo(f"Collecting {len(regions)} region(s) from {start} ...")
    # ... dispatch to collect_all_regions, collect_all_building_info, etc.
```

### status Command with Formatted Output

```python
# Source: sqlite3 stdlib + existing collection_log schema (HIGH confidence)
@app.command()
def status():
    """지역별 수집 현황 출력"""
    conn = init_db(DB_PATH)
    rows = conn.execute("""
        SELECT lawd_cd, data_type, MAX(deal_ym) AS last_ym,
               SUM(record_count) AS total_records
        FROM collection_log
        GROUP BY lawd_cd, data_type
        ORDER BY lawd_cd, data_type
    """).fetchall()
    if not rows:
        typer.echo("No data collected yet.")
        return
    typer.echo(f"{'LAWD_CD':<10} {'Type':<10} {'Last YM':<10} {'Records':>10}")
    typer.echo("-" * 44)
    for r in rows:
        typer.echo(f"{r['lawd_cd']:<10} {r['data_type']:<10} {r['last_ym']:<10} {r['total_records']:>10,}")
```

### export Command

```python
# Source: pandas docs — pd.read_sql + to_csv(encoding='utf-8-sig') (HIGH confidence)
import pandas as pd

@app.command()
def export(
    output: str = typer.Option("output.csv", "--output", "-o", help="CSV 출력 경로"),
):
    """apartment_analysis VIEW를 Excel 호환 UTF-8 BOM CSV로 내보내기"""
    conn = init_db(DB_PATH)
    df = pd.read_sql("SELECT * FROM apartment_analysis", conn)
    df.to_csv(output, encoding="utf-8-sig", index=False)
    typer.echo(f"Exported {len(df):,} rows to {output}")
```

### create_views() in schema.py

```python
# Source: SQLite official docs CREATE VIEW (HIGH confidence)
def create_views(conn: sqlite3.Connection) -> None:
    """
    Create analysis views. Safe to call multiple times (CREATE VIEW IF NOT EXISTS).
    Called automatically by init_db().
    """
    conn.executescript("""
        DROP VIEW IF EXISTS apartment_analysis;
        CREATE VIEW apartment_analysis AS
        SELECT
            a.id          AS apartment_id,
            a.lawd_cd,
            a.apt_nm,
            a.umd_nm,
            a.build_year,
            a.total_households,
            a.latitude,
            a.longitude,

            t_agg.deal_ym      AS latest_trade_ym,
            t_agg.price_avg    AS latest_trade_price_avg,
            t_agg.price_min    AS latest_trade_price_min,
            t_agg.price_max    AS latest_trade_price_max,
            t_agg.deal_count   AS latest_trade_deal_count,

            r_agg.deal_ym      AS latest_rent_ym,
            r_agg.deposit_avg  AS latest_rent_deposit_avg,

            CASE
                WHEN t_agg.price_avg IS NOT NULL AND t_agg.price_avg > 0
                     AND r_agg.deposit_avg IS NOT NULL
                THEN ROUND(CAST(r_agg.deposit_avg AS REAL) / t_agg.price_avg * 100, 1)
                ELSE NULL
            END AS jeonse_ratio_pct,

            cs.nearest_station,
            cs.stops_to_gbd,
            cs.stops_to_cbd,
            cs.stops_to_ybd

        FROM apartments a

        LEFT JOIN (
            SELECT apartment_id, deal_ym,
                   AVG(price_avg) AS price_avg,
                   MIN(price_min) AS price_min,
                   MAX(price_max) AS price_max,
                   SUM(deal_count) AS deal_count
            FROM monthly_prices
            WHERE deal_type = 'trade'
            GROUP BY apartment_id, deal_ym
        ) t_agg ON t_agg.apartment_id = a.id
               AND t_agg.deal_ym = (
                   SELECT MAX(deal_ym) FROM monthly_prices
                   WHERE apartment_id = a.id AND deal_type = 'trade'
               )

        LEFT JOIN (
            SELECT apartment_id, deal_ym,
                   AVG(deposit_avg) AS deposit_avg
            FROM monthly_prices
            WHERE deal_type = 'rent'
            GROUP BY apartment_id, deal_ym
        ) r_agg ON r_agg.apartment_id = a.id
               AND r_agg.deal_ym = (
                   SELECT MAX(deal_ym) FROM monthly_prices
                   WHERE apartment_id = a.id AND deal_type = 'rent'
               )

        LEFT JOIN commute_stops cs ON cs.apartment_id = a.id;
    """)
    conn.commit()
```

Note: `DROP VIEW IF EXISTS` + `CREATE VIEW` (without `IF NOT EXISTS`) is used instead of `CREATE VIEW IF NOT EXISTS` because SQLite's `CREATE VIEW IF NOT EXISTS` does not update the view if it already exists with a different definition. `DROP` + `CREATE` inside `init_db()` is safe since the view has no data of its own.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| argparse for CLI | Typer with type hints | Typer 0.3+ (2020) | CLI code is 3x shorter; auto-help and shell completion |
| `encoding='utf-8'` for CSV | `encoding='utf-8-sig'` | Pandas long-standing feature | Required for Korean Excel compatibility; BOM signals UTF-8 to Excel |
| Manual JOIN for latest row | Correlated subquery or windowed GROUP BY | SQLite 3.25+ (2018) | Correct per-group latest selection without duplicates |
| Hard-coded CSV export script | `pd.read_sql()` on SQLite VIEW | Pandas 1.0+ | Analysis query changes only update the VIEW; no script changes needed |

**Deprecated/outdated:**

- `argparse` for pipeline CLI: functional but verbose; Typer is the project choice per REQUIREMENTS.md CLI-01.
- `encoding='utf-8'` in `to_csv()`: generates plain UTF-8 which Excel misreads on Korean Windows. Always use `utf-8-sig`.
- `CREATE VIEW IF NOT EXISTS` when VIEW definition may need updating: use `DROP VIEW IF EXISTS` + `CREATE VIEW` in `init_db()` to ensure definition stays current.

---

## Open Questions

1. **VIEW deduplication when monthly_prices has multiple exclu_use_ar bands**
   - What we know: `monthly_prices` stores one row per `(apartment_id, deal_type, deal_ym, exclu_use_ar)`. For a given apartment and latest month, there may be 2–5 rows (different unit sizes).
   - What's unclear: The requirement says "최신 시세" without specifying which size band. AVG across bands is the most defensible but may not reflect any single unit type.
   - Recommendation: Use pre-aggregated JOIN (`AVG(price_avg)`, `SUM(deal_count)`) as shown in Pattern 4 / create_views() example. Add a column comment in the VIEW or docstring explaining this. The planner can decide if a separate "per-size-band" view is needed for v2.

2. **`status` command display of subway/geocoding progress**
   - What we know: `collection_log` tracks `trade`, `rent`, `building` data types. Subway distances and geocoding are NOT tracked in `collection_log` (they use their own DB-level caching).
   - What's unclear: Should `status` also show geocoding and subway distance coverage percentages?
   - Recommendation: For v1, status shows only what `collection_log` tracks (trade/rent/building). Add a secondary count query: `SELECT COUNT(*) FROM apartments WHERE latitude IS NOT NULL` and `SELECT COUNT(DISTINCT apartment_id) FROM subway_distances` for supplementary coverage info. Keep simple.

3. **`collect --data-type subway` requires TMAP_APP_KEY**
   - What we know: `collect_all_subway_distances()` raises `RuntimeError` if `TMAP_APP_KEY` env var is not set.
   - What's unclear: How should the CLI surface this error to the user?
   - Recommendation: In the `collect` command, check `os.getenv("TMAP_APP_KEY")` before dispatching to subway collection; print a clear error message and `raise typer.Exit(1)` rather than letting the RuntimeError propagate.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `pytest tests/test_pipeline_phase4.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `app` object is importable from `pipeline.cli.main` | unit (import check) | `pytest tests/test_pipeline_phase4.py::test_cli_app_importable -x` | Wave 0 |
| CLI-01 | `typer.testing.CliRunner` invokes `collect --help` and exits 0 | unit | `pytest tests/test_pipeline_phase4.py::test_collect_help -x` | Wave 0 |
| CLI-01 | `export --help` exits 0 | unit | `pytest tests/test_pipeline_phase4.py::test_export_help -x` | Wave 0 |
| CLI-01 | `status` with empty DB prints "No data collected yet" | unit (in-memory DB) | `pytest tests/test_pipeline_phase4.py::test_status_empty -x` | Wave 0 |
| CLI-02 | `_resolve_regions("seoul")` returns only SEOUL_REGIONS keys | unit | `pytest tests/test_pipeline_phase4.py::test_resolve_regions_seoul -x` | Wave 0 |
| CLI-02 | `_resolve_regions("unknown")` raises SystemExit | unit | `pytest tests/test_pipeline_phase4.py::test_resolve_regions_invalid -x` | Wave 0 |
| CLI-03 | `export_to_csv()` writes utf-8-sig CSV with correct row count | unit (in-memory DB + tmp file) | `pytest tests/test_pipeline_phase4.py::test_export_utf8_sig -x` | Wave 0 |
| CLI-03 | Output CSV BOM is `b'\xef\xbb\xbf'` (UTF-8 BOM bytes) | unit | `pytest tests/test_pipeline_phase4.py::test_export_bom_present -x` | Wave 0 |
| CLI-04 | `create_views(conn)` succeeds on schema from `init_db()` | unit (in-memory DB) | `pytest tests/test_pipeline_phase4.py::test_create_views -x` | Wave 0 |
| CLI-04 | `SELECT * FROM apartment_analysis` returns 0 rows on empty DB (not error) | unit (in-memory DB) | `pytest tests/test_pipeline_phase4.py::test_apartment_analysis_empty -x` | Wave 0 |
| CLI-04 | VIEW with seeded data returns correct jeonse_ratio_pct | unit (in-memory DB with seed rows) | `pytest tests/test_pipeline_phase4.py::test_jeonse_ratio_calculation -x` | Wave 0 |
| CLI-04 | VIEW returns 1 row per apartment (no duplicates from size bands) | unit (in-memory DB with multi-band seed) | `pytest tests/test_pipeline_phase4.py::test_view_no_duplicates -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_pipeline_phase4.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_phase4.py` — all 12 tests above; use `CliRunner` from `typer.testing` for CLI tests; use `tmp_db` fixture (already in `conftest.py`) for VIEW and export tests
- [ ] `pipeline/cli/__init__.py` — package marker (empty file)
- [ ] `pipeline/cli/main.py` — stub with `app = typer.Typer()` and three `@app.command()` stubs; import-safe and callable with `--help`
- [ ] `pipeline/storage/schema.py` — add `create_views(conn)` function and call from `init_db()` (additive modification only)
- [ ] `typer` dependency: `pip install typer>=0.12.0` and add to `pyproject.toml` `[project.dependencies]`

*(conftest.py `tmp_db` fixture already exists — no gap)*

---

## Sources

### Primary (HIGH confidence)

- `typer.tiangolo.com/tutorial/commands/` — subcommand registration, `@app.command()`, `[project.scripts]` format
- `typer.tiangolo.com/tutorial/package/` — exact pyproject.toml entry point format confirmed: `pipeline = "pipeline.cli.main:app"`
- `pypi.org/project/typer/` — latest version 0.24.1 (2026-02-21), requires Python 3.10+, dependencies: click, rich, shellingham
- `pandas.pydata.org/docs/reference/api/pandas.read_sql.html` — `read_sql(sql, con)` with sqlite3 connection object
- `sqlite.org/windowfunctions.html` + `sqlite.org/lang_corefunc.html` — SQLite window function support (3.25+), COALESCE, NULLIF
- `pipeline/storage/schema.py` (local) — confirmed exact table schema: `monthly_prices`, `commute_stops`, `subway_distances`, `collection_log`
- `pipeline/config/regions.py` (local) — `PIPELINE_REGIONS`, `SEOUL_REGIONS`, `GYEONGGI_REGIONS` already defined
- `pipeline/collectors/trade_rent.py` (local) — `collect_all_regions()` is existing sync entry point; `asyncio.run()` pattern confirmed
- `pipeline/storage/repository.py` (local) — upsert patterns and commit ownership confirmed

### Secondary (MEDIUM confidence)

- `hyunbinseo.medium.com` — utf-8-sig BOM for Korean Excel CSV confirmed; pattern verified by pandas docs
- `tobywf.com/2017/08/unicode-csv-excel/` — BOM behavior in Excel confirmed with Python examples
- Multiple sources agree: `df.to_csv(path, encoding='utf-8-sig', index=False)` is the idiomatic pattern for Korean Excel compatibility

### Tertiary (LOW confidence)

- VIEW duplicate-row risk from multi-exclu_use_ar bands: inferred from schema design; not tested against production data. Planner should verify with a real DB sample.

---

## Metadata

**Confidence breakdown:**
- Standard stack (Typer, pandas): HIGH — official docs confirmed, version verified
- Architecture (CLI pattern, VIEW SQL): HIGH — based on official docs and existing codebase patterns
- VIEW SQL correctness for multi-band deduplication: MEDIUM — pattern is correct per SQLite docs but needs integration test with real data
- Pitfalls: HIGH — derived from existing codebase decisions (asyncio.run pattern, existing schema) and confirmed pandas behavior

**Research date:** 2026-03-18T05:32:44Z
**Valid until:** 2026-04-18 (Typer and pandas APIs stable; SQLite VIEW semantics stable)
