# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-18
**Phases:** 5 | **Plans:** 17 | **Tasks:** ~45

### What Was Built

- **Phase 1**: SQLite schema (6 tables + indexes), MOLIT API client (serviceKey auth, pagination, XML), idempotency log, region config (29 LAWD_CDs)
- **Phase 2**: Full MOLIT data collection — trade prices, rent prices, building info for 5 regions from 2006 to present
- **Phase 3**: TMAP walk-distance collector (per-line caching), Kakao geocoding, networkx BFS subway graph (GTFS + GTX-A), commute stops to GBD/CBD/YBD
- **Phase 4**: Typer CLI (`collect / export / status`), `apartment_analysis` VIEW (최신 시세 + 전세가율 + 업무지구 접근성), utf-8-sig CSV export
- **Phase 5**: Gap closure — 3-column UNIQUE migration for `subway_distances`, geocode CLI dispatch before subway, Phase 3 VERIFICATION.md

### What Worked

- **GSD wave-based execution**: Parallel plan execution per wave kept context lean and surfaced failures early
- **Xfail scaffold pattern**: Wave 0 test stubs (xfail) → Wave 1 implementation turning them xpass — made test-driven execution reliable
- **Milestone audit → gap closure phase**: The v1.0 audit precisely identified the 3 real gaps (SUBW-01/02/03, COMM-05); Phase 5 closed all of them in a single plan
- **SQLite table-recreate migration**: Standard approach for UNIQUE constraint changes — idempotent, data-safe, well-documented

### What Was Inefficient

- **Audit status not auto-updated**: After Phase 5 closed all audit gaps, `v1.0-MILESTONE-AUDIT.md` still showed `status: gaps_found` — created confusion at `complete-milestone`. Audit should be re-run or status manually updated after gap closure phases
- **Naver Maps → TMAP drift**: Initial plan assumed Naver Maps, actual implementation used TMAP (KAKAO key) — gap between plan and implementation required research correction mid-phase
- **2-column UNIQUE shipped**: The original schema used a 2-column UNIQUE that contradicted the collector's intent (per-line storage). A schema review step during Phase 3 planning would have caught this

### Patterns Established

- **Wave 0 = test scaffold**: Every phase creates xfail test stubs in Wave 0 before implementation waves
- **Gap closure phases**: Decimal or numbered gap-closure phases with `gap_closure: true` frontmatter for audit-identified fixes
- **CLI dispatch ordering**: Prerequisite data collection (geocoding) must appear before dependent collection (subway) in the dispatch block — source order = execution order
- **3-column UNIQUE for per-line data**: Any table storing per-attribute rows for a parent entity needs all discriminating attributes in the UNIQUE key

### Key Lessons

1. **Audit gaps → immediate gap phase**: Don't ship a milestone with `gaps_found` in the audit. Phase 5 pattern (create gap phase immediately) works well.
2. **UNIQUE constraints should match collector intent**: If collector stores per-line rows, schema UNIQUE must include the line discriminator.
3. **Prerequisite checks in CLI**: When collecting data with implicit dependencies (geocode → subway), make the dependency explicit in the dispatch order.
4. **Verify Phase N before shipping Phase N+1**: Phase 3 lacked a VERIFICATION.md — Phase 5 had to create it retroactively. Run `/gsd:verify-work` after each phase.

### Cost Observations

- Model mix: ~100% sonnet (executor + verifier + planner + researcher)
- Sessions: ~14 days git history (including legacy realestate_csv.py commits)
- Active GSD development: 2 days (2026-03-17 to 2026-03-18)
- Notable: 17 plans, ~113 commits — high commit density indicates good atomicity

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Gap Phases | Test Pattern |
|-----------|--------|-------|------------|--------------|
| v1.0 | 5 | 17 | 1 (Ph 5) | xfail scaffold |

