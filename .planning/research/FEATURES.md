# Feature Landscape

**Domain:** 한국 부동산 데이터 수집 파이프라인 (Korean Real Estate Data Pipeline)
**Researched:** 2026-03-17T05:30:22Z
**Confidence:** HIGH (based on existing codebase + MOLIT API domain knowledge)

---

## Context: What Already Exists

The existing `realestate_csv.py` provides a working foundation:

- MOLIT API integration with `serviceKey` URL-safe encoding (critical: must use `quote(unquote(key), safe='')`)
- `LAWD_CD` (5-digit 지역코드) resolution from address strings
- Full pagination loop (`numOfRows=1000`, increments `pageNo` until `len(items) < page_size`)
- Apartment name fuzzy matching (strip "아파트" suffix, partial match both directions)
- XML parsing via `ET.fromstring()` traversing `.//item` elements
- CSV output with normalized column names

The new pipeline replaces CSV output with SQLite and adds 4 new data collection features.

---

## Table Stakes

Features that must exist for the pipeline to be useful. Missing any = incomplete product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 매매 실거래가 수집 (지역구 전체) | 핵심 투자 데이터 | Medium | 기존 코드 재사용, CSV 입력 제거하고 지역구 단위 자동 스캔으로 전환 |
| 전세가 수집 (지역구 전체) | 전세가율 분석의 기반 | Medium | MOLIT `getRTMSDataSvcAptRent` API, 기존 코드 재사용 |
| 아파트 단지 목록 자동 확보 | CSV 입력 없이 지역구 내 전체 단지 수집 | Medium | MOLIT API 응답에서 `aptNm` + `umdNm` + `jibun` 조합으로 단지 식별 |
| SQLite 적재 | pandas/대시보드/CSV 내보내기 공통 기반 | Low | Python 내장 `sqlite3`, 별도 서버 불필요 |
| 지역코드(LAWD_CD) 관리 | 모든 API 호출의 키 파라미터 | Low | 기존 `SIGUNGU_MAP` 확장: 분당구(41175), 과천시(41390), 하남시(41550), 안양시 동안구(41220) |
| CLI 인터페이스 | 수동 실행 운영 | Low | `argparse` 기반, 지역/기간/수집항목 선택 |
| 월별 집계 (최저/최고/평균, 거래건수) | 원시 건당 데이터보다 분석에 직접 유용 | Low | 수집 후 SQLite GROUP BY로 계산, 또는 수집 시 집계 |
| API rate-limit 대응 | MOLIT API는 초당 10건 제한, 과도한 호출 시 차단 | Medium | `asyncio.sleep(0.1)` 또는 semaphore로 동시성 제한 |
| 중복 적재 방지 | 재실행 시 데이터 중복 누적 방지 | Low | SQLite `INSERT OR REPLACE` 또는 `INSERT OR IGNORE` with unique index |
| 진행상황 출력 | 수천 건 수집 시 진행 확인 필요 | Low | `tqdm` 또는 단순 print 카운터 |

---

## Differentiators

Features that make this pipeline analytically superior to raw MOLIT API data.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 지하철 도보 거리 (Naver Maps) | 역세권 분석의 핵심, 직선거리가 아닌 실제 도보 경로 | Medium | Naver Directions5 API, 1km 초과 시 NULL 저장 (의미없는 역 제외) |
| GBD/CBD/YBD 최단 정거장 수 (BFS) | 업무지구 접근성 = 직장인 수요와 직결 | High | 전국 지하철 그래프 내장 + BFS/Dijkstra, 환승 포함, 인접행렬로 표현 |
| 건물정보 통합 (건폐율, 용적률, 세대수, 주차) | 단지 품질 판별, 재건축 가능성 평가 기반 | Medium | MOLIT `getBrBasisOulnInfo` API (건축물대장 기반), 법정동코드 + 지번 필요 |
| 평형 단위 표준화 (㎡ → 평) | 한국 시장에서 평형이 직관적 단위 | Low | `pyeong = area_sqm / 3.3058`, 소수점 없는 정수 평형으로 버킷화 (e.g., 24평, 32평) |
| 전세가율 자동 계산 | 매매가 대비 전세가 비율 = 투자 안정성 지표 | Low | SQLite 뷰(VIEW)로 매매/전세 테이블 JOIN |
| 다기간 시계열 보관 (2006년~현재) | 장기 시세 추이 분석 가능 | Low | MOLIT API는 2006년부터 제공, `--start 200601` 옵션으로 전체 이력 수집 |
| 수집 이력 관리 (마지막 수집 월 추적) | 재실행 시 미수집 월만 추가 수집 | Low | `collection_log` 테이블에 `(lawd_cd, deal_ymd, data_type, collected_at)` 기록 |

---

## Anti-Features

Features to explicitly NOT build in v1.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| 실시간 데이터 수집 | MOLIT 실거래 데이터 자체가 1-2개월 지연 게시, 실시간 의미 없음 | 월별 배치 수집으로 충분 |
| 스케줄링/크론 자동화 | v1은 수동 실행으로 충분, 복잡도 증가 | 나중에 cron 또는 GitHub Actions 추가 |
| 웹 대시보드 구현 | SQLite + pandas로 분석 가능, UI는 별도 프로젝트 | Streamlit 등 별도 연동 |
| 서울/경기 5개 지역 외 확장 | 범위 폭발, 지역 추가는 단순 설정 변경으로 가능 | `REGIONS` 설정에 LAWD_CD 추가만으로 확장 가능하도록 설계 |
| 오피스텔/연립다세대 수집 | 아파트 분석에 집중, 데이터 혼재 방지 | 별도 데이터 타입으로 향후 추가 가능 |
| Naver Maps로 정거장 수 계산 | API 비용 발생, 정거장 수는 그래프 BFS가 더 정확하고 무료 | BFS 그래프 내장 |
| PostgreSQL/MySQL 사용 | 배포 복잡도 증가, SQLite면 충분 | SQLite (분석용 파일 DB) |
| 아파트 이미지/사진 수집 | 저장 용량, API 복잡도 대비 분석 가치 낮음 | 텍스트 메타데이터만 수집 |
| 실거래가 건당 원본 보관 + 별도 집계 | 건당 데이터는 용량이 크고 분석 효율 낮음 | 집계(평균/최저/최고/건수)만 SQLite에 보관 |

---

## Korea-Specific Data Quirks

### MOLIT API 응답 필드명 (실거래가 매매 - `getRTMSDataSvcAptTradeDev`)

```
aptNm      → 아파트명 (예: "은마")
excluUseAr → 전용면적 ㎡ (소수점 있음, 예: "84.9")
dealAmount → 거래금액 만원 (쉼표 포함, 예: "130,000" = 13억)
dealYear   → 계약년 (예: "2024")
dealMonth  → 계약월 (예: "1")
dealDay    → 계약일 (예: "15")
floor      → 층 (예: "12")
buildYear  → 건축년도 (예: "1979")
umdNm      → 법정동명 (예: "대치동")
jibun      → 지번 (예: "901")
roadNm     → 도로명 (예: "남부순환로")
aptDong    → 동 (예: "101동")
dealingGbn → 거래구분 (예: "중개거래", "직거래")
```

### MOLIT API 응답 필드명 (전세 - `getRTMSDataSvcAptRent`)

```
deposit     → 보증금 만원 (쉼표 포함)
monthlyRent → 월세 만원 (전세이면 "0")
leaseType   → 임차유형 (전세/월세 구분)
```

### 지역코드(LAWD_CD) 특이사항

- 5자리 시군구 코드 (법정동 코드 앞 5자리)
- 위례(하남시): `41550` (하남시 전체, 위례신도시가 하남시에 포함)
- 인덕원(안양시 동안구): `41220`
- 분당구(성남시): `41175` (성남시 수정구 41171, 중원구 41173과 구분 필요)
- 과천시: `41390`
- MOLIT API의 `LAWD_CD` 파라미터는 5자리, 일부 문서에서 10자리 법정동코드와 혼동 주의

### 평형(坪) 단위 변환

- `1평 = 3.3058㎡` (정확값: 3.30578512396694㎡)
- 한국 부동산 시장은 전용면적(㎡) 기준이지만, 일반적 소통은 평형 기준
- API 응답은 항상 ㎡ 기준 → 저장 시 둘 다 보관 권장
- 평형 버킷화: `int(excluUseAr / 3.3)` → 소수점 버림 (예: 84.9㎡ → 25평)
- 표준 평형 구간: 소형(~20평), 중형(21~35평), 대형(36평~)

### 전세가율(Jeonse Rate)

- `전세가율 = 전세보증금 / 매매가 × 100 (%)`
- 70% 이상이면 갭투자 위험 높음
- 50% 이하면 투자 안정성 높음
- 지역별 평균 전세가율이 투자 지표로 활용됨

### GBD/CBD/YBD 업무지구 정의

- **CBD** (City Business District, 도심권): 종로구/중구 — 종각역(1호선) 기준
- **GBD** (Gangnam Business District, 강남권): 강남구/서초구 — 강남역(2호선/신분당선) 기준
- **YBD** (Yeouido Business District, 여의도권): 영등포구 여의도 — 여의도역(5호선/9호선) 기준
- 정거장 수 = 환승 포함 BFS 최단 경로 (이동시간 아님)
- 환승역 통과 시 `+1 stop` 카운팅 (환승 자체에 추가 카운트 없음)

---

## Feature Dependencies

```
아파트 단지 목록 확보
  → 매매가 수집 (단지별 집계를 위해 단지 식별 필요)
  → 전세가 수집 (동일)
  → 건물정보 수집 (법정동코드 + 지번 필요, 실거래 응답에서 확보)
  → 지하철 도보 거리 (아파트 좌표 필요 → Naver Geocoding 선행)

Naver Geocoding (주소 → 좌표)
  → 지하철 도보 거리 (Naver Directions5 API)
  → GBD/CBD/YBD 정거장 수 계산에서는 불필요 (그래프 BFS)

지하철 노선 그래프 내장
  → GBD/CBD/YBD 최단 정거장 수 (BFS)
  → 가장 가까운 역 식별 (Haversine 거리 기반 역 선택 → BFS 시작점)

SQLite 스키마 확정
  → 모든 수집 기능 (적재 대상 테이블이 존재해야 함)
```

---

## SQLite Schema Recommendations

### 핵심 설계 원칙

1. 원시 건당 데이터보다 집계 데이터 보관 (용량 효율)
2. 아파트 단지를 `apartments` 마스터 테이블로 정규화
3. 모든 금액은 만원(KRW) 정수로 저장 (소수점 없음)
4. 면적은 ㎡(실수)와 평(정수) 둘 다 컬럼 보관
5. NULL 허용: 지하철 1km 초과 시 NULL, 데이터 미수집 시 NULL

### 권장 스키마

```sql
-- 아파트 단지 마스터
CREATE TABLE apartments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lawd_cd     TEXT NOT NULL,          -- 5자리 지역코드
    sido        TEXT NOT NULL,          -- 시/도 (서울특별시, 경기도)
    sigungu     TEXT NOT NULL,          -- 시군구 (강남구, 분당구)
    umd_nm      TEXT NOT NULL,          -- 법정동명 (대치동)
    jibun       TEXT,                   -- 지번 (901)
    road_nm     TEXT,                   -- 도로명
    apt_nm      TEXT NOT NULL,          -- 아파트명 (은마)
    apt_dong    TEXT,                   -- 동 (101동)
    lat         REAL,                   -- 위도 (Naver Geocoding)
    lon         REAL,                   -- 경도
    build_year  INTEGER,                -- 건축년도
    -- 건물정보 (MOLIT HouseInfo API)
    floor_area_ratio    REAL,           -- 용적률 (%)
    building_coverage   REAL,           -- 건폐율 (%)
    total_households    INTEGER,        -- 세대수
    parking_count       INTEGER,        -- 주차대수
    -- 지하철 접근성
    nearest_station_name    TEXT,       -- 가장 가까운 역명
    nearest_station_line    TEXT,       -- 호선 (2호선, 신분당선)
    nearest_station_walk_m  INTEGER,    -- 도보 거리 (미터), 1km 초과 시 NULL
    -- 업무지구 접근성 (BFS 정거장 수)
    stops_to_cbd    INTEGER,            -- 종각역까지 최단 정거장 수
    stops_to_gbd    INTEGER,            -- 강남역까지 최단 정거장 수
    stops_to_ybd    INTEGER,            -- 여의도역까지 최단 정거장 수
    -- 메타
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(lawd_cd, umd_nm, jibun, apt_nm)
);

-- 월별 매매가 집계
CREATE TABLE trade_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id    INTEGER NOT NULL REFERENCES apartments(id),
    deal_ym         TEXT NOT NULL,      -- YYYYMM (202401)
    area_sqm        REAL NOT NULL,      -- 전용면적 ㎡
    area_pyeong     INTEGER NOT NULL,   -- 전용면적 평 (int)
    price_min       INTEGER NOT NULL,   -- 최저 거래가 (만원)
    price_max       INTEGER NOT NULL,   -- 최고 거래가 (만원)
    price_avg       INTEGER NOT NULL,   -- 평균 거래가 (만원)
    deal_count      INTEGER NOT NULL,   -- 거래건수
    created_at      TEXT NOT NULL,
    UNIQUE(apartment_id, deal_ym, area_pyeong)
);

-- 월별 전세가 집계
CREATE TABLE rent_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id    INTEGER NOT NULL REFERENCES apartments(id),
    deal_ym         TEXT NOT NULL,      -- YYYYMM
    area_sqm        REAL NOT NULL,      -- 전용면적 ㎡
    area_pyeong     INTEGER NOT NULL,   -- 전용면적 평
    deposit_min     INTEGER NOT NULL,   -- 최저 전세보증금 (만원)
    deposit_max     INTEGER NOT NULL,   -- 최고 전세보증금 (만원)
    deposit_avg     INTEGER NOT NULL,   -- 평균 전세보증금 (만원)
    deal_count      INTEGER NOT NULL,   -- 거래건수
    created_at      TEXT NOT NULL,
    UNIQUE(apartment_id, deal_ym, area_pyeong)
);

-- 수집 이력 (재실행 시 미수집 월만 추가)
CREATE TABLE collection_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lawd_cd     TEXT NOT NULL,
    deal_ym     TEXT NOT NULL,          -- YYYYMM
    data_type   TEXT NOT NULL,          -- trade | rent | building
    status      TEXT NOT NULL,          -- success | error | empty
    record_count INTEGER,
    collected_at TEXT NOT NULL,
    UNIQUE(lawd_cd, deal_ym, data_type)
);

-- 분석용 뷰: 전세가율
CREATE VIEW jeonse_rate AS
SELECT
    a.sigungu,
    a.apt_nm,
    t.area_pyeong,
    t.deal_ym,
    t.price_avg AS trade_avg,
    r.deposit_avg AS rent_avg,
    ROUND(CAST(r.deposit_avg AS REAL) / t.price_avg * 100, 1) AS jeonse_rate_pct
FROM trade_prices t
JOIN apartments a ON t.apartment_id = a.id
LEFT JOIN rent_prices r ON r.apartment_id = t.apartment_id
    AND r.deal_ym = t.deal_ym
    AND r.area_pyeong = t.area_pyeong
WHERE t.price_avg > 0;
```

### 인덱스 권장

```sql
CREATE INDEX idx_trade_apt_ym ON trade_prices(apartment_id, deal_ym);
CREATE INDEX idx_rent_apt_ym ON rent_prices(apartment_id, deal_ym);
CREATE INDEX idx_apt_lawd ON apartments(lawd_cd);
CREATE INDEX idx_apt_name ON apartments(sigungu, apt_nm);
CREATE INDEX idx_collection_log ON collection_log(lawd_cd, deal_ym, data_type);
```

---

## MVP Recommendation

**Phase 1 (최우선):** 데이터 기반 확보

1. SQLite 스키마 생성 (`apartments`, `trade_prices`, `rent_prices`, `collection_log`)
2. 매매가 수집: 5개 지역 × 전체 월 → `trade_prices` 적재
3. 전세가 수집: 5개 지역 × 전체 월 → `rent_prices` 적재
4. 아파트 단지 자동 등록: 수집 중 `apartments` 마스터 테이블 upsert
5. CLI 기본: `--regions`, `--start`, `--end`, `--types` 옵션

**Phase 2:** 위치 데이터 보강

6. Naver Geocoding으로 `apartments.lat/lon` 확보
7. 지하철 도보 거리 수집 → `apartments.nearest_station_*` 업데이트
8. 지하철 그래프 내장 + BFS로 GBD/CBD/YBD 정거장 수 계산

**Phase 3 (완성):** 건물정보 + 분석 뷰

9. MOLIT 건축물대장 API로 건물정보 수집
10. `jeonse_rate` 뷰 및 CSV 내보내기 기능

**Defer (v1 범위 외):**

- 스케줄링 자동화 (cron/GitHub Actions)
- 웹 대시보드 (Streamlit 별도 프로젝트)
- 서울/경기 5개 지역 외 지역 확장

---

## Sources

- 기존 코드 `realestate_csv.py`: MOLIT API 연동 패턴, 지역코드 매핑, XML 파싱 — HIGH confidence
- 기존 코드 `app/mcp/fastmcp_realestate.py`: MOLIT 엔드포인트 URL 패턴 — HIGH confidence
- 기존 코드 `app/mcp/location_service.py`: Naver Maps API 통합 패턴, Haversine 계산 — HIGH confidence
- 기존 코드 `app/agent/real_estate_agent.py`: 평형 단위 변환(3.3 divisor), 역세권 정의(500m/1km) — HIGH confidence
- 도메인 지식: GBD/CBD/YBD 업무지구 정의, 전세가율 개념, 법정동코드 체계 — MEDIUM confidence (training data, but well-established Korean RE conventions)
- MOLIT API 필드명: 기존 코드 `normalize_trade_row()` 함수에서 직접 확인 — HIGH confidence
