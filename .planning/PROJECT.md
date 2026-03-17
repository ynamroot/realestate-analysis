# 부동산 데이터 수집 파이프라인 (RealEstate Data Pipeline)

## What This Is

지정 지역(서울, 경기도 분당/과천/위례/인덕원)의 아파트 매매·전세 실거래가, 지하철 접근성, 건물 기본정보를 통합 수집하여 SQLite에 적재하는 Python CLI 파이프라인이다. 기존 `realestate_csv.py`를 재설계·확장하여 투자 분석, 대시보드 연동, CSV 내보내기를 지원하는 구조적 DB를 구축한다.

## Core Value

지정 지역 전체 아파트의 시세·교통·건물 정보를 하나의 SQLite DB에 통합하여, pandas 분석과 향후 대시보드 연동이 즉시 가능한 상태로 유지한다.

## Requirements

### Validated

- ✓ 국토교통부 MOLIT API 연동 (serviceKey 인증, XML 파싱) — 기존 realestate_csv.py
- ✓ 지역코드(LAWD_CD) 기반 실거래가 조회 및 페이지네이션 — 기존 realestate_csv.py
- ✓ Naver Maps API 키 보유 (.env) — 기존 인프라

### Active

- [ ] 지정 지역구 전체 아파트 자동 수집 (CSV 입력 없이 지역구 단위 스캔)
- [ ] 월별 매매가 수집: 지역구 × 평형 × 월별 (최저/최고/평균, 거래건수)
- [ ] 월별 전세가 수집: 지역구 × 평형 × 월별 (최저/최고/평균, 거래건수)
- [ ] 아파트별 지하철역 거리 수집 (호선별, Naver Maps API, 1km 초과 시 null)
- [ ] 아파트별 건물 정보 수집 (건폐율, 건축년도, 용적률, 세대수, 주차대수) — 국토교통부 HouseInfo API
- [ ] GBD/CBD/YBD까지 최단 정거장 수 계산 (환승 포함, 전국 지하철 노선 그래프)
- [ ] 전체 데이터 SQLite 적재 (분석/대시보드/CSV 내보내기 지원 스키마)
- [ ] CLI 인터페이스 (지역, 기간, 수집 항목 선택 가능)

### Out of Scope

- 스케줄링/크론 자동화 — v1은 수동 실행, 나중에 추가
- 웹 대시보드 구현 — 데이터 적재 후 별도 프로젝트
- 실시간 데이터 — 월별 배치 수집으로 충분
- 서울/경기 5개 지역 외 — 명시적 지역 한정
- FastAPI A2A 에이전트 기능 확장 — 별도 유지

## Context

- **기존 코드**: `realestate_csv.py`에 MOLIT API 연동, 주소→LAWD_CD 변환, 실거래가 조회, 아파트명 필터링 구현됨
- **API 키**: `.env`에 MOLIT_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 보유
- **지역 범위**: 서울 전체 자치구 + 성남시 분당구, 과천시, 하남시(위례), 안양시 동안구(인덕원)
- **데이터 범위**: 2006년~현재 (MOLIT API 제공 시점부터 전체)
- **지하철 정거장 수**: 전국 지하철 노선 그래프를 내장하거나 공공 GTFS 데이터로 BFS 계산
- **기존 리포**: FastAPI A2A 에이전트 구조 존재하나 이번 작업은 독립 파이프라인으로 분리

## Constraints

- **Tech Stack**: Python (기존 코드 재사용), sqlite3 내장 모듈
- **API**: MOLIT (실거래가/건물정보), Naver Maps (도보 거리) — 기존 키 사용
- **실행**: CLI 수동 실행, 스케줄링 제외
- **지역**: 서울, 분당, 과천, 위례, 인덕원 5개 권역 고정
- **정거장 계산**: 환승 포함 최단 정거장 수 (이동시간 아님)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite 사용 | pandas/대시보드/CSV 모두 지원, 별도 서버 불필요 | — Pending |
| 지역구 전체 자동 수집 | CSV 입력 대신 MOLIT API에서 해당 지역 전체 아파트 목록 확보 | — Pending |
| Naver Maps API로 도보 거리 | 기존 키 보유, 정확한 도보 경로 거리 제공 | — Pending |
| 정거장 수는 BFS 계산 | API 없이 오프라인 그래프로 환승 포함 최단 경로 계산 | — Pending |
| realestate_csv.py 재설계 | 기능 통폐합, 모듈화, SQLite 출력으로 전환 | — Pending |

---
*Last updated: 2026-03-17 after initialization*
