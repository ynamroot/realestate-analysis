# Architecture Patterns

**Domain:** 한국 부동산 데이터 수집 파이프라인
**Researched:** 2026-03-17
**Confidence:** HIGH (derived from direct codebase analysis + domain knowledge of MOLIT/Naver APIs)

---

## Recommended Architecture

This is a **brownfield extension** of the existing `realestate_csv.py`. The new pipeline lives as a
standalone `pipeline/` package at the repo root, completely independent of the FastAPI A2A application
in `app/`. The two systems share only `.env` configuration.

### High-Level Component Map

```
CLI (pipeline/cli.py)
        │
        ├─── Orchestrator (pipeline/orchestrator.py)
        │         │
        │         ├── collectors/
        │         │     ├── molit_trade.py      # 매매/전세 실거래가 (MOLIT API)
        │         │     ├── molit_house_info.py # 건물정보 (MOLIT HouseInfo API)
        │         │     └── naver_distance.py   # 도보 거리 (Naver Maps API)
        │         │
        │         ├── processors/
        │         │     ├── region_resolver.py  # 주소 → LAWD_CD (from realestate_csv.py)
        │         │     ├── price_aggregator.py # 월별 통계 집계 (min/max/avg/count)
        │         │     └── subway_graph.py     # 전국 지하철 그래프 + BFS
        │         │
        │         └── storage/
        │               ├── db.py               # SQLite 연결/마이그레이션
        │               ├── schema.py           # CREATE TABLE 정의
        │               └── repository.py       # upsert/query helpers
        │
        └── pipeline/config.py                  # .env 로딩, API 키, 지역 목록
```

### Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| `cli.py` | argparse 진입점, 사용자 옵션 파싱 | CLI args | — | orchestrator |
| `orchestrator.py` | 수집 순서 조율, 진행 출력 | config | — | all collectors, processors, storage |
| `collectors/molit_trade.py` | MOLIT 실거래가 API 호출, XML 파싱 | lawd_cd, deal_ymd | List[dict] | MOLIT API (HTTP) |
| `collectors/molit_house_info.py` | MOLIT HouseInfo API 호출 | lawd_cd | List[dict] | MOLIT API (HTTP) |
| `collectors/naver_distance.py` | Naver Maps Directions API 호출 | apt coords, station coords | float (meters) | Naver API (HTTP), SQLite cache |
| `processors/region_resolver.py` | 주소 → LAWD_CD 변환 (재사용 from realestate_csv.py) | address string | str LAWD_CD | — |
| `processors/price_aggregator.py` | 원시 거래 records → 평형별 월별 통계 | List[dict] raw trades | List[dict] aggregated | — |
| `processors/subway_graph.py` | 전국 지하철 그래프 BFS, GBD/CBD/YBD 최단 정거장 수 | station_id | int stops | — |
| `storage/db.py` | SQLite 연결, WAL 모드, 마이그레이션 실행 | db_path | Connection | — |
| `storage/schema.py` | DDL 정의 (CREATE TABLE IF NOT EXISTS) | — | SQL strings | db.py |
| `storage/repository.py` | INSERT OR REPLACE, 조회 헬퍼 | orm-like dicts | — | db.py |
| `config.py` | .env 로딩, 대상 지역 목록 상수 | .env file | Settings object | all |

---

## Data Flow

### 전체 파이프라인 흐름

```
1. CLI 파싱
   └─ --region, --start, --end, --collect [trade|rent|subway|building|all]

2. region_resolver: 지역구 → LAWD_CD 목록
   └─ SIGUNGU_MAP (from realestate_csv.py, 재사용)

3. molit_trade collector (지역구 × 월 루프)
   └─ MOLIT API → XML → parse → List[raw_trade_dict]
   └─ price_aggregator → 평형별 월별 min/max/avg/count
   └─ repository.upsert_monthly_prices()

4. molit_house_info collector (지역구별)
   └─ MOLIT HouseInfo API → 단지 목록 (건폐율/용적률/세대수/주차)
   └─ repository.upsert_apartments() + upsert_building_info()

5. naver_distance collector (아파트 × 인근 지하철역)
   └─ 캐시 체크 (subway_distances 테이블)
   └─ 캐시 miss → Naver Maps API → 도보 거리(m)
   └─ 1000m 초과 → null 저장, 포함 안 함
   └─ repository.upsert_subway_distance()

6. subway_graph processor (아파트별)
   └─ 내장 전국 노선 그래프 로딩 (JSON or hardcoded dict)
   └─ BFS (출발역 → GBD/CBD/YBD 환승역 포함)
   └─ repository.upsert_commute_stops()

7. CLI 완료 출력
   └─ 수집 건수, 소요시간, DB 파일 경로
```

### 아파트 좌표 획득 전략

MOLIT HouseInfo API는 아파트 단지의 위도/경도를 제공하지 않는다. 두 가지 접근:

1. **1차**: MOLIT HouseInfo API 응답의 `brtcCode`/`signguCode`/`bjdongCode`로 법정동 중심 좌표 근사
2. **2차**: Naver Geocoding API로 `"아파트명 + 법정동주소"` 쿼리 → 위도/경도
   - 법정동 주소는 MOLIT 실거래가 응답의 `umdNm` + `jibun` 조합에서 확보

권장: Naver Geocoding (Naver Maps Static API 키 동일)을 1회만 호출해 `apartments.lat/lon`에 캐시.

---

## SQLite 스키마

### ER 다이어그램 (텍스트)

```
apartments (pk: id)
│   id          TEXT PRIMARY KEY   -- "{lawd_cd}_{apt_name}" 결정적 키
│   lawd_cd     TEXT NOT NULL      -- 5자리 지역코드
│   region_name TEXT               -- 지역구 명칭 (예: "성남시 분당구")
│   apt_name    TEXT NOT NULL      -- 단지명
│   dong        TEXT               -- 법정동
│   jibun       TEXT               -- 지번
│   lat         REAL               -- 위도 (Naver Geocoding)
│   lon         REAL               -- 경도
│   collected_at TEXT              -- ISO8601
│
├───< monthly_prices (fk: apartment_id)
│       id              INTEGER PRIMARY KEY
│       apartment_id    TEXT NOT NULL → apartments.id
│       trade_type      TEXT NOT NULL   -- 'trade' | 'rent'
│       deal_ym         TEXT NOT NULL   -- 'YYYYMM'
│       area_m2         REAL NOT NULL   -- 전용면적(㎡)
│       price_min       INTEGER         -- 만원
│       price_max       INTEGER         -- 만원
│       price_avg       REAL            -- 만원
│       count           INTEGER
│       deposit_min     INTEGER         -- 전세/월세: 보증금 (만원)
│       deposit_max     INTEGER
│       deposit_avg     REAL
│       monthly_min     INTEGER         -- 월세 (만원)
│       monthly_max     INTEGER
│       monthly_avg     REAL
│       UNIQUE(apartment_id, trade_type, deal_ym, area_m2)
│
├───< building_info (fk: apartment_id, 1:1)
│       apartment_id    TEXT PRIMARY KEY → apartments.id
│       build_year      INTEGER         -- 건축년도
│       total_units     INTEGER         -- 세대수
│       floor_area_ratio REAL           -- 용적률(%)
│       building_coverage_ratio REAL    -- 건폐율(%)
│       parking_per_unit REAL           -- 세대당 주차대수
│       collected_at    TEXT
│
├───< subway_distances (fk: apartment_id)
│       id              INTEGER PRIMARY KEY
│       apartment_id    TEXT NOT NULL → apartments.id
│       station_name    TEXT NOT NULL   -- 역명 (예: "강남역")
│       line_name       TEXT            -- 노선명 (예: "2호선")
│       station_id      TEXT            -- 그래프 내 역 ID
│       walk_distance_m INTEGER         -- 도보 거리(m), NULL if >1000m
│       collected_at    TEXT
│       UNIQUE(apartment_id, station_id)
│
└───< commute_stops (fk: apartment_id)
        id              INTEGER PRIMARY KEY
        apartment_id    TEXT NOT NULL → apartments.id
        destination     TEXT NOT NULL   -- 'GBD'|'CBD'|'YBD'
        nearest_station TEXT            -- 출발역명
        stops           INTEGER         -- 최단 정거장 수 (환승 포함)
        transfer_count  INTEGER         -- 환승 횟수
        UNIQUE(apartment_id, destination)
```

### 인덱스

```sql
CREATE INDEX idx_monthly_prices_apt_ym
    ON monthly_prices(apartment_id, deal_ym);

CREATE INDEX idx_subway_distances_apt
    ON subway_distances(apartment_id);

CREATE INDEX idx_apartments_lawd
    ON apartments(lawd_cd);
```

---

## Patterns to Follow

### Pattern 1: Repository의 INSERT OR REPLACE

SQLite `INSERT OR REPLACE INTO` (UPSERT)를 기본 저장 전략으로 사용한다.
재수집 시 멱등성이 보장되고, 부분 실패 후 재실행이 안전하다.

```python
# storage/repository.py
def upsert_monthly_prices(conn: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
    INSERT OR REPLACE INTO monthly_prices
        (apartment_id, trade_type, deal_ym, area_m2,
         price_min, price_max, price_avg, count)
    VALUES
        (:apartment_id, :trade_type, :deal_ym, :area_m2,
         :price_min, :price_max, :price_avg, :count)
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)
```

### Pattern 2: Naver API 캐시 — DB 우선 조회

Naver Maps API는 유료 (월 사용량 제한). 동일 (apt, station) 쌍은 캐시에서 반환한다.

```python
# collectors/naver_distance.py
def get_walk_distance(conn, apt_id, station_id, apt_coords, station_coords) -> int | None:
    # 1. 캐시 체크
    row = conn.execute(
        "SELECT walk_distance_m FROM subway_distances WHERE apartment_id=? AND station_id=?",
        (apt_id, station_id)
    ).fetchone()
    if row is not None:          # NULL도 캐시됨 (>1000m 확인 완료)
        return row[0]

    # 2. API 호출 (rate limit: 1 req/sec)
    dist = call_naver_direction_api(apt_coords, station_coords)
    value = dist if dist and dist <= 1000 else None

    # 3. 저장 (NULL 포함)
    conn.execute(
        "INSERT OR REPLACE INTO subway_distances "
        "(apartment_id, station_id, walk_distance_m, collected_at) VALUES (?,?,?,?)",
        (apt_id, station_id, value, datetime.utcnow().isoformat())
    )
    conn.commit()
    return value
```

**Rate limit 구현**: `asyncio.sleep(1.0)` 또는 `time.sleep(1.0)` per API call.
Naver Maps Directions API: 일일 10만 건 무료 (2026 기준, 검증 필요).

### Pattern 3: 지하철 그래프 — 내장 JSON

전국 지하철 노선을 외부 API 없이 내장 JSON으로 보유한다.
`pipeline/data/subway_graph.json` — 역 노드 + 노선 엣지 (환승 포함 연결).

```python
# processors/subway_graph.py
from collections import deque
import json

DESTINATIONS = {
    "GBD": {"강남역", "삼성역", "선릉역", "역삼역"},  # 강남업무지구
    "CBD": {"시청역", "광화문역", "종각역", "을지로입구역"},  # 도심업무지구
    "YBD": {"여의도역", "여의나루역"},               # 여의도업무지구
}

def bfs_min_stops(graph: dict, start_station_id: str, targets: set[str]) -> tuple[int, int]:
    """
    Returns (min_stops, transfer_count) from start to any target station.
    graph: {station_id: [(neighbor_id, same_line: bool), ...]}
    """
    queue = deque([(start_station_id, 0, 0, None)])  # id, stops, transfers, current_line
    visited = set()
    while queue:
        sid, stops, transfers, line = queue.popleft()
        if sid in visited:
            continue
        visited.add(sid)
        if sid in targets:
            return stops, transfers
        for neighbor, neighbor_line in graph.get(sid, []):
            t = transfers + (1 if neighbor_line != line and line is not None else 0)
            queue.append((neighbor, stops + 1, t, neighbor_line))
    return -1, -1   # 연결 없음
```

**그래프 데이터 출처**: 서울 열린데이터광장 GTFS (고신뢰) 또는 수동 구축 (서울/수도권 한정).
GTFS 사용 시 `stops.txt` + `stop_times.txt` + `trips.txt`에서 그래프 추출 가능.

### Pattern 4: 실거래가 집계

MOLIT API는 개별 거래 건을 반환한다. DB에는 집계값(월별·평형별 통계)을 저장한다.
개별 건은 저장하지 않아 DB 크기를 관리 가능하게 유지한다.

```python
# processors/price_aggregator.py
from collections import defaultdict

def aggregate_trades(raw_trades: list[dict]) -> list[dict]:
    """
    (deal_ym, area_m2) 키로 그룹화 → min/max/avg/count
    """
    groups = defaultdict(list)
    for t in raw_trades:
        ym = f"{t['dealYear']}{t['dealMonth']:>02s}"
        area = round(float(t.get('excluUseAr', 0) or 0), 1)
        price = int(t.get('dealAmount', '0').replace(',', '') or 0)
        groups[(ym, area)].append(price)

    result = []
    for (ym, area), prices in groups.items():
        result.append({
            "deal_ym": ym,
            "area_m2": area,
            "price_min": min(prices),
            "price_max": max(prices),
            "price_avg": round(sum(prices) / len(prices), 1),
            "count": len(prices),
        })
    return result
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: 개별 거래 건 전체 저장
**What:** 모든 개별 거래 row를 DB에 저장
**Why bad:** 2006년~현재 서울 전체 = 수백만 건, SQLite 크기 수 GB, 분석 쿼리 느림
**Instead:** price_aggregator로 월별·평형별 집계 후 저장. 원시 데이터 필요 시 CSV로 임시 덤프.

### Anti-Pattern 2: Naver API 무캐시 반복 호출
**What:** 수집할 때마다 동일 (apt, station) 쌍에 API 재호출
**Why bad:** 비용 발생, rate limit 초과, 재수집 시 불필요한 지연
**Instead:** subway_distances 테이블을 캐시로 사용 (NULL 포함 저장, 체크 후 skip).

### Anti-Pattern 3: realestate_csv.py 직접 수정
**What:** 기존 스크립트에 새 기능 추가
**Why bad:** 기존 CSV 출력 워크플로우 파괴, 단일 파일 비대화, 롤백 어려움
**Instead:** `pipeline/` 신규 패키지로 분리. `region_resolver.py`에서 SIGUNGU_MAP/SIDO_MAP 코드만 복사.

### Anti-Pattern 4: 동기 HTTP + 전체 지역 순차 처리
**What:** for 루프로 지역 × 월 × 아파트를 순차 호출
**Why bad:** 25개 서울 자치구 × 240개월 × 1 req = 6,000건, 순차시 >1시간
**Instead:** `asyncio.gather()` + semaphore로 동시 처리 (MOLIT API는 병렬 수십 건 허용).

---

## Suggested Build Order (Phase Dependencies)

다음 순서는 데이터 의존성을 기반으로 한다:

```
Phase 1: Foundation
  storage/schema.py   → DB 스키마 정의 (모든 후속 단계의 기반)
  storage/db.py       → SQLite 연결, WAL 모드, 마이그레이션
  storage/repository.py → CRUD 헬퍼
  config.py           → .env 로딩, 지역 목록 상수
  processors/region_resolver.py → LAWD_CD 변환 (realestate_csv.py에서 이식)

Phase 2: Core Collectors (MOLIT)
  collectors/molit_trade.py      → 실거래가/전세 수집
  processors/price_aggregator.py → 월별 통계 집계
  (apartments 테이블에 단지 목록 확보 — 후속 단계의 입력)

Phase 3: Building Info
  collectors/molit_house_info.py → 건폐율/용적률/세대수 수집
  (apartments.id가 이미 존재해야 foreign key 충족)

Phase 4: Subway Distance
  collectors/naver_distance.py → 도보 거리 (캐시 포함)
  (apartments.lat/lon 필요 → Phase 2/3 완료 후)

Phase 5: Commute Stops (BFS)
  processors/subway_graph.py + pipeline/data/subway_graph.json
  (subway_distances 테이블의 nearest_station 정보 활용)

Phase 6: CLI + Orchestrator
  pipeline/cli.py         → argparse, 옵션 조합
  pipeline/orchestrator.py → Phase 2~5 실행 조율
```

### 의존 관계 요약

```
schema → db → repository
config → all collectors/processors
region_resolver → molit_trade → apartments rows → [building_info, naver_distance, subway_graph]
molit_trade → price_aggregator → monthly_prices
naver_distance → subway_distances → commute_stops (BFS입력)
```

---

## Scalability Considerations

| Concern | 현재 규모 (서울+경기 5개 권역) | 확장 (전국) | 대응 |
|---------|--------------------------|------------|------|
| DB 크기 | ~50MB (집계 기준) | ~500MB | 집계 유지, 파티션 불필요 |
| API 호출 수 | ~10,000 req/run | ~100,000 | semaphore 동시성 + 증분 수집 |
| BFS 속도 | <1ms/아파트 | <5ms | 인메모리 그래프, 허용 범위 |
| Naver API 비용 | ~수백 req/run | ~수천 | DB 캐시로 재수집 시 최소화 |

---

## Integration with Existing realestate_csv.py

| 항목 | realestate_csv.py | 신규 pipeline/ |
|------|------------------|----------------|
| 위치 | 리포 루트 (`realestate_csv.py`) | `pipeline/` 패키지 |
| 입력 | CSV 파일 (주소, 아파트명) | CLI 옵션 (지역구 자동 스캔) |
| 출력 | CSV | SQLite DB |
| API | MOLIT 실거래가 | MOLIT 실거래가 + HouseInfo + Naver |
| 재사용 코드 | SIGUNGU_MAP, SIDO_MAP, fetch_trades 로직, parse_xml | pipeline/processors/region_resolver.py에 이식 |
| 공존 | 기존 파일 삭제 안 함 — CSV 워크플로우 유지 | 독립적으로 실행 |

**이식 전략**: `region_resolver.py`는 `realestate_csv.py`의 `SIGUNGU_MAP`, `SIDO_MAP`,
`address_to_lawd_cd()` 함수를 그대로 복사한다. `molit_trade.py`는 `fetch_trades()`, `parse_xml()` 로직을
asyncio + httpx 기반으로 동일하게 이식한다. 이를 통해 검증된 로직을 재활용하면서 구조적 분리를 달성한다.

---

## Sources

- `realestate_csv.py` 직접 분석 (직접 코드 리뷰, HIGH confidence)
- `.planning/PROJECT.md` 요구사항 (HIGH confidence)
- MOLIT API 구조: 기존 코드의 엔드포인트/파라미터 패턴 (HIGH confidence)
- Naver Maps API 캐싱 패턴: 표준 비용 최적화 관행 (MEDIUM confidence — Naver API 정책 공식 문서 미검증)
- GTFS 기반 지하철 그래프: 서울 열린데이터광장 GTFS 공개 데이터셋 (MEDIUM confidence)
- BFS 알고리즘: 표준 그래프 탐색 (HIGH confidence)
