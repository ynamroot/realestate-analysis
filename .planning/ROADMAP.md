# Roadmap: 부동산 데이터 수집 파이프라인

## Overview

기존 `realestate_csv.py`의 CSV 기반 워크플로를 SQLite 백엔드로 전환하고, 건물정보·지하철 도보거리·정거장 수 계산을 추가하는 4단계 파이프라인이다. Phase 1에서 스키마와 MOLIT 클라이언트를 확립하고, Phase 2에서 전체 MOLIT 데이터 수집을 완료한 뒤, Phase 3에서 Naver Maps와 BFS 지하철 그래프를 구축하고, Phase 4에서 Typer CLI와 분석 뷰로 마무리한다.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - SQLite 스키마, MOLIT API 클라이언트, 지역 설정, 멱등성 로그 (completed 2026-03-17)
- [x] **Phase 2: MOLIT Data Collection** - 매매/전세 실거래가 + 건물정보 전체 수집 및 적재 (completed 2026-03-17)
- [ ] **Phase 3: Geospatial + Subway Graph** - TMAP 도보거리 + networkx BFS 정거장 수 계산
- [ ] **Phase 4: CLI + Analysis Views** - Typer CLI, 오케스트레이터, 전세가율 VIEW, CSV 내보내기

## Phase Details

### Phase 1: Foundation
**Goal**: 파이프라인이 실행 가능한 기반 인프라가 존재한다 — SQLite DB, MOLIT 클라이언트, 지역 설정, 중복 방지 로그
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04
**Success Criteria** (what must be TRUE):
  1. `python -c "from pipeline.storage.schema import init_db; init_db()"` 실행 시 6개 테이블과 인덱스가 생성된다
  2. MOLIT API 클라이언트가 serviceKey를 URL에 직접 embed하여 401 없이 XML 응답을 받는다
  3. 5개 지역(서울 자치구, 분당구, 과천시, 위례, 인덕원) LAWD_CD가 코드에 매핑되어 있다
  4. 동일 (lawd_cd, deal_ym, data_type) 조합을 두 번 수집하면 두 번째는 스킵된다
**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — Test scaffold: conftest.py + 9 failing test stubs (Wave 0)
- [ ] 01-02-PLAN.md — package skeleton + schema.py (init_db) + idempotency.py (Wave 1)
- [ ] 01-03-PLAN.md — region config: PIPELINE_REGIONS 29 LAWD_CDs (Wave 1, parallel)
- [ ] 01-04-PLAN.md — MOLIT API client: MolitClient + pagination + resultCode check (Wave 2)

### Phase 2: MOLIT Data Collection
**Goal**: 5개 지역 전체 아파트의 2006년~현재 매매·전세 실거래가와 건물정보가 SQLite에 완전히 적재된다
**Depends on**: Phase 1
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, BLDG-01, BLDG-02
**Success Criteria** (what must be TRUE):
  1. `SELECT COUNT(*) FROM apartments` 실행 시 5개 지역 전체 아파트 단지 수가 반환된다
  2. `SELECT * FROM monthly_prices WHERE deal_type='trade'` 가 2006년부터 현재까지 매매 집계 데이터를 포함한다
  3. `SELECT * FROM monthly_prices WHERE deal_type='rent'` 가 동기간 전세 집계 데이터를 포함한다
  4. `SELECT build_year, total_households FROM apartments WHERE build_year IS NOT NULL` 으로 건물정보가 확인된다
  5. dealAmount 쉼표, excluUseAr float 변환, dealMonth zero-padding이 모두 정규화된 상태로 저장된다
**Plans**: 5 plans

Plans:
- [ ] 02-01-PLAN.md — Test scaffold: 12 test stubs + package __init__.py markers (Wave 0)
- [ ] 02-02-PLAN.md — Normalizer/aggregator pure functions: normalize_trade_item, normalize_rent_item, aggregate_monthly, get_month_range (Wave 1)
- [ ] 02-03-PLAN.md — Storage repository: upsert_apartment, insert_monthly_prices, upsert_building_info (Wave 1, parallel)
- [ ] 02-04-PLAN.md — Trade/rent collector loop: collect_district + collect_all_regions (Wave 2)
- [ ] 02-05-PLAN.md — Building info collector: collect_building_info + collect_all_building_info (Wave 2, parallel)

### Phase 3: Geospatial + Subway Graph
**Goal**: 각 아파트에서 반경 1km 이내 지하철역까지의 실제 도보거리와 GBD/CBD/YBD까지의 최단 정거장 수가 계산되어 DB에 존재한다
**Depends on**: Phase 2
**Requirements**: SUBW-01, SUBW-02, SUBW-03, COMM-01, COMM-02, COMM-03, COMM-04, COMM-05
**Success Criteria** (what must be TRUE):
  1. `SELECT * FROM subway_distances WHERE apartment_id = ?` 가 해당 아파트의 호선별 도보거리(m) 또는 NULL(1km 초과)을 반환한다
  2. 동일 아파트를 다시 수집해도 TMAP API를 재호출하지 않고 캐시에서 반환된다
  3. `SELECT stops_to_gbd, stops_to_cbd, stops_to_ybd FROM commute_stops WHERE apartment_id = ?` 가 환승 포함 최단 정거장 수를 반환한다
  4. BFS 그래프가 서울 GTFS 기반으로 GTX-A 포함 전국 지하철 노선을 커버한다
**Plans**: 4 plans

Plans:
- [ ] 03-01-PLAN.md — Test scaffold + schema migration (lat/lon) + module stubs (Wave 0)
- [ ] 03-02-PLAN.md — TMAP client + haversine + subway graph builder + BFS min_stops (Wave 1)
- [ ] 03-03-PLAN.md — Kakao geocoding client + geocode_all_apartments + stations.xlsx download (Wave 1, parallel, has checkpoint)
- [ ] 03-04-PLAN.md — subway_distances collector + commute_stops BFS collector (Wave 2)

### Phase 4: CLI + Analysis Views
**Goal**: 사용자가 CLI 한 줄로 수집·내보내기·상태 확인을 할 수 있고, pandas로 즉시 분석 가능한 SQLite VIEW가 존재한다
**Depends on**: Phase 3
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. `pipeline collect --region seoul --start 200601` 명령이 실행되어 해당 지역 데이터를 수집한다
  2. `pipeline export --output output.csv` 명령이 Excel에서 한글이 깨지지 않는 utf-8-sig CSV를 생성한다
  3. `pipeline status` 명령이 각 지역별 마지막 수집 월과 레코드 수를 출력한다
  4. `SELECT * FROM apartment_analysis` VIEW가 아파트별 최신 시세, 전세가율, 업무지구 접근성을 통합 반환한다
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | Complete    | 2026-03-17 |
| 2. MOLIT Data Collection | 5/5 | Complete    | 2026-03-17 |
| 3. Geospatial + Subway Graph | 0/4 | Not started | - |
| 4. CLI + Analysis Views | 0/TBD | Not started | - |
