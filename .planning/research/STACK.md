# Technology Stack

**Project:** 한국 부동산 데이터 수집 파이프라인
**Researched:** 2026-03-17
**Confidence:** HIGH (based on existing codebase analysis + library knowledge through August 2025)

---

## Recommended Stack

### HTTP Client — httpx (already in codebase)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | >=0.27.0 | MOLIT API + Naver Maps API HTTP calls | Already used in `realestate_csv.py` and the broader FastAPI codebase. Supports both sync and async interfaces. Native `asyncio` support with connection pooling. Built-in timeout and retry-friendly API. |

**Do NOT use aiohttp.** The codebase already depends on httpx 0.27+. Mixing two async HTTP clients adds dependency weight with zero benefit. httpx's sync API (`httpx.Client`) is also useful for simple one-shot CLI scripts that don't need the full async event loop.

**Korea-specific MOLIT quirk:** The `serviceKey` is a URL-encoded string issued by data.go.kr. It must be double-decoded then re-encoded before embedding in query strings. The existing `realestate_csv.py` already handles this correctly with `quote(unquote(api_key), safe='')`. **Do not use httpx's `params=` dict for serviceKey** — httpx re-encodes `+` as `%2B` which breaks MOLIT's signature validation. Build the URL manually as the existing code does.

**MOLIT XML encoding quirk:** Responses are EUC-KR encoded at the HTTP level but most modern MOLIT endpoints actually return UTF-8 with a declared charset. Always read `resp.text` (httpx auto-detects charset from Content-Type), not `resp.content`. If a MOLIT endpoint returns garbled Korean, force: `resp.content.decode('euc-kr')`.

---

### XML Parsing — xml.etree.ElementTree (stdlib)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| xml.etree.ElementTree | stdlib | Parse MOLIT XML responses | Already used in `realestate_csv.py`. MOLIT responses are simple flat `<item>` lists — no namespace complexity, no deep nesting. Zero extra dependency. lxml adds C compilation overhead for no gain here. |

**Do NOT use lxml or BeautifulSoup** for MOLIT XML. The response schema is trivially flat (`<response><body><items><item>...</item></items></body></response>`). ElementTree's `.findall(".//item")` covers 100% of the use case.

**Pagination pattern (already validated):** MOLIT uses `numOfRows` + `pageNo` parameters. When `len(items) < numOfRows`, you're on the last page. The existing implementation in `fetch_trades()` is correct.

---

### Database — sqlite3 (stdlib) + No ORM

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sqlite3 | stdlib | Primary data store | PROJECT.md explicitly requires sqlite3. No server, no setup, file-portable, natively supported by pandas and Streamlit. |

**Do NOT use SQLAlchemy.** This is a standalone CLI pipeline writing to a single SQLite file. SQLAlchemy's session/connection pooling, ORM mapping, and migration overhead are irrelevant. Raw `sqlite3` with parameterized queries (`?` placeholders) is simpler, faster to write, and has zero extra dependencies.

**Schema approach:** Use `CREATE TABLE IF NOT EXISTS` in a `schema.py` module. Run schema creation at pipeline startup. Use `executemany()` for bulk inserts — 10-100x faster than row-by-row for thousands of transaction records.

**Index strategy:** Add indexes on `(lawd_cd, deal_ym, apt_name)` for the transaction tables and `(apt_id)` for joins. Without indexes, pandas cross-joins on 20 years of transaction data will be slow.

---

### Data Analysis / Export — pandas

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pandas | >=2.0.0 | Aggregation (min/max/avg per apt/size/month), CSV export | Standard for tabular real estate analytics. `pd.read_sql()` directly queries SQLite. `DataFrame.to_csv()` handles UTF-8-BOM for Excel compatibility (Korean columns). |

**Specific usage pattern:**
```python
import pandas as pd, sqlite3
conn = sqlite3.connect("realestate.db")
df = pd.read_sql("SELECT * FROM apt_trades WHERE lawd_cd = ?", conn, params=("11680",))
summary = df.groupby(["apt_name", "area_m2", "deal_ym"])["price_만원"].agg(["min", "max", "mean", "count"])
summary.to_csv("output.csv", encoding="utf-8-sig")  # utf-8-sig = Excel-compatible BOM
conn.close()
```

**Do NOT use polars** despite its 2024-2025 popularity surge. The dataset size (millions of rows max) does not justify the unfamiliar API, and pandas has better SQLite integration via `read_sql`.

---

### CLI Interface — Typer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| typer | >=0.12.0 | CLI commands for region selection, date range, collection type | Type-annotated CLI — Python function signature becomes CLI automatically. No decorator boilerplate like Click. Generates `--help` with Korean-friendly `help=` strings. Rich integration for progress bars built-in. |

**Do NOT use argparse.** The existing `realestate_csv.py` uses argparse, which is fine for a single-file script but does not scale to a multi-command pipeline (`collect`, `export`, `status`, `migrate`). Typer's subcommand support (`app = typer.Typer(); @app.command()`) handles this cleanly.

**Do NOT use Click directly.** Typer is a typed wrapper around Click. All Click functionality is available when needed, but 90% of use cases need zero Click knowledge.

**Minimum version:** 0.12.0 (released 2024) — fixes Python 3.12 compatibility issues with `Optional` type annotations.

---

### Graph BFS (Subway) — networkx

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| networkx | >=3.2 | Subway graph BFS: shortest station count GBD/CBD/YBD | Standard Python graph library. `nx.Graph` with stations as nodes, direct connections as edges (weight=1). `nx.shortest_path_length()` runs BFS for unweighted graphs. No external API needed. |

**Graph construction approach:**
```python
import networkx as nx
G = nx.Graph()
# Add edges: (station_a, station_b) for every adjacent station pair
# Transfer stations exist as single nodes shared across lines
G.add_edge("강남", "역삼")
G.add_edge("강남", "삼성(구)", line="2")
# ...
nx.shortest_path_length(G, source="잠실", target="여의도")  # returns int hop count
```

**Data source for graph:** Use a hardcoded Python dict/adjacency list for Korean subway (Seoul metro + GTX lines in scope). GTFS public data from Seoul Open Data exists but requires preprocessing. For v1, a hardcoded adjacency list of ~400 stations covering Lines 1-9, Bundang, Sinbundang, GTX-A/B/C, and Gyeongui-Jungang is the most reliable approach — no file parsing, no network call, works offline.

**Do NOT use scipy.sparse graph algorithms.** networkx is sufficient and readable. scipy adds a large binary dependency for marginal BFS performance gains that are irrelevant at subway scale (600 nodes max).

---

### Environment / Config — python-dotenv (already in codebase)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-dotenv | >=1.1.0 | Load MOLIT_API_KEY, NAVER_CLIENT_ID/SECRET from .env | Already present in requirements.txt and used by realestate_csv.py. No change needed. |

For the standalone pipeline, use simple `os.getenv()` after `load_dotenv()` — no need for Pydantic BaseSettings which is overkill for a CLI tool without HTTP server lifecycle.

---

### Progress / Output — Rich (via Typer)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| rich | >=13.0.0 | Progress bars, colored output, tables | Typer pulls in rich as a dependency. Use `typer.echo()` for simple messages and `rich.progress.track()` for long-running collection loops across 25 구 × 240 months. |

No explicit `pip install rich` needed — Typer 0.12+ includes it as a dependency.

---

### Logging — loguru (already in codebase)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| loguru | >=0.7.2 | Structured logging for API errors, pagination state | Already in requirements.txt. Replace `print(..., file=sys.stderr)` patterns in realestate_csv.py with `logger.warning()`. Loguru's `logger.add("pipeline.log")` gives free file logging for debugging long-running collections. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| HTTP client | httpx | aiohttp | Already in codebase; aiohttp lacks sync API needed for simple scripts |
| XML parsing | stdlib ET | lxml | MOLIT XML is trivially flat; lxml adds C build dependency |
| XML parsing | stdlib ET | BeautifulSoup | HTML parser overhead, wrong tool for structured XML |
| Database | sqlite3 raw | SQLAlchemy | ORM overhead unnecessary for a batch write pipeline |
| Database | sqlite3 raw | DuckDB | Good option for analytics but breaks `pd.read_sql` pattern; not in constraints |
| DataFrame | pandas | polars | pandas has better SQLite integration; dataset within pandas comfort zone |
| CLI | typer | click | Typer is typed Click; less boilerplate for multi-command CLI |
| CLI | typer | argparse | argparse doesn't scale to subcommands cleanly |
| Graph | networkx | scipy.sparse | networkx is readable at subway scale; scipy adds large binary dependency |
| Graph | networkx | igraph | networkx has better Python API; igraph is C-extension only benefit at large scale |

---

## Installation

```bash
# New pipeline dependencies (on top of existing requirements.txt)
pip install typer>=0.12.0 networkx>=3.2 pandas>=2.0.0

# httpx, python-dotenv, loguru already in requirements.txt
```

**Full pipeline requirements addition (append to requirements.txt):**
```
# Pipeline-specific
typer>=0.12.0
networkx>=3.2
pandas>=2.0.0
```

---

## Korea-Specific API Notes

### MOLIT (국토교통부) API

- **Auth:** `serviceKey` is a URL-encoded key from data.go.kr. The portal issues it pre-encoded. Must be re-encoded before URL construction: `quote(unquote(raw_key), safe='')`.
- **serviceKey placement:** Always in URL string directly, NOT in `params={}` dict. httpx/requests re-encodes `+` chars which breaks authentication.
- **Base URL (current as of 2025):** `https://apis.data.go.kr/1613000/` (the existing code uses this correctly)
- **Pagination:** `numOfRows` (max 1000) + `pageNo`. Last page: `len(items) < numOfRows`.
- **Response:** UTF-8 XML. Field names are camelCase English (`aptNm`, `dealAmount`, `excluUseAr`).
- **HouseInfo API** (건물정보): Different endpoint family — `RTMSDataSvcAptBldMgm` — returns building coverage ratio, FAR, year built, household count, parking.
- **Rate limits:** No documented rate limit, but sequential async calls with 100ms delay are safe in practice. Parallel calls across multiple LAWD_CDs at once are fine.

### Naver Maps API (네이버 지도)

- **Auth:** `X-NCP-APIGW-API-KEY-ID` and `X-NCP-APIGW-API-KEY` request headers (not query params).
- **Directions5 endpoint** for walking distance: `https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving` (use `option=trafast` for walking approximation, or `map-direction-15/v1/driving` for 5-waypoint support).
- **Walking specifically:** Use `https://naveropenapi.apigw.ntruss.com/map-direction-15/v1/walking` endpoint if available on your plan, or Directions5 with walking mode.
- **Coordinate system:** WGS84 (lat/lng). MOLIT addresses must be geocoded first via Naver Geocoding API before routing.
- **1km cutoff rule:** If distance > 1000m, store NULL. Skip the Directions API call if geocoded straight-line distance > 1.5km (optimization to avoid API quota on clearly out-of-range pairs).
- **Quota:** Free tier = 6,000 calls/day for Directions. With ~300 apartments × ~5 nearby stations = 1,500 calls. Fits in free tier if batched carefully.

---

## Sources

- Existing codebase: `realestate_csv.py` (validated MOLIT integration pattern)
- Existing codebase: `requirements.txt` (current dependency versions)
- `.planning/codebase/INTEGRATIONS.md` (MOLIT endpoint documentation)
- Library knowledge: httpx 0.27, typer 0.12, networkx 3.x, pandas 2.x (training data through August 2025, HIGH confidence for stable libraries)
- MOLIT serviceKey encoding: validated pattern from `realestate_csv.py` line 362
