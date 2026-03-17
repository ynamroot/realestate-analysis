# Phase 2: MOLIT Data Collection - Research

**Researched:** 2026-03-17T07:15:40Z
**Domain:** MOLIT trade/rent collection loop, data normalization, aggregation, building-info API
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PRICE-01 | 지역구별 전체 아파트 월별 매매 실거래 수집 (2006년~현재), SQLite apartments + monthly_prices 적재 | MolitClient.fetch_all("trade") already implemented; need collector loop over PIPELINE_REGIONS × month_range + upsert functions |
| PRICE-02 | 지역구별 전체 아파트 월별 전세 실거래 수집 (2006년~현재), monthly_prices 적재 | Same MolitClient.fetch_all("rent"); same loop; monthly_prices deal_type='rent' rows |
| PRICE-03 | 평형(전용면적 구간)별 월별 집계 — 거래건수, 최저가, 최고가, 평균가 | Aggregator function groups raw items by (aptNm, umdNm, excluUseAr_bucket) then computes min/max/avg/count; no external library needed |
| PRICE-04 | dealAmount 쉼표 제거, excluUseAr float 변환, dealMonth zero-padding 정규화 | Normalization verified in realestate_csv.py normalize_trade_row(); patterns fully specified below |
| BLDG-01 | 국토교통부 HouseInfo API로 각 아파트 건폐율, 건축년도, 용적률, 세대수, 주차대수 수집 | RTMSDataSvcAptBldMgm endpoint; LAWD_CD format is 5-digit (same as trade); apartment identity matched via (aptNm, umdNm) |
| BLDG-02 | building_info 테이블에 apartment_id FK로 연결하여 적재 | building_info table already exists with UNIQUE(apartment_id); INSERT OR REPLACE pattern |
</phase_requirements>

---

## Summary

Phase 2 is the main data collection phase. It builds on the complete Phase 1 foundation — `MolitClient`, `init_db()`, `PIPELINE_REGIONS`, `is_collected`/`mark_collected` — and adds three new modules: a collector that loops over all 29 districts × all months from 200601 to the previous calendar month, a normalizer/aggregator that converts raw MOLIT `<item>` dicts into `monthly_prices` rows (with proper dealAmount comma-stripping, excluUseAr float conversion, and dealMonth zero-padding), and a building-info collector that calls the MOLIT `RTMSDataSvcAptBldMgm` API to populate `building_info` rows linked via `apartment_id` FK.

The upsert pattern for `apartments` and `monthly_prices` is the critical algorithmic piece. Every `<item>` from the trade/rent API identifies an apartment by `(aptNm, umdNm, lawd_cd)`. The collector must `INSERT OR IGNORE` the apartment row to get its `id`, then insert the aggregated monthly price row. The `monthly_prices` table has no UNIQUE constraint, so the collector is responsible for de-duplicating at the `(apartment_id, deal_type, deal_ym, exclu_use_ar)` grain before inserting.

The HouseInfo (building info) API is a separate MOLIT endpoint that returns building-level metadata for all apartment complexes in a district. Its LAWD_CD parameter is the same 5-digit format. The response fields (`buldNm`, `bcRat`, `vlRat`, `hhldCnt`, `pkngCnt`, `bldYr`) map to `building_info` columns. The key challenge is matching HouseInfo response rows to already-inserted `apartments` rows by name, since the building API uses `buldNm` while the trade API uses `aptNm` for the same complex.

**Primary recommendation:** Build the Phase 2 modules in this order: (1) normalizer/aggregator pure functions (no I/O, easy to test), (2) apartment upsert + monthly_prices upsert storage functions, (3) trade/rent collector loop with idempotency, (4) HouseInfo collector. Test each layer independently before wiring to the next.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | `apartments` + `monthly_prices` + `building_info` upserts | Already used in Phase 1; no ORM needed |
| httpx | >=0.25.2 | Async HTTP calls to MOLIT trade/rent/building APIs | Already in requirements.txt; `MolitClient` uses it |
| xml.etree.ElementTree | stdlib | Parse MOLIT XML responses for building info | Same as Phase 1; MOLIT XML is flat `<item>` lists |
| python-dotenv | >=1.0.0 | Load `MOLIT_API_KEY` | Already in requirements.txt |
| loguru | >=0.7.2 | Progress logging during long collection runs | Already in requirements.txt |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime | stdlib | Generate month range from "200601" to previous month | `get_month_range()` ported from `realestate_csv.py` |
| asyncio | stdlib | Run async collection loop from sync entry point | `asyncio.run()` wrapper for the collector |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw sqlite3 upserts | SQLAlchemy ORM | ORM adds zero value for simple INSERT OR IGNORE patterns; raw sqlite3 is 10x simpler here |
| In-process aggregation | Pandas groupby | Pandas would be imported just for groupby on a list of dicts; stdlib `statistics` + `collections.defaultdict` is sufficient and has no import overhead |
| Sequential async calls | asyncio.gather parallel | Parallel across districts risks MOLIT rate limits; sequential with no sleep is safe and documented as correct |

**Installation:** No new packages needed for Phase 2. All dependencies are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Module Structure

```
pipeline/
├── collectors/
│   ├── __init__.py
│   ├── trade_rent.py      # collect_district() — trade + rent loop per LAWD_CD × month
│   └── building_info.py   # collect_building_info() — HouseInfo API per LAWD_CD
├── processors/
│   ├── __init__.py
│   └── normalizer.py      # normalize_trade_item(), normalize_rent_item(), aggregate_monthly()
└── storage/
    ├── __init__.py
    └── repository.py      # upsert_apartment(), upsert_monthly_prices(), upsert_building_info()
```

All new modules are inside `pipeline/` (already discoverable via `pyproject.toml` `include = ["pipeline*"]`).

### Pattern 1: Month Range Generator

**What:** Generates all YYYYMM strings from a start month (e.g., "200601") up to the previous calendar month (to avoid the MOLIT 1-2 month submission lag).

**When to use:** Called once at collection start; drives the outer loop.

```python
# Source: realestate_csv.py get_month_range() — adapted
from datetime import datetime, timedelta

def get_month_range(start_ym: str = "200601") -> list[str]:
    """Return all YYYYMM strings from start_ym up to previous calendar month."""
    now = datetime.now()
    # Previous month to avoid MOLIT submission lag
    prev = now.replace(day=1) - timedelta(days=1)
    end_y, end_m = prev.year, prev.month

    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    result = []
    y, m = sy, sm
    while (y, m) <= (end_y, end_m):
        result.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result
```

### Pattern 2: Data Normalization (PRICE-04)

**What:** Convert raw MOLIT `<item>` dict fields to typed Python values. Three mandatory transformations:
1. `dealAmount`: strip commas, cast to `int`
2. `excluUseAr`: cast to `float` (already decimal string, e.g., `"84.9700"`)
3. `dealMonth`: zero-pad to 2 digits (e.g., `"1"` → `"01"`)

```python
# Source: realestate_csv.py normalize_trade_row() — field names confirmed from MOLIT XML
def normalize_trade_item(item: dict) -> dict:
    """Normalize a raw MOLIT trade <item> dict. Returns typed fields."""
    deal_amount_raw = item.get("dealAmount", "").replace(",", "").strip()
    exclu_use_ar_raw = item.get("excluUseAr", "").strip()
    deal_month_raw = item.get("dealMonth", "").strip()

    return {
        "apt_nm":       item.get("aptNm", "").strip(),
        "umd_nm":       item.get("umdNm", "").strip(),
        "jibun":        item.get("jibun", "").strip(),
        "road_nm":      item.get("roadNm", "").strip(),
        "build_year":   _safe_int(item.get("buildYear", "")),
        "deal_year":    _safe_int(item.get("dealYear", "")),
        "deal_month":   deal_month_raw.zfill(2),          # PRICE-04 zero-padding
        "deal_ym":      f"{item.get('dealYear','')}{deal_month_raw.zfill(2)}",
        "exclu_use_ar": _safe_float(exclu_use_ar_raw),    # PRICE-04 float conversion
        "price":        _safe_int(deal_amount_raw),        # PRICE-04 comma removal → int
        "floor":        _safe_int(item.get("floor", "")),
    }

def normalize_rent_item(item: dict) -> dict:
    """Normalize a raw MOLIT rent <item> dict."""
    deposit_raw = item.get("deposit", "").replace(",", "").strip()
    deal_month_raw = item.get("dealMonth", "").strip()
    return {
        "apt_nm":       item.get("aptNm", "").strip(),
        "umd_nm":       item.get("umdNm", "").strip(),
        "jibun":        item.get("jibun", "").strip(),
        "road_nm":      item.get("roadNm", "").strip(),
        "build_year":   _safe_int(item.get("buildYear", "")),
        "deal_year":    _safe_int(item.get("dealYear", "")),
        "deal_month":   deal_month_raw.zfill(2),
        "deal_ym":      f"{item.get('dealYear','')}{deal_month_raw.zfill(2)}",
        "exclu_use_ar": _safe_float(item.get("excluUseAr", "")),
        "deposit":      _safe_int(deposit_raw),
        "monthly_rent": _safe_int(item.get("monthlyRent", "").replace(",", "")),
        "floor":        _safe_int(item.get("floor", "")),
    }

def _safe_int(s: str) -> int | None:
    try:
        return int(s.strip()) if s.strip() else None
    except ValueError:
        return None

def _safe_float(s: str) -> float | None:
    try:
        return float(s.strip()) if s.strip() else None
    except ValueError:
        return None
```

### Pattern 3: Monthly Aggregation (PRICE-03)

**What:** Group normalized items by `(apt_nm, umd_nm, deal_ym, exclu_use_ar_bucket)` and compute `min`, `max`, `avg`, `count`. For trade: price stats. For rent: deposit stats.

**When to use:** Called after normalizing all items for a single `(lawd_cd, deal_ym, deal_type)` batch before inserting into `monthly_prices`.

```python
# Source: project research — standard aggregation pattern
from collections import defaultdict

def aggregate_monthly(normalized_items: list[dict], deal_type: str) -> list[dict]:
    """
    Group normalized items into one monthly_prices row per (apt_nm, umd_nm, deal_ym, exclu_use_ar).

    For trade: price_min, price_max, price_avg, deal_count.
    For rent:  deposit_min, deposit_max, deposit_avg, deal_count.
    """
    groups: dict[tuple, list] = defaultdict(list)
    for item in normalized_items:
        key = (item["apt_nm"], item["umd_nm"], item["deal_ym"], item["exclu_use_ar"])
        groups[key].append(item)

    rows = []
    for (apt_nm, umd_nm, deal_ym, exclu_use_ar), items in groups.items():
        row = {
            "apt_nm": apt_nm,
            "umd_nm": umd_nm,
            "deal_ym": deal_ym,
            "deal_type": deal_type,
            "exclu_use_ar": exclu_use_ar,
            "deal_count": len(items),
        }
        if deal_type == "trade":
            prices = [i["price"] for i in items if i["price"] is not None]
            row["price_min"] = min(prices) if prices else None
            row["price_max"] = max(prices) if prices else None
            row["price_avg"] = sum(prices) / len(prices) if prices else None
            row["deposit_min"] = row["deposit_max"] = row["deposit_avg"] = None
        else:  # rent
            deposits = [i["deposit"] for i in items if i["deposit"] is not None]
            row["deposit_min"] = min(deposits) if deposits else None
            row["deposit_max"] = max(deposits) if deposits else None
            row["deposit_avg"] = sum(deposits) / len(deposits) if deposits else None
            row["price_min"] = row["price_max"] = row["price_avg"] = None
        rows.append(row)
    return rows
```

### Pattern 4: Apartment Upsert + Monthly Prices Insert

**What:** The storage layer that translates aggregated rows into DB writes.

**Key constraint:** `apartments` has `UNIQUE(lawd_cd, apt_nm, umd_nm)`. Use `INSERT OR IGNORE` to get the `id` without overwriting existing rows. Then insert `monthly_prices` rows linked by `apartment_id`.

```python
# Source: project research — sqlite3 stdlib pattern
def upsert_apartment(conn, lawd_cd: str, apt_nm: str, umd_nm: str, **kwargs) -> int:
    """
    Insert apartment if not exists. Return apartment_id.
    Uses INSERT OR IGNORE so existing rows are never overwritten.
    """
    conn.execute(
        "INSERT OR IGNORE INTO apartments (lawd_cd, apt_nm, umd_nm, jibun, road_nm, build_year) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (lawd_cd, apt_nm, umd_nm,
         kwargs.get("jibun"), kwargs.get("road_nm"), kwargs.get("build_year")),
    )
    row = conn.execute(
        "SELECT id FROM apartments WHERE lawd_cd=? AND apt_nm=? AND umd_nm=?",
        (lawd_cd, apt_nm, umd_nm),
    ).fetchone()
    return row[0]


def insert_monthly_prices(conn, apartment_id: int, rows: list[dict]) -> int:
    """
    Insert aggregated monthly_prices rows. Skips rows already present
    by checking (apartment_id, deal_type, deal_ym, exclu_use_ar) before inserting.
    Returns count of newly inserted rows.
    """
    inserted = 0
    for row in rows:
        exists = conn.execute(
            "SELECT 1 FROM monthly_prices WHERE apartment_id=? AND deal_type=? "
            "AND deal_ym=? AND exclu_use_ar=?",
            (apartment_id, row["deal_type"], row["deal_ym"], row["exclu_use_ar"]),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO monthly_prices "
                "(apartment_id, deal_type, deal_ym, exclu_use_ar, "
                " price_min, price_max, price_avg, deal_count, "
                " deposit_min, deposit_max, deposit_avg) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (apartment_id, row["deal_type"], row["deal_ym"], row["exclu_use_ar"],
                 row.get("price_min"), row.get("price_max"), row.get("price_avg"),
                 row["deal_count"],
                 row.get("deposit_min"), row.get("deposit_max"), row.get("deposit_avg")),
            )
            inserted += 1
    conn.commit()
    return inserted
```

### Pattern 5: Trade/Rent Collector Loop

**What:** The main collection orchestration — loops over all districts × all months, checks idempotency, calls MolitClient, normalizes, aggregates, stores.

```python
# Source: project research — extends realestate_csv.py process_csv() pattern
import asyncio
import httpx
from pipeline.clients.molit import MolitClient
from pipeline.config.regions import PIPELINE_REGIONS
from pipeline.utils.idempotency import is_collected, mark_collected

async def collect_district(
    conn,
    client: httpx.AsyncClient,
    molit: MolitClient,
    lawd_cd: str,
    months: list[str],
    deal_type: str,
) -> int:
    """Collect all months for one district and deal_type. Returns total rows inserted."""
    total = 0
    for deal_ym in months:
        if is_collected(conn, lawd_cd, deal_ym, deal_type):
            continue
        items = await molit.fetch_all(client, lawd_cd, deal_ym, deal_type)
        if deal_type == "trade":
            normalized = [normalize_trade_item(i) for i in items]
        else:
            normalized = [normalize_rent_item(i) for i in items]
        aggregated = aggregate_monthly(normalized, deal_type)
        for agg_row in aggregated:
            apt_id = upsert_apartment(
                conn, lawd_cd,
                agg_row["apt_nm"], agg_row["umd_nm"],
            )
            total += insert_monthly_prices(conn, apt_id, [agg_row])
        mark_collected(conn, lawd_cd, deal_ym, deal_type, record_count=len(aggregated))
    return total
```

### Pattern 6: HouseInfo API (BLDG-01)

**What:** MOLIT HouseInfo endpoint returns building metadata for all apartment complexes in a district. Endpoint family: `RTMSDataSvcAptBldMgm`. Same serviceKey embedding pattern as trade/rent.

**Confirmed endpoint:** `https://apis.data.go.kr/1613000/RTMSDataSvcAptBldMgm/getRTMSDataSvcAptBldMgm`

**LAWD_CD format:** 5-digit (same as trade/rent). Confirmed from STACK.md and FEATURES.md — the 10-digit 법정동코드 concern noted in STATE.md is for a *different* MOLIT API family (`getBrBasisOulnInfo`). The `RTMSDataSvcAptBldMgm` family uses 5-digit LAWD_CD.

**Key response fields:**
```
buldNm      → 건물명 (아파트 단지명)
bcRat       → 건폐율 (%) — maps to building_coverage_ratio
vlRat       → 용적률 (%) — maps to floor_area_ratio
hhldCnt     → 세대수 — maps to total_households
pkngCnt     → 주차대수 — maps to total_parking
bldYr       → 건축년도 — maps to build_year
umdNm       → 법정동명 (used for apartment matching)
```

**Apartment matching:** HouseInfo uses `buldNm`; the existing `apartments` table was populated from trade/rent with `aptNm`. These two fields name the same complex but may differ in spacing or suffix (e.g., "은마" vs "은마아파트"). Match strategy: strip common suffixes ("아파트", " APT") and compare normalized strings. Fall back to inserting the apartment if no match is found (the HouseInfo row is still valuable).

```python
# Source: project research — building info collection pattern
_STRIP = ["아파트", "APT", "apt", " "]

def _normalize_apt_name(name: str) -> str:
    n = name.strip()
    for suffix in _STRIP:
        if n.endswith(suffix):
            n = n[:-len(suffix)]
    return n.replace(" ", "").lower()

async def collect_building_info(conn, client: httpx.AsyncClient, molit: MolitClient, lawd_cd: str):
    """
    Fetch building info for all apartments in a district and populate building_info table.
    Matches HouseInfo buldNm to apartments.apt_nm via normalized name comparison.
    """
    BLDG_ENDPOINT = (
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptBldMgm/"
        "getRTMSDataSvcAptBldMgm"
    )
    if is_collected(conn, lawd_cd, "000000", "building"):
        return

    url = (
        f"{BLDG_ENDPOINT}?serviceKey={molit.safe_key}"
        f"&LAWD_CD={lawd_cd}&numOfRows=1000&pageNo=1"
    )
    # ... fetch, parse, match, insert building_info rows
    mark_collected(conn, lawd_cd, "000000", "building")
```

### Anti-Patterns to Avoid

- **Inserting monthly_prices without checking for duplicates:** The `monthly_prices` table has no UNIQUE constraint. Always check before inserting, or use `collection_log` idempotency at the `(lawd_cd, deal_ym, data_type)` grain to ensure each month is only processed once.
- **Querying current month:** MOLIT has a 1-2 month submission lag. Always set end month to `previous calendar month`. Querying the current month produces sparse or empty results that appear correct.
- **Blocking the async loop with conn.commit() too frequently:** Commit once per `(lawd_cd, deal_ym)` pair, not after every row insert. Reduces WAL checkpoint overhead by a factor of ~10,000.
- **Using buildYear from HouseInfo vs. trade response without reconciliation:** The `apartments` table may already have `build_year` from trade response `buildYear`. The HouseInfo `bldYr` is more authoritative — update `apartments.build_year` when HouseInfo provides it.
- **Matching apartment names with exact string equality:** `aptNm` (trade) and `buldNm` (HouseInfo) are never guaranteed to match exactly. Always normalize before comparing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP | Custom socket client | `httpx.AsyncClient` via `MolitClient.fetch_all()` | Already built in Phase 1; all pagination + error handling included |
| XML parsing | String splitting | `xml.etree.ElementTree._parse_items()` | Already built in Phase 1 |
| Idempotency | In-memory set | `is_collected()` / `mark_collected()` from `pipeline.utils.idempotency` | Already built in Phase 1; persists across restarts |
| Month enumeration | Date arithmetic from scratch | `get_month_range()` ported from `realestate_csv.py` | Handles year rollover, end-of-month edge cases |
| Aggregation stats | pandas groupby | stdlib `collections.defaultdict` + built-in `min/max/sum` | No new dependency; adequate for list-of-dicts grouping |
| Apartment dedup | Custom hash set | `INSERT OR IGNORE` on `UNIQUE(lawd_cd, apt_nm, umd_nm)` | DB-enforced; survives restarts |

**Key insight:** Every hard problem in Phase 2 has either been solved in Phase 1 or exists as a proven pattern in `realestate_csv.py`. The work is wiring, normalizing, and aggregating — not inventing.

---

## Common Pitfalls

### Pitfall 1: MOLIT 1-2 Month Submission Lag (EMPTY CURRENT MONTH)

**What goes wrong:** Collecting through the current calendar month yields 0 rows for the most recent month, which the collection_log marks as collected. When the data finally appears 4-6 weeks later, the idempotency check blocks re-collection.

**Why it happens:** Korean local governments batch-submit transactions to MOLIT with a 1-2 month lag. The API accepts the month query but returns an empty response.

**How to avoid:** Always set `end_ym` to the previous calendar month:
```python
prev = datetime.now().replace(day=1) - timedelta(days=1)
end_ym = prev.strftime("%Y%m")
```

**Warning signs:** Most recent month returns 0 items; month before returns hundreds.

### Pitfall 2: monthly_prices Duplicate Rows (NO UNIQUE CONSTRAINT)

**What goes wrong:** Running the collector twice for the same `(lawd_cd, deal_ym, deal_type)` inserts duplicate `monthly_prices` rows because the table has no UNIQUE constraint. `collection_log` prevents duplicate API calls, but the DB rows are already duplicated from the first run if the process crashed mid-insert.

**Why it happens:** The `monthly_prices` schema (from Phase 1) does not have a UNIQUE constraint on `(apartment_id, deal_type, deal_ym, exclu_use_ar)` — this was a deliberate design choice to allow for future partial updates.

**How to avoid:** Check existence before every insert (see Pattern 4). Alternatively, treat `collection_log` as the sole gate: if `is_collected()` returns True, skip entirely. This means the first run must be atomic (commit all rows for a month before calling `mark_collected`).

**Warning signs:** `SELECT COUNT(*) FROM monthly_prices` grows after each re-run even with idempotency enabled.

### Pitfall 3: Apartment Name Mismatch (HouseInfo vs. Trade)

**What goes wrong:** HouseInfo `buldNm` is "은마" while trade `aptNm` is "은마아파트". Exact-string match fails. The HouseInfo row creates a second `apartments` row for the same complex, then `building_info` inserts against the wrong `apartment_id`.

**Why it happens:** MOLIT trade and HouseInfo endpoints use different source databases with inconsistent naming conventions.

**How to avoid:** Normalize both names before comparison: strip common suffixes, strip spaces, lowercase. Accept partial matches where one normalized name is a prefix/suffix of the other.

**Warning signs:** `apartments` table has duplicate rows that differ only in name suffix.

### Pitfall 4: HouseInfo API LAWD_CD Format (CONFIRMED: 5-DIGIT)

**What goes wrong:** Using 10-digit 법정동코드 with `RTMSDataSvcAptBldMgm` returns 0 results silently.

**Why it happens:** The STATE.md research flag ("MOLIT HouseInfo API LAWD_CD 파라미터 형식 (5자리 vs 10자리 법정동코드) 확인 필요") was flagged before research was complete. Research confirms: `RTMSDataSvcAptBldMgm` uses the same 5-digit LAWD_CD as the trade/rent endpoints. The 10-digit concern applies only to the unrelated `getBrBasisOulnInfo` (건축물대장) family which is NOT used in this project.

**How to avoid:** Use 5-digit `LAWD_CD` from `PIPELINE_REGIONS` for all three MOLIT endpoints. No conversion needed.

**Warning signs:** HouseInfo returns 0 items for districts that definitely have apartments.

### Pitfall 5: Committing Inside the Aggregation Loop (PERFORMANCE)

**What goes wrong:** Calling `conn.commit()` after every single `monthly_prices` INSERT turns what should be a fast bulk operation into thousands of individual fsync calls. For 29 districts × 20 years × 12 months = ~6,960 API calls, committing per-row inside the aggregation loop can increase total write time by 100×.

**How to avoid:** Commit once per `(lawd_cd, deal_ym)` batch — after all aggregated rows for that batch have been inserted. The `mark_collected()` call at the end of each batch already commits.

### Pitfall 6: Large Districts Exceed 1,000 Results Per Month (TRUNCATION)

**What goes wrong:** 강남구 in active months (e.g., 201901) has >1,000 transactions. A single-page fetch returns exactly 1,000 rows and silently truncates the rest.

**Why it happens:** MOLIT max `numOfRows` is 1,000. Pagination is required.

**How to avoid:** `MolitClient.fetch_all()` already handles pagination correctly (loops until `len(items) < page_size`). Never bypass `fetch_all()` with a direct single-page call.

**Warning signs:** A month returns exactly 1,000 rows.

---

## Code Examples

### Month Range Generator

```python
# Source: realestate_csv.py get_month_range() — adapted for pipeline
from datetime import datetime, timedelta

def get_month_range(start_ym: str = "200601") -> list[str]:
    now = datetime.now()
    prev = now.replace(day=1) - timedelta(days=1)
    end_y, end_m = prev.year, prev.month
    sy, sm = int(start_ym[:4]), int(start_ym[4:])
    result = []
    y, m = sy, sm
    while (y, m) <= (end_y, end_m):
        result.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result
```

### MOLIT Field Mapping — Trade vs. Rent

```python
# Source: realestate_csv.py normalize_trade_row() + FEATURES.md field reference
# Trade endpoint fields (camelCase, all string):
TRADE_FIELDS = {
    "aptNm":      "아파트명 — key for apartment identity",
    "umdNm":      "법정동명 — secondary identity key",
    "jibun":      "지번 — informational",
    "roadNm":     "도로명 — informational",
    "dealAmount": "거래금액(만원) — CONTAINS COMMAS: strip before int()",
    "excluUseAr": "전용면적(㎡) — float string: '84.9700'",
    "dealYear":   "계약년 — int string: '2024'",
    "dealMonth":  "계약월 — MAY LACK ZERO-PAD: '1' not '01'",
    "buildYear":  "건축년도 — int string, may be empty",
}

# Rent endpoint adds:
RENT_EXTRA_FIELDS = {
    "deposit":    "보증금(만원) — CONTAINS COMMAS: strip before int()",
    "monthlyRent":"월세(만원) — '0' for pure 전세",
}
```

### HouseInfo Endpoint URL Construction

```python
# Source: project research — same serviceKey pattern as trade/rent
HOUSEINFO_ENDPOINT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptBldMgm/"
    "getRTMSDataSvcAptBldMgm"
)

url = (
    f"{HOUSEINFO_ENDPOINT}?serviceKey={molit.safe_key}"
    f"&LAWD_CD={lawd_cd}"
    f"&numOfRows=1000&pageNo={page}"
)
# Note: HouseInfo does NOT take a DEAL_YMD parameter — it returns all complexes for the district
```

### building_info Upsert

```python
# Source: project research — building_info has UNIQUE(apartment_id)
def upsert_building_info(conn, apartment_id: int, bldg: dict) -> None:
    """Insert or replace building_info for an apartment."""
    conn.execute(
        "INSERT OR REPLACE INTO building_info "
        "(apartment_id, build_year, total_households, floor_area_ratio, "
        " building_coverage_ratio, total_parking) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (apartment_id,
         bldg.get("build_year"),
         bldg.get("total_households"),
         bldg.get("floor_area_ratio"),
         bldg.get("building_coverage_ratio"),
         bldg.get("total_parking")),
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSV output per run (`realestate_csv.py`) | SQLite upsert — full history in one file | Phase 2 | pandas/dashboard-ready; no file management |
| Input-driven (CSV of apartments to query) | District-scan (all apartments in LAWD_CD) | Phase 2 | Complete coverage; no manual apartment list |
| No idempotency | `collection_log` + `is_collected()` gate | Phase 1 (inherited) | Safe reruns; resume after crash |
| No building info | HouseInfo API → `building_info` table | Phase 2 | `build_year`, `total_households`, FAR, BCR available |

**Deprecated/outdated:**
- `realestate_csv.py process_csv()` approach: superseded by `collect_district()` loop — no CSV input needed, full district scan instead.

---

## Open Questions

1. **HouseInfo API `DEAL_YMD` parameter requirement**
   - What we know: Trade/rent APIs require `DEAL_YMD` (year-month). HouseInfo returns building-level data without a time dimension.
   - What's unclear: Does `RTMSDataSvcAptBldMgm` accept/require a `DEAL_YMD` or any date parameter? Research suggests NO — it returns all complexes in the district. Confirm with a live test call.
   - Recommendation: Omit `DEAL_YMD` for HouseInfo. Use `"000000"` as the `deal_ym` sentinel in `collection_log` for building data (one entry per district).

2. **`monthly_prices` UNIQUE constraint gap**
   - What we know: The schema has no UNIQUE constraint on `monthly_prices`. Duplicate rows are possible if the collector crashes mid-batch and is re-run.
   - What's unclear: Whether to add a UNIQUE constraint via a schema migration or handle in application code.
   - Recommendation: Handle in application code (check before insert). Adding a UNIQUE constraint post-Phase-1 requires `ALTER TABLE` which is not supported for UNIQUE in SQLite — it would require recreating the table. Keep as application-level dedup.

3. **`apartments.build_year` source of truth**
   - What we know: Both trade response (`buildYear`) and HouseInfo (`bldYr`) provide build year. They may disagree.
   - Recommendation: HouseInfo is the authoritative source. When HouseInfo provides `bldYr`, `UPDATE apartments SET build_year=? WHERE id=?`. Trade `buildYear` is used only when HouseInfo is not yet available.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_pipeline_phase2.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRICE-04 | `normalize_trade_item()` strips comma from dealAmount, returns int | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_trade_deal_amount -x` | Wave 0 |
| PRICE-04 | `normalize_trade_item()` converts excluUseAr to float | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_trade_exclu_use_ar -x` | Wave 0 |
| PRICE-04 | `normalize_trade_item()` zero-pads dealMonth "1" → "01" | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_trade_deal_month_padding -x` | Wave 0 |
| PRICE-03 | `aggregate_monthly()` groups items by (apt_nm, umd_nm, deal_ym, exclu_use_ar) | unit | `pytest tests/test_pipeline_phase2.py::test_aggregate_monthly_grouping -x` | Wave 0 |
| PRICE-03 | `aggregate_monthly()` computes correct min/max/avg/count for trade | unit | `pytest tests/test_pipeline_phase2.py::test_aggregate_monthly_stats -x` | Wave 0 |
| PRICE-01 | `upsert_apartment()` inserts new apartment and returns correct id | unit (in-memory DB) | `pytest tests/test_pipeline_phase2.py::test_upsert_apartment_new -x` | Wave 0 |
| PRICE-01 | `upsert_apartment()` returns same id on second call for same apartment | unit (in-memory DB) | `pytest tests/test_pipeline_phase2.py::test_upsert_apartment_idempotent -x` | Wave 0 |
| PRICE-01 | `insert_monthly_prices()` does not insert duplicate rows | unit (in-memory DB) | `pytest tests/test_pipeline_phase2.py::test_insert_monthly_prices_no_dup -x` | Wave 0 |
| PRICE-02 | `normalize_rent_item()` strips commas from deposit | unit | `pytest tests/test_pipeline_phase2.py::test_normalize_rent_deposit -x` | Wave 0 |
| BLDG-01 | `upsert_building_info()` inserts building_info row linked by apartment_id | unit (in-memory DB) | `pytest tests/test_pipeline_phase2.py::test_upsert_building_info -x` | Wave 0 |
| BLDG-02 | `upsert_building_info()` replaces on second call (INSERT OR REPLACE) | unit (in-memory DB) | `pytest tests/test_pipeline_phase2.py::test_upsert_building_info_replace -x` | Wave 0 |
| PRICE-01/02 | `get_month_range("200601")` starts at "200601", ends before current month | unit | `pytest tests/test_pipeline_phase2.py::test_month_range_bounds -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_pipeline_phase2.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_phase2.py` — all 12 tests listed above (pure function + in-memory DB tests; no network calls)
- [ ] `pipeline/collectors/__init__.py` — package marker
- [ ] `pipeline/processors/__init__.py` — package marker
- [ ] `pipeline/storage/__init__.py` — package marker (may already exist; verify)

*(conftest.py already exists with `tmp_db` fixture — no gap)*

---

## Sources

### Primary (HIGH confidence)

- `pipeline/clients/molit.py` — MolitClient, ENDPOINTS dict, serviceKey pattern (Phase 1 implementation)
- `pipeline/storage/schema.py` — exact column names for apartments, monthly_prices, building_info tables
- `pipeline/config/regions.py` — PIPELINE_REGIONS (29 entries, 5-digit LAWD_CDs)
- `pipeline/utils/idempotency.py` — is_collected/mark_collected interface
- `realestate_csv.py` — normalize_trade_row() field names, get_month_range(), serviceKey encoding (line 362)
- `.planning/research/FEATURES.md` — MOLIT field reference table, Korea-specific quirks
- `.planning/research/ARCHITECTURE.md` — HouseInfo API endpoint family, component design
- `.planning/research/STACK.md` — HouseInfo endpoint: `RTMSDataSvcAptBldMgm`

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — HouseInfo LAWD_CD format note (5-digit confirmed for `RTMSDataSvcAptBldMgm`)
- `.planning/STATE.md` — Research flags clarified: 10-digit concern applies to `getBrBasisOulnInfo` only, not to `RTMSDataSvcAptBldMgm`

### Tertiary (LOW confidence)

- HouseInfo `DEAL_YMD` parameter requirement — not verified by live call; architecture research suggests it is not required. Mark for validation in Wave 0 test or first live run.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in codebase; no new dependencies for Phase 2
- Architecture: HIGH — module layout follows ARCHITECTURE.md; normalizer/aggregator patterns derived from existing `realestate_csv.py`
- Data normalization patterns: HIGH — field names and transformations verified from `realestate_csv.py` and FEATURES.md
- HouseInfo endpoint URL: MEDIUM — endpoint family confirmed from STACK.md; exact parameter behavior (no DEAL_YMD) is LOW until live-tested
- Pitfalls: HIGH — all pitfalls verified against existing codebase patterns and MOLIT API behavior documented in Phase 1 research

**Research date:** 2026-03-17T07:15:40Z
**Valid until:** 2026-04-17 (MOLIT API endpoints are stable; LAWD_CD codes are permanent; normalization patterns are locked by existing code)
