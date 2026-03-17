# Domain Pitfalls

**Domain:** 한국 부동산 데이터 수집 파이프라인 (Korean Real Estate Data Pipeline)
**Researched:** 2026-03-17T05:31:27Z
**Confidence:** HIGH — pitfalls drawn directly from confirmed codebase evidence in realestate_csv.py, location_service.py, and fastmcp_realestate.py

---

## Critical Pitfalls

Mistakes that cause silent failures, 401 errors, or complete data loss.

---

### Pitfall 1: MOLIT API serviceKey Double-Encoding (401 Errors)

**What goes wrong:** When `serviceKey` is passed via `httpx params={}` dict, httpx URL-encodes the value. If the key is already URL-encoded (as issued by data.go.kr with `+` and `/` characters), httpx double-encodes it — turning `%2B` into `%252B`. The server receives a malformed key and returns HTTP 401.

**Why it happens:** data.go.kr issues API keys containing `+` and `/` characters that are themselves URL-unsafe. The key must be pre-encoded before injection. Using `params={"serviceKey": key}` applies a second encoding pass.

**Consequences:** Every API call fails with 401. The error message ("SERVICE_KEY_IS_NOT_REGISTERED_ERROR") looks like a registration problem, not an encoding problem. Teams waste hours re-issuing keys.

**Prevention:** Manually embed the pre-encoded key directly in the URL string, not via the params dict.

```python
# WRONG — httpx double-encodes the key
params = {"serviceKey": api_key, "LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd}
response = await client.get(endpoint, params=params)

# CORRECT — key embedded in URL, other params passed normally
from urllib.parse import unquote, quote
safe_key = quote(unquote(api_key), safe='')
url = f"{base_url}?serviceKey={safe_key}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=1000&pageNo={page}"
response = await client.get(url)
```

This exact fix is already implemented in `realestate_csv.py` line 362. The new pipeline must preserve this pattern — do not refactor to `params={}` for serviceKey.

**Detection:** Response body contains `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` or result code `30` despite the key being valid and registered on data.go.kr.

**Phase:** Pipeline foundation (Phase 1). Must be correct before any data collection is possible.

---

### Pitfall 2: MOLIT API XML Field Names Are English camelCase, Not Korean

**What goes wrong:** The MOLIT RTMSOBJSvc API returns XML with English camelCase field names (`aptNm`, `dealAmount`, `excluUseAr`, `umdNm`, `dealYear`, `dealMonth`, `dealDay`, `buildYear`, `floor`, `aptDong`, `jibun`, `roadNm`, `dealingGbn`, `deposit`, `monthlyRent`). Code that looks for Korean keys (`거래금액`, `아파트명`, `전용면적`) will silently return empty strings for all values.

**Why it happens:** The API documentation uses Korean labels for human readers, but the actual XML `<tag>` elements are English camelCase. The disconnect is not obvious until you inspect raw XML output.

**Consequences:** All numeric fields (price, area, year) parse as empty strings. Aggregation produces zeros. The bug is silent — rows appear valid but all data fields are blank.

**Prevention:** Always map from camelCase XML field names. Keep a reference mapping:

```python
# MOLIT Trade (매매) XML fields
"aptNm"       # 아파트명
"dealAmount"  # 거래금액 (contains commas: "55,000")
"excluUseAr"  # 전용면적(㎡)
"floor"       # 층
"buildYear"   # 건축년도
"dealYear"    # 계약년
"dealMonth"   # 계약월
"dealDay"     # 계약일
"umdNm"       # 법정동명
"jibun"       # 지번
"roadNm"      # 도로명
"aptDong"     # 동
"dealingGbn"  # 거래구분 (직거래/중개거래)

# MOLIT Rent (전월세) XML fields — same as above plus:
"deposit"       # 보증금(만원)
"monthlyRent"   # 월세금(만원)
```

`dealAmount` values include comma separators ("55,000") that must be stripped before numeric conversion.

**Detection:** After parsing, spot-check `row.get("aptNm")` against `row.get("아파트명")` — the Korean key will return None for every row.

**Phase:** Phase 1 (data model definition). Define the field mapping table once, before writing any aggregation logic.

---

### Pitfall 3: Apartment Name Matching Failures (API Name vs Real Name Discrepancy)

**What goes wrong:** The `aptNm` field in MOLIT data uses the official registered name, which often differs from the commonly known name. Examples:
- API returns `"은마"`, users search `"은마아파트"` (or vice versa)
- API returns `"래미안블레스티지"`, users store `"래미안 블레스티지"` (spacing difference)
- API returns `"힐스테이트에코마포"`, users store `"힐스테이트 에코 마포"` (spacing + structure)
- New branded names after rebranding (건설사 변경 후 이름 변경)

**Why it happens:** MOLIT registers the legal building name at the time of construction approval. Colloquial names, spacing conventions, and brand changes create a persistent mismatch between user-supplied names and API data.

**Consequences:** `filter_by_apt_name` returns 0 matches, and the fallback dumps the entire district's transactions (potentially thousands of rows) into the output, contaminating the dataset.

**Prevention:**
1. Strip the suffix `아파트`/`APT` before comparison
2. Remove all spaces from both sides before substring matching
3. Use bidirectional containment check (key in item OR item in key)
4. When 0 matches found, log candidate names from the API response so the user can correct the input

```python
def _strip_suffix(name: str) -> str:
    for s in ["아파트", "APT", "apt"]:
        if name.strip().endswith(s):
            name = name.strip()[:-len(s)]
    return name.replace(" ", "").strip()

def matches(query: str, api_name: str) -> bool:
    q = _strip_suffix(query)
    a = _strip_suffix(api_name)
    return q in a or a in q
```

For the new pipeline (district-scan mode without user-supplied names), this pitfall shifts: you must correctly identify which `aptNm` values belong to the same physical complex across months (same building, minor spelling drift between records over time).

**Detection:** Zero-match result for a known apartment in a district that clearly has transactions. Fallback log message appears: `"[주의] '{name}' 매칭 없음"`.

**Phase:** Phase 1-2. Define normalization functions before building the apartment roster deduplication logic.

---

### Pitfall 4: Naver Maps NCP IAM Credentials vs Application API Key Mismatch

**What goes wrong:** Naver Cloud Platform issues two types of credentials: IAM credentials (prefix `ncp_iam_`) for server/service-level authentication, and Application API keys (Client ID / Client Secret) for Maps APIs. The Maps Geocoding, Direction, and Places APIs require Application API keys sent as HTTP headers (`X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`). Using IAM credentials returns 401 or 403 with no clear error message.

**Why it happens:** The NCP console has multiple credential sections. Developers often issue IAM credentials first (they appear first in the UI) and try to use them for Maps APIs.

**Consequences:** All Naver Maps calls fail. The existing codebase already has a detection check for `ncp_iam_` prefix in `location_service.py` (lines 199-204, 299-304), indicating this was already encountered.

**Prevention:**
1. Issue credentials from NCP Console → AI·Application Service → Maps → Application registration
2. The Application section generates a separate Client ID and Client Secret
3. Add a startup check: if `NAVER_CLIENT_ID.startswith("ncp_iam_")`, fail fast with a clear message

```python
if NAVER_CLIENT_ID.startswith("ncp_iam_"):
    raise ValueError(
        "Naver Maps requires Application API credentials, not IAM credentials. "
        "Go to NCP Console → Maps → Application to get Client ID/Secret."
    )
```

**Detection:** API returns 401. `NAVER_CLIENT_ID` value starts with `ncp_iam_`. Already detected at runtime in `location_service.py`.

**Phase:** Phase 3 (Naver Maps integration). Validate credential type before writing any walking-distance collection code.

---

### Pitfall 5: Naver Maps Direction5 API — Walking Distance vs Straight-Line Distance

**What goes wrong:** The `calculate_distance()` haversine function in `location_service.py` computes straight-line distance, not walking distance. For the pipeline requirement of "도보 거리 1km 초과 시 null", using straight-line distance will systematically underestimate walking distance — especially in areas with rivers, hills, or highway barriers. A station 700m straight-line could be 1.3km walking.

**Why it happens:** Haversine is easy to implement without an API key. The code silently uses it as a substitute for actual routing.

**Consequences:** Apartments near the Han River or behind elevated highways are incorrectly classified as "within 1km walking distance" when they are not. This corrupts the accessibility data.

**Prevention:** Use Naver Maps Direction5 API (walking mode) for the actual pipeline. The endpoint is `https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving` with `option=traoptimal` replaced by walking parameters, or the pedestrian-specific endpoint.

Key constraint: Direction5 API has daily call limits (default 1,000 calls/day for free tier; 300,000/month for paid). For a district with 500 apartments and 5 target stations (GBD/CBD/YBD + 2 nearest), that is 2,500 calls minimum. Plan API quota before implementation.

**Rate limit mitigation:**
- Cache results in SQLite after first calculation
- Only call for apartments without an existing cached value
- Batch calls with 100ms delays to avoid burst throttling

**Detection:** Walking distances are consistently shorter than expected for apartments near rivers. Compare a sample of haversine results against Google Maps walking times.

**Phase:** Phase 3. Must use real routing API, not haversine, for the 1km threshold classification.

---

### Pitfall 6: MOLIT API numOfRows=1000 Pagination — Silent Truncation

**What goes wrong:** The MOLIT API has a hard limit of 1,000 rows per request. For busy districts (강남구, 서초구, 송파구), a single month can have more than 1,000 transactions. Without pagination, data is silently truncated. The API returns exactly 1,000 rows with no error or warning.

**Why it happens:** The API follows the standard Korean public data portal pagination pattern but does not return a `totalCount` that is reliably checked.

**Consequences:** Monthly aggregates (min/max/avg price, transaction count) are wrong for high-volume districts. The error is impossible to detect without comparing to MOLIT's published monthly statistics.

**Prevention:** Implement full pagination. Fetch until the returned row count is less than `numOfRows`.

```python
page = 1
all_items = []
while True:
    items = await fetch_page(lawd_cd, deal_ymd, page, page_size=1000)
    all_items.extend(items)
    if len(items) < 1000:
        break
    page += 1
```

This is already implemented in `realestate_csv.py` `fetch_trades()`. The new pipeline must preserve this loop — do not simplify to a single-page call.

**Detection:** For 강남구 in any month 2020-present, a single-page call returns exactly 1,000 rows. Check if `len(items) == 1000` and compare the result count to the official MOLIT monthly statistics report.

**Phase:** Phase 1. Required for data integrity from the first data collection run.

---

## Moderate Pitfalls

---

### Pitfall 7: SQLite Bulk Insert Performance — Row-by-Row vs executemany

**What goes wrong:** Inserting rows one at a time with individual `execute()` calls inside a loop is 50-100x slower than `executemany()` with a list. For 2006–present across all Seoul districts (25 + 5 regions), a full historical load can produce millions of rows. Row-by-row insertion can take hours instead of minutes.

**Prevention:**
1. Use `executemany()` with a list of tuples, not a loop of `execute()`
2. Wrap bulk inserts in explicit transactions (`BEGIN`/`COMMIT`) rather than autocommit
3. Set `PRAGMA journal_mode=WAL` for concurrent reads during load
4. Set `PRAGMA synchronous=NORMAL` during initial load, then restore to `FULL`

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("BEGIN")
conn.executemany(
    "INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?)",
    [(row["aptNm"], row["dealAmount"], ...) for row in batch]
)
conn.execute("COMMIT")
```

**Detection:** A full district-month insert taking more than 1 second per call. Profile with `time.perf_counter()` around insert blocks.

**Phase:** Phase 4 (SQLite schema and loading). Set these PRAGMAs in the schema initialization, not per-insert.

---

### Pitfall 8: SQLite Missing Composite Indexes for Query Patterns

**What goes wrong:** The analysis queries filter on `(district, pyeong_range, month)` combinations. Without composite indexes on these columns, pandas queries that join or filter the full transactions table scan millions of rows.

**Prevention:** Create indexes that match the primary query patterns at schema creation time:

```sql
-- Primary analysis index
CREATE INDEX idx_trades_district_month ON trades(lawd_cd, deal_ym);

-- Apartment-level aggregation index
CREATE INDEX idx_trades_apt_month ON trades(apt_nm_normalized, deal_ym);

-- Area bucket queries
CREATE INDEX idx_trades_area ON trades(exclu_use_ar);
```

Define indexes in the schema migration, not as an afterthought after performance problems emerge.

**Detection:** `EXPLAIN QUERY PLAN` output showing `SCAN TABLE trades` instead of `SEARCH TABLE trades USING INDEX`.

**Phase:** Phase 4 (schema design). Index design must happen before the first data load, not after.

---

### Pitfall 9: BFS Subway Graph — Hardcoded Partial Station List

**What goes wrong:** `location_service.py` contains a `SUBWAY_STATIONS` dict with approximately 35 stations — a tiny fraction of Seoul's 300+ stations and the wider metropolitan network. A BFS on this partial graph produces incorrect "nearest station" results and cannot compute transfers or GBD/CBD/YBD hop counts.

**Why it happens:** Manually maintaining a complete subway graph is infeasible. The current code was built for demonstration, not production.

**Consequences:** BFS results for stations not in the hardcoded list return incorrect nearest-station assignments. Transfer routes through missing stations are broken.

**Prevention:** Use Seoul Metro's official GTFS (General Transit Feed Specification) data, available from:
- 서울 열린데이터광장 (data.seoul.go.kr) — GTFS format
- 한국철도공사 코레일 공공데이터 포털 — intercity lines

Build the graph from GTFS `stops.txt` and `stop_times.txt`:

```python
import csv
import collections

def build_subway_graph(gtfs_dir: str) -> dict:
    """Build adjacency graph from GTFS stops and stop_times."""
    graph = collections.defaultdict(set)
    # Parse stop_times.txt: group by trip_id, connect consecutive stops
    ...
    return graph
```

For transfer connections, GTFS `transfers.txt` provides explicit transfer station links.

Alternative: Use the static SUBWAY_LINES adjacency list published by Seoul Metro (updated annually) bundled as a JSON file in the project.

**Detection:** BFS from "과천시청역" to "강남역" returns 2 hops (direct on 4호선) but the hardcoded list contains neither station.

**Phase:** Phase 5 (BFS/accessibility calculation). GTFS data loading must be the first task in this phase.

---

### Pitfall 10: BFS Transfer Counting — Station Node vs Physical Station Conflation

**What goes wrong:** In subway graphs, transfer stations (환승역) have multiple platform entries in GTFS (one per line). Naive BFS that counts each `stop_id` as one hop counts the transfer itself as a hop. "강남역 2호선" → "강남역 신분당선" appears as 1 hop (a transfer), inflating the station count.

**Why it happens:** GTFS models each line's stop separately with a unique `stop_id`. The logical station is a group of physical platforms.

**Consequences:** Routes with transfers show higher hop counts than routes without, even when the transfer adds no actual station. This skews accessibility rankings for apartments near transfer hubs.

**Prevention:**
1. Group `stop_id` entries by physical station using GTFS `parent_station` field
2. Build the graph at the physical station level, not the platform level
3. Treat a transfer (same physical station, different lines) as 0 additional hops

```python
# Map platform stop_ids to parent station
parent_map = {}  # stop_id -> parent_station_id
for stop in stops:
    if stop["parent_station"]:
        parent_map[stop["stop_id"]] = stop["parent_station"]
    else:
        parent_map[stop["stop_id"]] = stop["stop_id"]

# Build graph at parent station level
graph[parent_map[stop_a]].add(parent_map[stop_b])
```

**Detection:** BFS from 교대역 to 강남역 returns 1 hop (correct: direct on 2호선), but a route from 교대역 via transfer at 사당역 to 방배역 should also show correctly without inflated counts.

**Phase:** Phase 5. Define the physical station grouping before BFS implementation begins.

---

### Pitfall 11: MOLIT API Response — 200 Status with Error Body

**What goes wrong:** MOLIT API (and all Korean public data portal APIs) return HTTP 200 even for error conditions. The error is encoded in the XML body as a result code. Common patterns:
- `<resultCode>30</resultCode>` — SERVICE_KEY_IS_NOT_REGISTERED_ERROR
- `<resultCode>22</resultCode>` — LIMITED_NUMBER_OF_SERVICE_REQUESTS_PER_SECOND_EXCEEDS_ERROR
- `<resultCode>99</resultCode>` — APPLICATION_ERROR (invalid parameter values)

Code that only checks `response.raise_for_status()` will treat all of these as success and attempt to parse an error XML as data, producing 0 items silently.

**Prevention:** Parse the result code before processing items:

```python
def check_api_result(xml_text: str) -> tuple[bool, str]:
    root = ET.fromstring(xml_text)
    code = root.findtext(".//resultCode") or root.findtext(".//cmmMsgHeader/errMsg")
    if code and code != "00" and code != "0000":
        msg = root.findtext(".//resultMsg") or root.findtext(".//errMsg") or "Unknown error"
        return False, f"API Error {code}: {msg}"
    return True, ""
```

Rate limit errors (code 22) require exponential backoff, not immediate retry.

**Detection:** API call returns 200 with `items=[]` for a district that definitely has transactions in that month.

**Phase:** Phase 1. Add result code checking to the base HTTP client wrapper from the start.

---

## Minor Pitfalls

---

### Pitfall 12: LAWD_CD Granularity — 5-Digit vs 10-Digit Codes

**What goes wrong:** MOLIT API uses 5-digit `LAWD_CD` (시군구 level). The SIGUNGU_MAP in `realestate_csv.py` correctly maps to 5-digit codes. However, some documentation references 10-digit `법정동코드` (동 level) or 8-digit codes. Passing a wrong-length code returns an empty result set with no error.

**Prevention:** Always use exactly 5-digit codes for MOLIT RTMSOBJSvc endpoints. Validate length before each API call:

```python
assert len(lawd_cd) == 5 and lawd_cd.isdigit(), f"Invalid LAWD_CD: {lawd_cd}"
```

For the target regions, the correct codes are:
- 성남시 분당구: `41175` (not `41130` which is 성남시 전체)
- 안양시 동안구: `41220` (not `41170` which is 안양시 전체)
- 하남시: `41550`
- 과천시: `41390`

**Phase:** Phase 1 (LAWD_CD mapping table). Validate the mapping table with a test call before building the full pipeline.

---

### Pitfall 13: dealAmount Comma Format — Numeric Conversion Without Strip

**What goes wrong:** `dealAmount` values in MOLIT XML contain comma separators: `"55,000"` (만원). Direct `int()` conversion raises `ValueError`. The `float()` conversion also fails. Code that silently catches the exception stores 0 as the price.

**Prevention:** Always strip commas before numeric conversion:

```python
price = int(row.get("dealAmount", "0").replace(",", "").strip() or "0")
```

**Detection:** All price values in the output are 0. The raw XML shows `<dealAmount>55,000</dealAmount>`.

**Phase:** Phase 1 (normalization). Apply to all numeric fields during XML parse.

---

### Pitfall 14: MOLIT Data Availability Lag — Current Month Returns Empty

**What goes wrong:** MOLIT transaction data is reported by local governments and typically has a 1-2 month lag. Querying the current month returns 0 or very few results, not because the area is inactive but because reports have not been submitted yet.

**Prevention:** When running the pipeline, stop at the previous month, not the current month. Add a configurable `lag_months=2` parameter:

```python
end_ym = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")  # last month
```

**Detection:** Current month query returns 0 results for 강남구. Previous month returns 300+ results.

**Phase:** Phase 1 (date range logic). Add the lag offset in the month range generator.

---

### Pitfall 15: SQLite utf-8 vs euc-kr Korean Text Corruption

**What goes wrong:** MOLIT XML responses are served in UTF-8 (declared in XML header). If the HTTP client reads the response as bytes and decodes with the wrong encoding (or if `response.text` auto-detects as `euc-kr` based on `Content-Type` header), Korean apartment names are corrupted.

**Prevention:**
1. Always use `response.content.decode('utf-8')` rather than `response.text` if there is any doubt about encoding detection
2. Verify SQLite is opened with `isolation_level` and that Python's `sqlite3` module stores text as UTF-8 (it does by default)
3. Do not write CSV intermediary files with default encoding — always specify `encoding='utf-8-sig'` for Excel compatibility

**Detection:** Apartment names in output show `?` characters or Mojibake (`ì•„ì 트` instead of `아파트`).

**Phase:** Phase 1. Set encoding explicitly in all I/O paths from the start.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| MOLIT API client setup | serviceKey double-encoding (Pitfall 1) | Embed key in URL string, not params dict |
| XML field parsing | camelCase field name mismatch (Pitfall 2) | Use English field name reference table |
| District-scan apartment deduplication | Name normalization across months (Pitfall 3) | Normalize before unique ID assignment |
| Naver Maps API setup | IAM vs Application credentials (Pitfall 4) | Check credential prefix at startup |
| Walking distance threshold | Straight-line vs routed distance (Pitfall 5) | Use Direction5 API, not haversine |
| High-volume district collection | Silent truncation at 1,000 rows (Pitfall 6) | Implement full pagination loop |
| SQLite schema creation | Missing composite indexes (Pitfall 8) | Define indexes in schema migration |
| SQLite bulk insert | Row-by-row insert performance (Pitfall 7) | Use executemany + explicit transaction |
| BFS graph data source | Partial hardcoded station list (Pitfall 9) | Load from GTFS or Seoul Metro static data |
| BFS transfer counting | Platform vs physical station confusion (Pitfall 10) | Group by parent_station in GTFS |
| Any API call success check | HTTP 200 with error body (Pitfall 11) | Parse resultCode before processing items |
| Month range generation | Current month data lag (Pitfall 14) | Default end = previous month |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| MOLIT API encoding (Pitfall 1) | HIGH | Confirmed fix in realestate_csv.py line 362 |
| XML field names (Pitfall 2) | HIGH | Confirmed in normalize_trade_row() |
| Apartment name matching (Pitfall 3) | HIGH | Confirmed in filter_by_apt_name() with fallback log |
| Naver IAM credentials (Pitfall 4) | HIGH | Confirmed detection code in location_service.py |
| Walking distance accuracy (Pitfall 5) | HIGH | Confirmed haversine usage in location_service.py |
| Pagination truncation (Pitfall 6) | HIGH | Confirmed pagination loop in fetch_trades() |
| SQLite performance (Pitfalls 7-8) | MEDIUM | Standard SQLite patterns, not yet in codebase |
| BFS GTFS approach (Pitfalls 9-10) | MEDIUM | GTFS is the authoritative source; transfer counting is well-documented |
| HTTP 200 error body (Pitfall 11) | HIGH | Standard Korean public data API behavior |
| LAWD_CD granularity (Pitfall 12) | HIGH | Confirmed in SIGUNGU_MAP with correct codes |
| Comma-format numbers (Pitfall 13) | HIGH | Confirmed .replace(",", "") in normalize_trade_row() |
| Data availability lag (Pitfall 14) | MEDIUM | Known MOLIT characteristic, not yet enforced in pipeline |
| Encoding (Pitfall 15) | MEDIUM | Standard concern, utf-8 used in existing code |

---

## Sources

- Codebase: `realestate_csv.py` — primary evidence for Pitfalls 1, 2, 3, 6, 12, 13
- Codebase: `app/mcp/location_service.py` — evidence for Pitfalls 4, 5, 9
- Codebase: `app/mcp/fastmcp_realestate.py` and `app/mcp/real_estate_server.py` — evidence for Pitfalls 6, 11
- PROJECT.md — requirement constraints for Pitfalls 5, 9, 10
- CONCERNS.md — evidence for CSV parsing silent failure (Pitfall 11 pattern)
- Korean Public Data Portal (data.go.kr) standard API behavior — Pitfalls 1, 11, 14
- Seoul Metro GTFS available at data.seoul.go.kr — Pitfalls 9, 10
