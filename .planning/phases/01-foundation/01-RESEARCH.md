# Phase 1: Foundation - Research

**Researched:** 2026-03-17T06:21:59Z
**Domain:** SQLite schema initialization, MOLIT API client, LAWD_CD region mapping, idempotency log
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | SQLite DB 초기화 — apartments, monthly_prices, building_info, subway_distances, commute_stops, collection_log 6개 테이블 + 인덱스 생성 | `sqlite3` stdlib `CREATE TABLE IF NOT EXISTS` pattern; `executemany` + WAL pragma for performance; index strategy documented below |
| FOUND-02 | MOLIT API 기반 클라이언트 — serviceKey URL-embed 패턴, HTTP-200 에러 body 파싱, 페이지네이션 (기존 realestate_csv.py 로직 계승) | `realestate_csv.py` fetch_trades() is the verified pattern; serviceKey double-encoding fix confirmed at line 362; HTTP-200 error body parsing pattern documented |
| FOUND-03 | 지역 설정 — 서울 전체 자치구, 성남시 분당구, 과천시, 하남시(위례), 안양시 동안구(인덕원) LAWD_CD 매핑 | All 5 LAWD_CDs verified in existing SIGUNGU_MAP; region_codes.py in app/data/ has the full confirmed mapping |
| FOUND-04 | collection_log 멱등성 — 동일 (lawd_cd × deal_ym × data_type) 재수집 방지 | SQLite `UNIQUE` constraint on `(lawd_cd, deal_ym, data_type)` + `INSERT OR IGNORE` pattern; no external library needed |
</phase_requirements>

---

## Summary

Phase 1 establishes the skeletal infrastructure that every subsequent phase depends on. It has four deliverables: the SQLite schema with 6 tables and indexes, an async MOLIT API client ported from the validated `realestate_csv.py`, a hardcoded LAWD_CD mapping for the 5 target regions, and a `collection_log` table with a UNIQUE constraint that implements idempotency.

All four deliverables are low-risk. The MOLIT API client pattern is already proven in `realestate_csv.py` and just needs to be moved into the `pipeline/` package. The LAWD_CD codes are already present and verified in `realestate_csv.py`'s SIGUNGU_MAP and in `app/data/region_codes.py`. The SQLite schema uses only stdlib `sqlite3` — no ORM, no migration tool. The idempotency pattern is a standard SQLite UNIQUE constraint.

The highest-risk item is the serviceKey URL encoding — getting it wrong causes silent 401 failures that look like registration problems. The fix is already in the codebase and must be preserved exactly. The second risk is HTTP-200 error bodies from the MOLIT API; these must be detected by parsing the `resultCode` field, not by checking the HTTP status code.

**Primary recommendation:** Port `fetch_trades()` from `realestate_csv.py` verbatim into `pipeline/clients/molit.py`, add resultCode body-error detection, then build the schema and region config around it. Do not refactor the serviceKey encoding pattern.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | All 6 tables, indexes, collection_log idempotency | Zero dependency; pandas/Streamlit compatible; PROJECT.md constraint |
| httpx | >=0.27.0 | Async HTTP calls to MOLIT API | Already in requirements.txt; used in realestate_csv.py; supports async + sync |
| xml.etree.ElementTree | stdlib | Parse MOLIT XML responses | Already used; MOLIT XML is flat `<item>` lists — no namespace complexity |
| python-dotenv | >=1.0.0 | Load MOLIT_API_KEY from .env | Already in requirements.txt |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru | >=0.7.2 | Structured logging for API errors, pagination state | Replace `print(..., file=sys.stderr)` in ported code |
| pathlib | stdlib | DB file path construction | Use `Path` instead of raw string concatenation |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 raw | SQLAlchemy | ORM overhead unnecessary; no HTTP server lifecycle; PROJECT.md constraint says sqlite3 |
| stdlib ET | lxml | MOLIT XML is trivially flat; lxml adds C build dependency with zero benefit |
| httpx | aiohttp | httpx already in codebase; aiohttp lacks sync API; no benefit to mixing |

**Installation:**

No new packages required for Phase 1. All dependencies are already in `requirements.txt`:

```bash
# Verify existing deps cover Phase 1
pip install httpx>=0.27.0 python-dotenv>=1.0.0 loguru>=0.7.2
# sqlite3 and xml.etree.ElementTree are stdlib
```

---

## Architecture Patterns

### Recommended Project Structure

The pipeline must live in a `pipeline/` package **completely separate** from `app/` (per PROJECT.md constraint: "pipeline/ 패키지를 app/과 완전 분리").

```
pipeline/
├── __init__.py
├── storage/
│   ├── __init__.py
│   └── schema.py          # init_db() — creates all 6 tables + indexes
├── clients/
│   ├── __init__.py
│   └── molit.py           # MolitClient — async HTTP, pagination, resultCode check
├── config/
│   ├── __init__.py
│   └── regions.py         # PIPELINE_REGIONS dict — 5 target LAWD_CDs
└── utils/
    ├── __init__.py
    └── idempotency.py     # is_collected(), mark_collected() helpers
```

The success criterion `python -c "from pipeline.storage.schema import init_db; init_db()"` dictates the exact import path. Use `pipeline.storage.schema` as the module path.

### Pattern 1: SQLite Schema Initialization

**What:** `init_db(db_path)` function that creates all 6 tables with `CREATE TABLE IF NOT EXISTS` and associated indexes, then sets performance PRAGMAs. Safe to call multiple times (idempotent by design).

**When to use:** Called once at pipeline startup, before any collection.

```python
# Source: sqlite3 stdlib + project research
import sqlite3
from pathlib import Path

DB_PATH = Path("realestate.db")

def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            apt_nm TEXT NOT NULL,
            umd_nm TEXT,
            jibun TEXT,
            road_nm TEXT,
            build_year INTEGER,
            total_households INTEGER,
            floor_area_ratio REAL,
            building_coverage_ratio REAL,
            total_parking INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lawd_cd, apt_nm, umd_nm)
        );

        CREATE TABLE IF NOT EXISTS monthly_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            deal_type TEXT NOT NULL CHECK(deal_type IN ('trade','rent')),
            deal_ym TEXT NOT NULL,
            exclu_use_ar REAL,
            price_min INTEGER,
            price_max INTEGER,
            price_avg REAL,
            deal_count INTEGER,
            deposit_min INTEGER,
            deposit_max INTEGER,
            deposit_avg REAL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS building_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            build_year INTEGER,
            total_households INTEGER,
            floor_area_ratio REAL,
            building_coverage_ratio REAL,
            total_parking INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id)
        );

        CREATE TABLE IF NOT EXISTS subway_distances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            station_name TEXT NOT NULL,
            line_name TEXT,
            walk_distance_m INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id, station_name)
        );

        CREATE TABLE IF NOT EXISTS commute_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartments(id),
            nearest_station TEXT NOT NULL,
            stops_to_gbd INTEGER,
            stops_to_cbd INTEGER,
            stops_to_ybd INTEGER,
            calculated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(apartment_id)
        );

        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            deal_ym TEXT NOT NULL,
            data_type TEXT NOT NULL,
            collected_at TEXT DEFAULT (datetime('now')),
            record_count INTEGER DEFAULT 0,
            UNIQUE(lawd_cd, deal_ym, data_type)
        );

        CREATE INDEX IF NOT EXISTS idx_apartments_lawd ON apartments(lawd_cd);
        CREATE INDEX IF NOT EXISTS idx_monthly_prices_apt ON monthly_prices(apartment_id, deal_ym);
        CREATE INDEX IF NOT EXISTS idx_monthly_prices_type ON monthly_prices(deal_type, deal_ym);
        CREATE INDEX IF NOT EXISTS idx_collection_log_key ON collection_log(lawd_cd, deal_ym, data_type);
    """)
    conn.commit()
    return conn
```

### Pattern 2: MOLIT API Client with serviceKey URL Embedding

**What:** Async `MolitClient` class that fetches all pages for a given `(lawd_cd, deal_ym, deal_type)`. Embeds serviceKey directly in the URL string — never via `params={}` dict. Checks for HTTP-200 error bodies.

**When to use:** Phase 2 collection calls this. Phase 1 only builds the client; it does not run collection.

```python
# Source: realestate_csv.py fetch_trades() — validated pattern
from urllib.parse import unquote, quote
import xml.etree.ElementTree as ET
import httpx

ENDPOINTS = {
    "trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "rent":  "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}

class MolitClient:
    def __init__(self, raw_api_key: str):
        # Pre-encode: decode any existing encoding, then re-encode safe
        # CRITICAL: do NOT use params={} for serviceKey — httpx double-encodes it
        self.safe_key = quote(unquote(raw_api_key), safe='')

    async def fetch_all(
        self,
        client: httpx.AsyncClient,
        lawd_cd: str,
        deal_ym: str,
        deal_type: str = "trade",
        page_size: int = 1000,
    ) -> list[dict]:
        base_url = ENDPOINTS[deal_type]
        all_items = []
        page = 1

        while True:
            # serviceKey embedded in URL string — do NOT move to params={}
            url = (
                f"{base_url}?serviceKey={self.safe_key}"
                f"&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ym}"
                f"&numOfRows={page_size}&pageNo={page}"
            )
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()

            # MOLIT returns HTTP 200 even for errors — check resultCode
            ok, err = _check_result_code(resp.text)
            if not ok:
                raise RuntimeError(f"MOLIT API error: {err}")

            items = _parse_items(resp.text)
            all_items.extend(items)
            if len(items) < page_size:
                break
            page += 1

        return all_items


def _check_result_code(xml_text: str) -> tuple[bool, str]:
    """HTTP 200 with error body detection — MOLIT API quirk"""
    try:
        root = ET.fromstring(xml_text)
        code = root.findtext(".//resultCode") or ""
        if code and code not in ("00", "0000", "000"):
            msg = root.findtext(".//resultMsg") or "Unknown MOLIT error"
            return False, f"Code {code}: {msg}"
        return True, ""
    except ET.ParseError:
        return False, "XML parse failure"


def _parse_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.findall(".//item")
    ]
```

### Pattern 3: Idempotency Check via collection_log

**What:** Before fetching `(lawd_cd, deal_ym, data_type)`, check if it already exists in `collection_log`. After successful fetch, insert with `INSERT OR IGNORE` — the UNIQUE constraint guarantees no double-counting.

**When to use:** Every collection call in Phase 2 wraps itself with these helpers.

```python
# Source: standard sqlite3 pattern for idempotency
import sqlite3

def is_collected(conn: sqlite3.Connection, lawd_cd: str, deal_ym: str, data_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM collection_log WHERE lawd_cd=? AND deal_ym=? AND data_type=?",
        (lawd_cd, deal_ym, data_type)
    ).fetchone()
    return row is not None


def mark_collected(conn: sqlite3.Connection, lawd_cd: str, deal_ym: str, data_type: str, record_count: int = 0):
    conn.execute(
        "INSERT OR IGNORE INTO collection_log (lawd_cd, deal_ym, data_type, record_count) VALUES (?,?,?,?)",
        (lawd_cd, deal_ym, data_type, record_count)
    )
    conn.commit()
```

### Pattern 4: Target Region LAWD_CD Mapping

**What:** A module-level dict of the 5 pipeline target regions with their verified 5-digit LAWD_CDs.

**When to use:** Imported by the orchestrator in Phase 4 CLI; used in Phase 2 collection loops.

```python
# Source: realestate_csv.py SIGUNGU_MAP + app/data/region_codes.py (both verified)
# All codes are 5-digit (시군구 level) as required by MOLIT RTMSOBJSvc endpoints

PIPELINE_REGIONS = {
    # 서울 전체 25개 자치구
    "강남구":    "11680",
    "강동구":    "11740",
    "강북구":    "11305",
    "강서구":    "11500",
    "관악구":    "11620",
    "광진구":    "11215",
    "구로구":    "11530",
    "금천구":    "11545",
    "노원구":    "11350",
    "도봉구":    "11320",
    "동대문구":  "11230",
    "동작구":    "11590",
    "마포구":    "11440",
    "서대문구":  "11410",
    "서초구":    "11650",
    "성동구":    "11200",
    "성북구":    "11290",
    "송파구":    "11710",
    "양천구":    "11470",
    "영등포구":  "11560",
    "용산구":    "11170",
    "은평구":    "11380",
    "종로구":    "11110",
    "중구":      "11140",
    "중랑구":    "11260",
    # 경기도 4개 권역
    "성남시 분당구":    "41175",  # 위례 일부 포함 지역
    "과천시":          "41390",
    "하남시":          "41550",  # 위례신도시 행정구역
    "안양시 동안구":   "41220",  # 인덕원 행정구역
}

# Convenience: Seoul only
SEOUL_REGIONS = {k: v for k, v in PIPELINE_REGIONS.items() if v.startswith("11")}
GYEONGGI_REGIONS = {k: v for k, v in PIPELINE_REGIONS.items() if v.startswith("41")}
```

### Anti-Patterns to Avoid

- **serviceKey via params={}:** httpx double-encodes it. Looks like a registration error. Always embed in URL string manually.
- **Checking only HTTP status code:** MOLIT returns HTTP 200 for all errors. Always parse `resultCode` from the XML body.
- **Single-page fetch without pagination:** Districts like 강남구 can exceed 1,000 rows/month. Always loop until `len(items) < page_size`.
- **SQLAlchemy or any ORM:** Zero benefit for a batch CLI pipeline. Raw sqlite3 with `executemany` is simpler and faster.
- **Using Korean field names on MOLIT XML:** XML tags are camelCase English (`aptNm`, `dealAmount`, `excluUseAr`). Korean keys always return empty.
- **Wrong-length LAWD_CD:** Always 5 digits. `assert len(lawd_cd) == 5 and lawd_cd.isdigit()` before every API call.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP | Custom socket client | httpx.AsyncClient | Already in codebase; handles timeouts, SSL, connection pooling |
| XML parsing | String splitting / regex | xml.etree.ElementTree | MOLIT XML is flat — ET.findall(".//item") covers 100% of cases |
| Idempotency | In-memory set | SQLite UNIQUE constraint + INSERT OR IGNORE | Persists across restarts; O(1) lookup via index; zero code |
| LAWD_CD lookup | Fresh geocoding call | Hardcoded PIPELINE_REGIONS dict | Codes don't change; API call for a static mapping is wasteful |
| URL encoding | Custom encoder | `urllib.parse.quote(unquote(key), safe='')` | Already validated in realestate_csv.py line 362; don't reinvent |

**Key insight:** Phase 1 has no novel algorithmic problems. Every pattern already exists in the codebase — the work is restructuring, not invention.

---

## Common Pitfalls

### Pitfall 1: serviceKey Double-Encoding (401 AUTH ERRORS)

**What goes wrong:** Passing `serviceKey` via `params={"serviceKey": key}` causes httpx to double-encode it. The server receives a malformed key and returns HTTP 401 with body `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`.

**Why it happens:** data.go.kr issues keys with `+` and `/` characters. These are URL-unsafe. httpx re-encodes them when building the query string.

**How to avoid:** Embed the pre-encoded key directly in the URL string:
```python
safe_key = quote(unquote(raw_key), safe='')
url = f"{base_url}?serviceKey={safe_key}&LAWD_CD={lawd_cd}..."
```

**Warning signs:** HTTP 401; body contains `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`; key is valid on data.go.kr portal.

### Pitfall 2: HTTP 200 with Error Body (SILENT DATA LOSS)

**What goes wrong:** `resp.raise_for_status()` succeeds. Code proceeds to parse items. `root.findall(".//item")` returns `[]`. No exception is raised. The collection_log marks the month as collected with 0 records. Real data is lost.

**Why it happens:** Korean public data portal APIs always return HTTP 200, encoding errors in XML body `<resultCode>`.

**How to avoid:** Parse `resultCode` before processing items. Raise on non-zero codes. Retry on code 22 (rate limit).

**Warning signs:** Consistently 0 items for districts that should have data; XML body starts with `<OpenAPI_ServiceResponse>` instead of `<response>`.

### Pitfall 3: Missing Pagination (SILENT DATA TRUNCATION)

**What goes wrong:** For busy months in 강남구, 서초구, 송파구, the API returns exactly 1,000 rows without any error. Code that fetches a single page silently drops transactions beyond row 1,000.

**How to avoid:** Always loop until `len(items) < page_size`. This is already implemented in `realestate_csv.py fetch_trades()` — copy the loop exactly.

**Warning signs:** Any single fetch returns exactly 1,000 rows.

### Pitfall 4: Wrong LAWD_CD Digit Count (EMPTY RESULTS)

**What goes wrong:** Passing a 2-digit sido code (`"11"`) or 10-digit 법정동 code instead of a 5-digit 시군구 code returns HTTP 200 with 0 items and no error.

**How to avoid:** Validate before each call: `assert len(lawd_cd) == 5 and lawd_cd.isdigit()`.

**Warning signs:** API returns 0 items for regions that definitely have transactions.

### Pitfall 5: MOLIT Data Availability Lag (FALSE EMPTY CURRENT MONTH)

**What goes wrong:** Querying the current month returns 0 or very few results — not because the area is quiet but because local governments have not yet submitted the data (1-2 month lag).

**How to avoid:** Set default end month to `previous month` in the date range generator:
```python
from datetime import datetime, timedelta
end_ym = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
```

**Warning signs:** Current month returns 0; previous month returns hundreds of results.

---

## Code Examples

### Schema Init (complete callable)

```python
# Source: sqlite3 stdlib docs + project research
# Call: python -c "from pipeline.storage.schema import init_db; init_db()"
import sqlite3
from pathlib import Path

def init_db(db_path: str | Path = "realestate.db") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # ... (full executescript as shown in Pattern 1 above)
    conn.commit()
    return conn
```

### serviceKey Encoding (from realestate_csv.py line 362)

```python
from urllib.parse import unquote, quote

# Raw key from os.getenv("MOLIT_API_KEY") may be pre-encoded or plain text
raw_key = os.getenv("MOLIT_API_KEY", "")
safe_key = quote(unquote(raw_key), safe='')
# safe_key is now safe to embed directly in URL string
```

### MOLIT XML Field Reference

```python
# Source: realestate_csv.py normalize_trade_row() — confirmed field names
# Trade (매매) endpoint fields:
TRADE_FIELDS = {
    "aptNm":      "아파트명",
    "dealAmount": "거래금액(만원) — contains commas: '55,000', strip before int()",
    "excluUseAr": "전용면적(㎡) — float",
    "floor":      "층",
    "buildYear":  "건축년도",
    "dealYear":   "계약년",
    "dealMonth":  "계약월",
    "dealDay":    "계약일",
    "umdNm":      "법정동명",
    "jibun":      "지번",
    "roadNm":     "도로명",
    "aptDong":    "동",
    "dealingGbn": "거래구분",
}

# Rent (전월세) adds:
RENT_EXTRA_FIELDS = {
    "deposit":      "보증금(만원)",
    "monthlyRent":  "월세금(만원)",
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| CSV output (realestate_csv.py) | SQLite backend (pipeline/) | pandas/dashboard/export all work directly |
| Address-based input | LAWD_CD district scan | No user input needed; full district coverage |
| No idempotency | collection_log UNIQUE constraint | Safe reruns; progress preserved across interruptions |
| argparse single-command | Typer subcommands (Phase 4) | `collect`, `export`, `status` as separate commands |

**Not changed from existing code:**
- serviceKey URL encoding pattern (preserve exactly)
- Pagination loop logic (preserve exactly)
- XML field name mapping (camelCase English)
- httpx.AsyncClient usage pattern

---

## Open Questions

1. **DB file location**
   - What we know: Must be accessible by CLI and by pandas analysis scripts
   - What's unclear: Should it default to `./realestate.db` in CWD, or a fixed path like `~/.pipeline/realestate.db`?
   - Recommendation: Default to `./realestate.db`; make it a CLI option `--db-path` in Phase 4

2. **pipeline/ package installation**
   - What we know: `pyproject.toml` currently builds `app/` package only
   - What's unclear: Should `pipeline/` be added to `pyproject.toml` or invoked directly?
   - Recommendation: Add `pipeline/` as a second package in `pyproject.toml` under `[tool.setuptools.packages.find]`; enables `from pipeline.storage.schema import init_db` to work from any directory

3. **하남시 = 위례 scope**
   - What we know: LAWD_CD `41550` is 하남시, which includes the 위례신도시 new town
   - What's unclear: Does the requirement mean all of 하남시, or only the 위례 sub-district?
   - Recommendation: Use `41550` (all of 하남시) in Phase 1 LAWD_CD mapping; the planner can refine if 위례-only is needed

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_pipeline_foundation.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | `init_db()` creates 6 tables + indexes; safe to call twice | unit | `pytest tests/test_pipeline_foundation.py::test_init_db_creates_tables -x` | Wave 0 |
| FOUND-01 | All 6 table names present after init | unit | `pytest tests/test_pipeline_foundation.py::test_table_names -x` | Wave 0 |
| FOUND-02 | MolitClient builds correct URL with serviceKey embedded (not double-encoded) | unit | `pytest tests/test_pipeline_foundation.py::test_molit_url_encoding -x` | Wave 0 |
| FOUND-02 | `_check_result_code` returns False for non-00 resultCode | unit | `pytest tests/test_pipeline_foundation.py::test_result_code_detection -x` | Wave 0 |
| FOUND-02 | Pagination loop stops when items < page_size | unit (mock) | `pytest tests/test_pipeline_foundation.py::test_pagination_stops -x` | Wave 0 |
| FOUND-03 | All 29 LAWD_CDs in PIPELINE_REGIONS are 5 digits | unit | `pytest tests/test_pipeline_foundation.py::test_lawd_cd_format -x` | Wave 0 |
| FOUND-03 | 5 required region names present (분당구, 과천시, 하남시, 동안구 + all Seoul) | unit | `pytest tests/test_pipeline_foundation.py::test_required_regions_present -x` | Wave 0 |
| FOUND-04 | `is_collected()` returns False before mark, True after mark | unit | `pytest tests/test_pipeline_foundation.py::test_idempotency_check -x` | Wave 0 |
| FOUND-04 | Second `mark_collected()` call with same key does not raise | unit | `pytest tests/test_pipeline_foundation.py::test_idempotency_no_duplicate -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_pipeline_foundation.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_foundation.py` — covers all FOUND-01 through FOUND-04 tests listed above
- [ ] `tests/conftest.py` — shared `tmp_db` fixture returning an in-memory or temp-file sqlite3 connection

*(No framework install gap — pytest already configured in pyproject.toml)*

---

## Sources

### Primary (HIGH confidence)

- `realestate_csv.py` — serviceKey encoding (line 362), pagination loop, XML field names, address→LAWD_CD mapping
- `app/data/region_codes.py` — verified LAWD_CD codes for all 5 target regions
- `pyproject.toml` — pytest configuration, existing dependency versions
- `.planning/research/STACK.md` — prior stack research (sqlite3, httpx, no ORM)
- `.planning/research/PITFALLS.md` — MOLIT API pitfalls (HIGH confidence, codebase-verified)
- `.planning/codebase/STRUCTURE.md` — existing project layout, where to add pipeline/

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` — pipeline feature requirements
- `STATE.md` decisions: SQLite, serviceKey URL-embed, pipeline/ separation, BFS networkx

### Tertiary (LOW confidence)

- None for Phase 1 scope — all Phase 1 patterns are directly verifiable from existing codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in codebase; no new dependencies for Phase 1
- Architecture: HIGH — module paths dictated by success criteria import path; patterns verified in existing code
- LAWD_CD codes: HIGH — verified in two independent files (realestate_csv.py SIGUNGU_MAP + app/data/region_codes.py GYEONGGI_SIGUNGU)
- Pitfalls: HIGH — all Phase 1 pitfalls are directly confirmed in realestate_csv.py source code
- Schema design: MEDIUM — column names are project decisions not yet in code; index strategy is standard SQLite practice

**Research date:** 2026-03-17T06:21:59Z
**Valid until:** 2026-04-17 (stable SQLite + MOLIT API patterns; LAWD_CD codes are permanent)
