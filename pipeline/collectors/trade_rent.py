"""
District-level trade/rent collection loop with idempotency.

Connects Phase 1 foundations (MolitClient, is_collected/mark_collected,
PIPELINE_REGIONS) to Phase 2 normalizer and repository. For each of the
29 districts × all months from start_ym to previous month, fetches,
normalizes, aggregates, and stores trade and rent data — skipping months
already collected.
"""
import asyncio
import sqlite3

import httpx
from loguru import logger

from pipeline.clients.molit import MolitClient
from pipeline.config.regions import PIPELINE_REGIONS
from pipeline.processors.normalizer import (
    aggregate_monthly,
    get_month_range,
    normalize_rent_item,
    normalize_trade_item,
)
from pipeline.storage.repository import insert_monthly_prices, upsert_apartment
from pipeline.utils.idempotency import is_collected, mark_collected


async def collect_district(
    conn: sqlite3.Connection,
    client: httpx.AsyncClient,
    molit: MolitClient,
    lawd_cd: str,
    months: list[str],
    deal_type: str,
) -> int:
    """
    Collect all months for one district and deal_type.

    For each month that has not already been collected, fetches raw items from
    the MOLIT API, normalizes them, aggregates by (apt_nm, umd_nm, deal_ym,
    exclu_use_ar), upserts apartment rows, inserts monthly_prices rows, and
    marks the (lawd_cd, deal_ym, deal_type) combination as collected.

    Args:
        conn: Open sqlite3 connection (schema must already exist).
        client: Open httpx.AsyncClient (caller manages lifecycle).
        molit: Initialized MolitClient instance.
        lawd_cd: 5-digit district code, e.g. "11680".
        months: Ordered list of YYYYMM strings to process.
        deal_type: "trade" or "rent".

    Returns:
        Total number of monthly_prices rows inserted across all months.
    """
    total = 0
    for deal_ym in months:
        if is_collected(conn, lawd_cd, deal_ym, deal_type):
            continue

        items = await molit.fetch_all(client, lawd_cd, deal_ym, deal_type)

        if deal_type == "trade":
            normalized = [normalize_trade_item(i) for i in items]
        else:
            normalized = [normalize_rent_item(i) for i in items]

        aggregated = aggregate_monthly(normalized, deal_type)

        for agg_row in aggregated:
            apt_id = upsert_apartment(
                conn,
                lawd_cd,
                agg_row["apt_nm"],
                agg_row["umd_nm"],
                jibun=None,
                road_nm=None,
                build_year=agg_row.get("build_year"),
            )
            total += insert_monthly_prices(conn, apt_id, [agg_row])

        mark_collected(conn, lawd_cd, deal_ym, deal_type, record_count=len(aggregated))
        logger.debug(
            f"Collected {lawd_cd} {deal_ym} {deal_type}: {len(aggregated)} agg rows"
        )

    return total


def collect_all_regions(
    conn: sqlite3.Connection,
    molit: MolitClient,
    start_ym: str = "200601",
) -> dict:
    """
    Run full collection for all PIPELINE_REGIONS, both trade and rent.

    Synchronous entry point. Creates an httpx.AsyncClient internally and
    calls collect_district for each of the 29 regions × 2 deal_types.

    NOTE: Uses asyncio.run() — do NOT call from inside an already-running
    async context.

    Args:
        conn: Open sqlite3 connection (schema must already exist).
        molit: Initialized MolitClient instance.
        start_ym: First month to collect, YYYYMM format. Defaults to "200601".

    Returns:
        Summary dict: {"trade": N, "rent": N, "regions": 29}.
    """
    months = get_month_range(start_ym)
    summary: dict = {"trade": 0, "rent": 0}

    async def _run() -> None:
        async with httpx.AsyncClient() as client:
            for name, lawd_cd in PIPELINE_REGIONS.items():
                logger.info(
                    f"Collecting {name} ({lawd_cd}) — {len(months)} months × 2 types"
                )
                for deal_type in ("trade", "rent"):
                    n = await collect_district(
                        conn, client, molit, lawd_cd, months, deal_type
                    )
                    summary[deal_type] += n

    asyncio.run(_run())
    summary["regions"] = len(PIPELINE_REGIONS)
    return summary
