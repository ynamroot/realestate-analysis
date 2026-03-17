# Project Research Summary

**Project:** 한국 부동산 데이터 수집 파이프라인 (Korean Real Estate Data Collection Pipeline)
**Domain:** Government API data pipeline with geospatial enrichment
**Researched:** 2026-03-17T05:35:39Z
**Confidence:** HIGH

## Executive Summary

This project is a brownfield CLI pipeline that replaces the existing `realestate_csv.py` script's CSV-based workflow with a structured SQLite backend while adding four new data dimensions: building information (coverage ratio, FAR, household count), walking distance to nearby subway stations via Naver Maps, BFS-computed commute stops to Seoul's three major business districts (GBD/CBD/YBD), and a persistent collection log for incremental re-runs. The existing codebase provides high-confidence, already-validated patterns for MOLIT API integration — critically the `serviceKey` URL-encoding fix and pagination loop — which must be preserved exactly when porting to the new `pipeline/` package structure.

The recommended approach is a six-phase build starting with SQLite schema and storage infrastructure, then layering MOLIT trade/rent collection, building metadata, Naver Maps geocoding and walking distance, subway BFS graph, and finally the Typer CLI and orchestrator. This ordering is driven by hard data dependencies: the `apartments` master table must exist before any FK-referencing table can receive data, and apartment coordinates (from Naver Geocoding) must exist before the Direction5 API can be called. Keeping the new `pipeline/` package entirely separate from the existing FastAPI `app/` avoids any risk of breaking the current A2A agent service.

The most consequential risks are all concentrated in Phase 1: the MOLIT `serviceKey` double-encoding bug (causes 100% silent 401 failures), the XML camelCase field naming gap (causes silent zero-value storage for all price data), and the lack of HTTP-200 error body detection (API errors appear as empty result sets). A second cluster of risks sits in Phase 4: the BFS subway graph must be built from GTFS data rather than the partial 35-station hardcoded list in the current `location_service.py`, and walking distances must use the Naver Direction5 routing API rather than haversine straight-line calculation. Addressing these six pitfalls before writing any aggregation or analysis logic prevents silent data corruption that is difficult to detect after the fact.

---

## Key Findings

### Recommended Stack

The full stack leverages the existing codebase dependencies wherever possible, adding only three new packages: `typer>=0.12.0` for multi-command CLI, `networkx>=3.2` for subway BFS, and `pandas>=2.0.0` for aggregation and CSV export. The existing `httpx`, `python-dotenv`, and `loguru` packages cover all remaining needs. No ORM (SQLAlchemy), no alternative HTTP client (aiohttp), and no columnar store (DuckDB or polars) are needed.

**Core technologies:**
- `httpx>=0.27.0`: MOLIT + Naver Maps API calls — already in codebase, sync and async interfaces, critical `serviceKey` URL-building pattern already validated
- `xml.etree.ElementTree` (stdlib): MOLIT XML parsing — MOLIT responses are trivially flat `<item>` lists, zero dependency overhead
- `sqlite3` (stdlib): Primary data store — explicitly required by PROJECT.md, no server, file-portable, native pandas integration
- `pandas>=2.0.0`: Monthly aggregation and CSV export — `read_sql()` + `to_csv(encoding='utf-8-sig')` for Excel-compatible Korean output
- `typer>=0.12.0`: CLI with subcommands (`collect`, `export`, `status`) — typed Click wrapper, generates `--help` with Korean strings, Rich progress bars included
- `networkx>=3.2`: Subway BFS for GBD/CBD/YBD stop counts — `nx.Graph` with station nodes, `shortest_path_length()` for unweighted BFS
- `loguru>=0.7.2`: Structured logging — already in codebase, file logging with `logger.add("pipeline.log")`

### Expected Features

**Must have (table stakes):**
- 매매 실거래가 수집 (전체 지역구, 월별) — core investment data; reuses existing MOLIT integration
- 전세가 수집 (전체 지역구, 월별) — basis for jeonse rate calculation
- 아파트 단지 자동 등록 — district-scan mode eliminates CSV input; `aptNm + umdNm + jibun` as unique key
- SQLite storage with `apartments`, `trade_prices`, `rent_prices`, `collection_log` tables
- 지역코드(LAWD_CD) mapping for 5 target regions: 강남구(11680), 분당구(41175), 과천시(41390), 하남시(41550), 동안구(41220)
- 월별 집계: min/max/avg price and deal count per apartment per area bucket per month
- 중복 방지: `INSERT OR REPLACE` with UNIQUE indexes — idempotent re-runs
- API rate-limit handling: `asyncio.sleep(0.1)` + semaphore for concurrent district fetches
- 진행상황 출력: Rich progress bars via Typer

**Should have (differentiators):**
- 지하철 도보 거리 (Naver Direction5 API) — actual routed walking distance, not straight-line; NULL if >1km
- GBD/CBD/YBD 최단 정거장 수 (BFS) — commute accessibility score; free, no API quota
- 건물정보 통합 (MOLIT HouseInfo API) — coverage ratio, FAR, household count, parking
- 평형 단위 표준화 (㎡ → 평) — store both; `int(area_sqm / 3.3)` for integer pyeong bucket
- 전세가율 자동 계산 — SQLite VIEW joining trade and rent tables
- 다기간 시계열 (2006~현재) — MOLIT provides data from 2006; `--start 200601` option
- 수집 이력 관리 — `collection_log` table tracks last-collected month per region/type

**Defer (v2+):**
- 스케줄링 자동화 (cron / GitHub Actions)
- 웹 대시보드 (Streamlit — separate project)
- 서울/경기 5개 지역 외 확장 (config-only change when ready)
- 오피스텔/연립다세대 수집
- 실시간 수집 (MOLIT data has 1-2 month lag; meaningless)

### Architecture Approach

The new `pipeline/` package is a standalone addition at the repo root, sharing only `.env` configuration with the existing `app/` FastAPI service. The architecture follows a layered collector → processor → storage pattern with a thin orchestrator coordinating execution order. All external API calls are isolated in `collectors/`, all pure computation in `processors/`, and all SQLite interaction in `storage/`. The Naver Maps result cache is stored in SQLite itself (the `subway_distances` table), avoiding redundant API calls on re-runs.

**Major components:**
1. `pipeline/cli.py` — Typer CLI entry point; parses `--regions`, `--start`, `--end`, `--collect` options
2. `pipeline/orchestrator.py` — Coordinates collector execution order; enforces dependency sequencing
3. `collectors/molit_trade.py` — MOLIT trade/rent API; async + semaphore; full pagination loop
4. `collectors/molit_house_info.py` — MOLIT building registry API; populates `apartments` building columns
5. `collectors/naver_distance.py` — Naver Direction5 walking distance; DB-cache-first pattern; NULL if >1km
6. `processors/price_aggregator.py` — Groups raw trade records into monthly min/max/avg/count aggregates
7. `processors/subway_graph.py` — GTFS-sourced BFS graph; physical station grouping via `parent_station`
8. `storage/schema.py + db.py + repository.py` — SQLite DDL, WAL-mode connection, upsert helpers

### Critical Pitfalls

1. **MOLIT serviceKey double-encoding** — Embed the pre-encoded key directly in the URL string; never use `params={"serviceKey": key}`. httpx re-encodes `+` as `%2B`, causing 401. Fix already exists in `realestate_csv.py` line 362 — copy exactly.

2. **MOLIT XML uses camelCase English field names** — `aptNm`, `dealAmount`, `excluUseAr`, not Korean keys. Silent zero values if Korean keys are used. `dealAmount` contains comma separators ("55,000") requiring `.replace(",", "")` before `int()`.

3. **HTTP 200 with error body** — MOLIT and all Korean public data APIs return HTTP 200 for errors. Parse `<resultCode>` before processing `<items>`. Code `30` = invalid key; code `22` = rate limit (needs backoff, not retry).

4. **Pagination truncation at 1,000 rows** — High-volume districts (강남구) exceed 1,000 transactions per month. Single-page calls silently truncate data. Must loop `pageNo` until `len(items) < numOfRows`. Already implemented in `fetch_trades()` — preserve this.

5. **BFS graph completeness** — The current `location_service.py` `SUBWAY_STATIONS` dict contains ~35 stations. This is a demonstration stub. The pipeline must load from Seoul Metro GTFS data (data.seoul.go.kr) and group stops by `parent_station` to avoid counting transfers as hops.

6. **Walking distance vs straight-line** — `location_service.py` uses haversine. For the 1km cutoff classification, haversine underestimates distances near rivers and elevated roads. Must use Naver Direction5 walking endpoint. Cache results in `subway_distances` table (NULL included) to avoid re-calling.

---

## Implications for Roadmap

Based on research, the architecture's data dependency chain directly dictates phase order. No phase can begin until its upstream dependency is complete.

### Phase 1: Foundation — Storage + Config + MOLIT Client
**Rationale:** Every subsequent collector writes to SQLite; the DB schema must exist first. The MOLIT client bugs (serviceKey encoding, pagination, XML field mapping, HTTP-200 error detection) must be solved at the base layer or they corrupt every phase above.
**Delivers:** Working SQLite schema with all tables and indexes; config module with LAWD_CD map; base MOLIT HTTP client with serviceKey fix, pagination, resultCode check, and camelCase field mapping; dealAmount comma stripping.
**Addresses:** Table stakes features — SQLite storage, LAWD_CD management, 중복 방지
**Avoids:** Pitfalls 1 (serviceKey encoding), 2 (camelCase fields), 6 (pagination truncation), 11 (HTTP-200 errors), 12 (LAWD_CD granularity), 13 (comma-format numbers), 14 (data lag), 15 (encoding)

### Phase 2: Core Data Collection — Trade + Rent + Apartment Roster
**Rationale:** Trade and rent collection populate the `apartments` master table as a side effect — apartment IDs created here are FK referenced by all subsequent phases. Cannot build building info, subway, or BFS until apartments exist.
**Delivers:** `trade_prices` and `rent_prices` populated for all 5 regions from 2006 to previous month; `apartments` table with base attributes (lawd_cd, apt_nm, umd_nm, jibun); `collection_log` entries; price aggregator producing monthly min/max/avg/count.
**Uses:** httpx async + semaphore, xml.etree.ElementTree, pandas groupby, sqlite3 executemany
**Implements:** `collectors/molit_trade.py`, `processors/price_aggregator.py`, `storage/repository.py`
**Avoids:** Pitfall 3 (apartment name normalization for deduplication across months), Pitfall 7 (executemany bulk insert), Pitfall 8 (composite indexes)

### Phase 3: Building Information
**Rationale:** MOLIT HouseInfo API enriches `apartments` rows that already exist. Requires apartment IDs from Phase 2. Independent of geocoding and BFS.
**Delivers:** `apartments` rows updated with `build_year`, `total_households`, `floor_area_ratio`, `building_coverage_ratio`, `parking_count`
**Uses:** MOLIT `getBrBasisOulnInfo` API (건축물대장), same httpx + XML pattern
**Implements:** `collectors/molit_house_info.py`

### Phase 4: Geolocation + Walking Distance
**Rationale:** Naver Geocoding converts apartment addresses to coordinates; coordinates are prerequisite for Naver Direction5 walking distance calls. Validate Naver credentials before writing any collection code (IAM vs Application key pitfall).
**Delivers:** `apartments.lat/lon` populated via Naver Geocoding; `subway_distances` table populated with walking distances (NULL if >1km) for the nearest candidate stations per apartment
**Uses:** Naver Maps Geocoding API + Direction5 API, SQLite cache-first pattern
**Implements:** `collectors/naver_distance.py`
**Avoids:** Pitfall 4 (IAM vs Application credentials — add startup check), Pitfall 5 (use routing API not haversine)

### Phase 5: Subway BFS — Commute Stop Counts
**Rationale:** Requires `subway_distances` nearest-station data from Phase 4 as BFS start points. The GTFS graph must be loaded and validated before implementing BFS logic to avoid the partial-station-list pitfall.
**Delivers:** `commute_stops` table populated with GBD/CBD/YBD stop counts per apartment; `stops_to_gbd`, `stops_to_cbd`, `stops_to_ybd` fields set on `apartments`
**Uses:** networkx BFS on GTFS-sourced graph; Seoul Metro GTFS from data.seoul.go.kr
**Implements:** `processors/subway_graph.py`, `pipeline/data/subway_graph.json`
**Avoids:** Pitfall 9 (partial hardcoded station list), Pitfall 10 (platform vs physical station — use `parent_station` grouping)

### Phase 6: CLI + Orchestrator + Analysis Views
**Rationale:** All data exists by now; the CLI and orchestrator are a coordination layer, not a data layer. Typer subcommands, progress bars, and the jeonse rate view are finishing touches.
**Delivers:** `pipeline/cli.py` with `collect`, `export`, `status` subcommands; `pipeline/orchestrator.py` coordinating Phases 2-5; `jeonse_rate` SQLite VIEW; CSV export with `utf-8-sig` encoding
**Uses:** Typer 0.12+, Rich progress bars, pandas `to_csv(encoding='utf-8-sig')`
**Implements:** `pipeline/cli.py`, `pipeline/orchestrator.py`

### Phase Ordering Rationale

- Schema before collectors: every table has FKs to `apartments`; schema must exist before any insert
- Apartments before building info: MOLIT HouseInfo uses apartment `(lawd_cd, jibun)` pairs discovered during trade collection
- Geocoding before walking distance: Direction5 API requires lat/lon coordinates
- Walking distance before BFS: nearest station (start node for BFS) comes from `subway_distances`
- All data before CLI: orchestrator needs all phases working end-to-end before wiring them together
- Pitfall cluster mitigation: all six critical pitfalls are fixed in Phases 1-2 before any derived computation runs

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Naver Maps):** Naver API quota tiers and exact walking endpoint URL need verification against current NCP documentation (2026 pricing may differ from training data)
- **Phase 5 (GTFS):** Seoul Metro GTFS file structure and `parent_station` coverage for GTX-A/B/C lines needs validation against the actual published dataset before graph construction begins

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** All MOLIT patterns are confirmed from existing codebase; no new research needed
- **Phase 2 (Trade/Rent):** Core logic is a port of validated `realestate_csv.py` code
- **Phase 3 (Building Info):** Same MOLIT HTTP pattern as Phase 2; endpoint is documented
- **Phase 6 (CLI):** Typer 0.12 patterns are well-documented and stable

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core technologies already in codebase and validated; only 3 new additions |
| Features | HIGH | Derived from direct codebase analysis and MOLIT domain; field names confirmed in existing normalize functions |
| Architecture | HIGH | Direct analysis of existing code; component boundaries and data flow are concrete, not speculative |
| Pitfalls | HIGH (critical 1-6, 11-14) / MEDIUM (7-10) | Critical pitfalls confirmed by existing codebase evidence; SQLite performance and GTFS patterns are well-established standards |

**Overall confidence:** HIGH

### Gaps to Address

- **Naver Direction5 walking endpoint URL:** The exact endpoint for pedestrian routing in NCP 2026 needs verification. `location_service.py` uses the driving endpoint. Confirm walking mode URL before Phase 4 implementation.
- **Naver API free tier limits:** Direction5 free quota (1,000 calls/day vs 6,000/day for Geocoding) needs checking against current NCP pricing. With ~300 apartments × 5 stations = 1,500 calls, paid tier may be needed for full dataset.
- **GTFS GTX line coverage:** Seoul Metro GTFS may not include GTX-A/B/C lines (operated by SRT/Korail). May require supplemental Korail GTFS or manual adjacency entries for GTX stations.
- **MOLIT HouseInfo API LAWD_CD parameter format:** `getBrBasisOulnInfo` may require 10-digit `법정동코드` rather than 5-digit `LAWD_CD`. Confirm parameter format before Phase 3 implementation.

---

## Sources

### Primary (HIGH confidence)
- `realestate_csv.py` — MOLIT serviceKey encoding, pagination loop, XML parsing, field mapping, apartment name normalization, LAWD_CD mapping
- `app/mcp/location_service.py` — Naver IAM credential detection, haversine usage, partial subway station list
- `app/mcp/fastmcp_realestate.py` — MOLIT endpoint URLs, HTTP-200 error handling patterns
- `app/agent/real_estate_agent.py` — pyeong conversion factor (3.3),역세권 distance thresholds
- `.planning/PROJECT.md` — Feature requirements, SQLite constraint, target regions

### Secondary (MEDIUM confidence)
- Library knowledge (training data through August 2025): httpx 0.27, typer 0.12, networkx 3.x, pandas 2.x — stable APIs
- Korean real estate domain conventions: jeonse rate thresholds, GBD/CBD/YBD definitions, pyeong conversion
- Korean public data portal API behavior: HTTP-200 error pattern, resultCode conventions

### Tertiary (needs validation during implementation)
- Naver Maps NCP 2026 API quota and walking endpoint URL
- Seoul Metro GTFS GTX line coverage (data.seoul.go.kr)
- MOLIT HouseInfo API parameter format for 5-digit vs 10-digit region codes

---
*Research completed: 2026-03-17T05:35:39Z*
*Ready for roadmap: yes*
