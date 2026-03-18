---
created: 2026-03-18T14:26:25.722Z
title: apartments 테이블 NULL 컬럼 수집 이슈 확인
area: api
files:
  - pipeline/storage/schema.py
  - pipeline/collectors/molit.py
---

## Problem

`apartments` 테이블의 `jibun`, `total_parking` 등 여러 컬럼이 모두 NULL인 상태. MOLIT 건물정보 수집 시 해당 필드가 파싱되지 않거나 DB에 적재되지 않는 이슈로 보임.

- `jibun` (지번 주소), `total_parking` (총 주차 대수) 등 건물 상세 정보 컬럼이 전부 None
- 수집 로직에서 XML 응답 파싱 누락 또는 컬럼 매핑 오류 가능성
- 혹은 MOLIT API 응답 자체에 해당 필드가 없는 경우도 점검 필요

## Solution

1. MOLIT 건물정보 API 응답 XML 샘플 확인 — 해당 필드가 실제로 내려오는지 검증
2. 파서 코드에서 `jibun`, `totalParking` 등 필드 추출 로직 확인
3. DB INSERT 시 컬럼 매핑 확인 (`schema.py`)
4. 누락된 필드는 파서 및 INSERT 쿼리에 추가
