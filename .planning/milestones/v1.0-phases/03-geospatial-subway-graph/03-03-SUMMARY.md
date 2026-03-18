---
phase: 03-geospatial-subway-graph
plan: "03"
subsystem: geocoding
status: partial
tags: [geocoding, kakao-api, apartment-coordinates, stations-xlsx]
dependency_graph:
  requires: [03-01]
  provides: [KakaoGeoClient, geocode_all_apartments, stations.xlsx]
  affects: [03-04, 03-05]
tech_stack:
  added: [httpx, loguru]
  patterns: [async-client, idempotent-batch-update, asyncio.run-wrapper]
key_files:
  created:
    - pipeline/clients/kakao_geo.py
    - pipeline/collectors/geocode.py
  modified: []
decisions:
  - "analyze_type=similar used (not exact) — returns best-match for partial addresses like 'umd_nm jibun'"
  - "No sleep/throttle between Kakao calls — 300k/day free quota exceeds ~300 apartment corpus"
  - "migrate_db() called at start of geocode_all_apartments() to ensure columns exist before querying"
metrics:
  completed_date: "2026-03-18"
  tasks_completed: 1
  tasks_total: 2
  files_created: 2
  files_modified: 0
checkpoint_status: "Paused at Task 2 — waiting for manual stations.xlsx download"
---

# Phase 3 Plan 03: Geocoding and Stations Data Summary

**One-liner:** Kakao Local API geocoder with idempotent batch updater for apartment lat/lon, plus manual stations.xlsx download gate.

## Status

Partial — Task 1 complete, Task 2 (human-verify checkpoint) pending.

## Completed Tasks

### Task 1: Kakao Geocoding client + geocode_all_apartments collector

**Commit:** bac64cf

Created two files:

- `pipeline/clients/kakao_geo.py` — `KakaoGeoClient` class: async geocoding via `GET https://dapi.kakao.com/v2/local/search/address.json`. Returns `(latitude, longitude)` tuple or `None`. Kakao's x=longitude/y=latitude convention preserved.
- `pipeline/collectors/geocode.py` — `geocode_all_apartments(conn)`: fetches all apartments with `latitude IS NULL`, geocodes via Kakao, writes coordinates back. `migrate_db()` called at entry to ensure columns exist. Raises `RuntimeError` if `KAKAO_REST_API_KEY` not set.

Address construction priority: `{umd_nm} {jibun}` > `road_nm` > `umd_nm`.

## Pending Tasks

### Task 2: Download stations.xlsx from data.go.kr (human-verify)

Manual download required from: https://www.data.go.kr/data/15013205/standard.do

Save to: `pipeline/data/stations.xlsx`

Required columns: 역사명, 노선명, 역위도, 역경도

## Deviations from Plan

None — plan executed exactly as written for Task 1.

## GTX-A Coverage Status

Not yet determined — pending stations.xlsx download.
To check after download:
```bash
python -c "import pandas as pd; df=pd.read_excel('pipeline/data/stations.xlsx', dtype=str); print(df[df['노선명'].str.contains('GTX', na=False)][['역사명','노선명']].to_string())"
```

## Self-Check

- [x] pipeline/clients/kakao_geo.py created
- [x] pipeline/collectors/geocode.py created
- [x] Commit bac64cf exists
- [ ] pipeline/data/stations.xlsx — pending manual download
