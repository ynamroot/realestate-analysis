# 부동산 데이터 수집 파이프라인 (RealEstate Data Pipeline)

## What This Is

지정 지역(서울, 경기도 분당/과천/위례/인덕원)의 아파트 매매·전세 실거래가, 지하철 도보거리(호선별), GBD/CBD/YBD 최단 정거장 수, 건물정보를 통합 수집하여 SQLite에 적재하는 Python CLI 파이프라인이다. `pipeline collect / export / status` CLI로 수집하고, `apartment_analysis` VIEW와 CSV 내보내기로 pandas/대시보드 연동을 지원한다.

## Core Value

지정 지역 전체 아파트의 시세·교통·건물 정보를 하나의 SQLite DB에 통합하여, pandas 분석과 향후 대시보드 연동이 즉시 가능한 상태로 유지한다.

## Current State (v1.0)

**Shipped:** 2026-03-18
**Stack:** Python 3.x, sqlite3, Typer, httpx, networkx, pytest
**Code:** ~19,600 lines Python, 164 files
**Tests:** 24 passing + 26 xpassed (phase-gated)

**What's working:**
- `pipeline collect --data-type all` — geocode → subway distances → commute stops (순서 보장)
- `pipeline export --output output.csv` — utf-8-sig CSV
- `pipeline status` — 지역별 수집 현황
- SQLite schema with `apartment_analysis` VIEW
- 5개 지역 × 전체 연도 MOLIT 데이터 수집
- TMAP 도보거리 캐싱 (UNIQUE(apt_id, station, line_name) 3-column)
- BFS 정거장 수 (서울 GTFS + GTX-A)
- Kakao geocoding → lat/lon 채움

**Known gaps / tech debt:**
- Naver Maps API → TMAP API로 전환됨 (키 업데이트 필요)
- `test_fastmcp.py`, `test_mcp.py` 비동기 실패 pre-existing (FastAPI A2A 레거시)
- 스케줄링/자동화 미구현 (수동 실행)

## Requirements

### Validated

- ✓ 국토교통부 MOLIT API 연동 (serviceKey 인증, XML 파싱) — v1.0
- ✓ 지역코드(LAWD_CD) 기반 실거래가 조회 및 페이지네이션 — v1.0
- ✓ 지정 지역구 전체 아파트 자동 수집 (CSV 입력 없이 지역구 단위 스캔) — v1.0
- ✓ 월별 매매가 수집: 지역구 × 평형 × 월별 (최저/최고/평균, 거래건수) — v1.0
- ✓ 월별 전세가 수집: 지역구 × 평형 × 월별 (최저/최고/평균, 거래건수) — v1.0
- ✓ 아파트별 지하철역 도보거리 수집 (호선별, 1km 초과 시 null) — v1.0
- ✓ 아파트별 건물 정보 수집 (건폐율, 건축년도, 용적률, 세대수, 주차대수) — v1.0
- ✓ GBD/CBD/YBD까지 최단 정거장 수 계산 (환승 포함) — v1.0
- ✓ 전체 데이터 SQLite 적재 (분석/대시보드/CSV 내보내기 지원 스키마) — v1.0
- ✓ CLI 인터페이스 (지역, 기간, 수집 항목 선택 가능) — v1.0

### Active

- [ ] 스케줄링/크론 자동화 — 월별 증분 수집
- [ ] 웹 대시보드 연동 — apartment_analysis VIEW 활용
- [ ] Naver Maps → TMAP API 키 정식 전환 확인

### Out of Scope

- 실시간 데이터 — 월별 배치 수집으로 충분
- 서울/경기 5개 지역 외 확장 — 명시적 지역 한정
- FastAPI A2A 에이전트 기능 확장 — 별도 프로젝트

## Context

- **API 키**: `.env`에 MOLIT_API_KEY, KAKAO_REST_API_KEY 보유 (TMAP은 KAKAO 키로 통합)
- **지역 범위**: 서울 전체 자치구 + 성남시 분당구, 과천시, 하남시(위례), 안양시 동안구(인덕원)
- **데이터 범위**: 2006년~현재 (MOLIT API 제공 시점부터 전체)
- **지하철 그래프**: 서울 GTFS 기반 networkx 그래프, GTX-A 포함

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite 사용 | pandas/대시보드/CSV 모두 지원, 별도 서버 불필요 | ✓ 잘 작동 |
| 지역구 전체 자동 수집 | CSV 입력 대신 MOLIT API에서 해당 지역 전체 아파트 목록 확보 | ✓ 잘 작동 |
| TMAP API로 도보거리 | Naver Maps 대신 TMAP 사용 (KAKAO 키) | ✓ 검증됨 |
| 정거장 수는 BFS 계산 | API 없이 오프라인 그래프로 환승 포함 최단 경로 계산 | ✓ 잘 작동 |
| UNIQUE(apt, station, line_name) 3-column | 호선별 분리 저장 — 2-column이면 INSERT OR IGNORE로 첫 호선만 저장 | ✓ Phase 5 fix |
| geocode → subway 순서 보장 | CLI dispatch에서 geocode 블록을 subway 블록 앞에 위치 | ✓ Phase 5 fix |
| realestate_csv.py 재설계 | 기능 통폐합, 모듈화, SQLite 출력으로 전환 | ✓ 완료 |

## Constraints

- **Tech Stack**: Python (기존 코드 재사용), sqlite3 내장 모듈
- **API**: MOLIT (실거래가/건물정보), TMAP/Kakao (도보 거리, 지오코딩) — 기존 키 사용
- **실행**: CLI 수동 실행, 스케줄링 제외 (v1.0)
- **지역**: 서울, 분당, 과천, 위례, 인덕원 5개 권역 고정
- **정거장 계산**: 환승 포함 최단 정거장 수 (이동시간 아님)

---
*Last updated: 2026-03-18 after v1.0 milestone*
