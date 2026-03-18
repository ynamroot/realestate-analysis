"""
Typer CLI entry point for the real estate pipeline.

Subcommands:
  collect   — fetch trade/rent/building/subway data from APIs
  export    — write apartment_analysis VIEW to UTF-8 BOM CSV
  status    — print collection_log summary per region
"""
import os
import sqlite3
from typing import Optional

import typer
from dotenv import load_dotenv

from pipeline.config.regions import GYEONGGI_REGIONS, PIPELINE_REGIONS, SEOUL_REGIONS
from pipeline.storage.schema import DB_PATH, init_db

app = typer.Typer(no_args_is_help=True, help="부동산 데이터 수집 파이프라인")


def _resolve_regions(region: Optional[str]) -> dict[str, str]:
    """
    Map --region shorthand to a LAWD_CD dict.

    "seoul"    -> SEOUL_REGIONS (25 entries)
    "gyeonggi" -> GYEONGGI_REGIONS (4 entries)
    Korean district name (e.g. "강남구") -> single-entry dict
    None       -> full PIPELINE_REGIONS (29 entries)
    """
    if region is None:
        return PIPELINE_REGIONS
    if region.lower() == "seoul":
        return SEOUL_REGIONS
    if region.lower() == "gyeonggi":
        return GYEONGGI_REGIONS
    if region in PIPELINE_REGIONS:
        return {region: PIPELINE_REGIONS[region]}
    typer.echo(
        f"Unknown region: '{region}'. Use 'seoul', 'gyeonggi', or a Korean district name "
        f"(e.g. '강남구'). Available: {list(PIPELINE_REGIONS.keys())}",
        err=True,
    )
    raise typer.Exit(1)


@app.command()
def collect(
    region: Optional[str] = typer.Option(
        None, help="seoul | gyeonggi | 강남구 | ... (기본값: 전체 29개 지역)"
    ),
    start: str = typer.Option("200601", help="수집 시작 월 YYYYMM (기본값: 200601)"),
    data_type: str = typer.Option(
        "all", help="trade | rent | building | geocode | subway | all (기본값: all)"
    ),
) -> None:
    """아파트 실거래가 + 건물정보 + 지하철 거리 수집"""
    load_dotenv()
    conn = init_db(DB_PATH)
    regions = _resolve_regions(region)
    typer.echo(f"Collecting {len(regions)} region(s) from {start} [data_type={data_type}] ...")
    # Dispatch to existing synchronous collector entry points.
    # Each internally calls asyncio.run() — do NOT make this function async.
    from pipeline.clients.molit import MolitClient
    molit_key = os.getenv("MOLIT_API_KEY", "")
    if not molit_key and data_type in ("trade", "rent", "building", "all"):
        typer.echo("MOLIT_API_KEY not set in environment — trade/rent/building collection skipped.", err=True)

    if data_type in ("trade", "rent", "all") and molit_key:
        from pipeline.collectors.trade_rent import collect_all_regions as _collect_trade
        from pipeline.clients.molit import MolitClient
        molit = MolitClient(molit_key)
        result = _collect_trade(conn, molit, start_ym=start)
        typer.echo(f"Trade/rent: {result}")

    if data_type in ("building", "all") and molit_key:
        from pipeline.collectors.building_info import collect_all_building_info
        from pipeline.clients.molit import MolitClient
        molit = MolitClient(molit_key)
        result = collect_all_building_info(conn, molit)
        typer.echo(f"Building: {result}")

    if data_type in ("geocode", "subway", "all"):
        kakao_key = os.getenv("KAKAO_REST_API_KEY")
        if not kakao_key:
            typer.echo("KAKAO_REST_API_KEY not set — geocoding skipped.", err=True)
            if data_type in ("subway", "all"):
                typer.echo(
                    "WARNING: subway collection will process 0 apartments because "
                    "no coordinates are set. Set KAKAO_REST_API_KEY and run geocode first.",
                    err=True,
                )
        else:
            from pipeline.collectors.geocode import geocode_all_apartments
            result = geocode_all_apartments(conn)
            typer.echo(f"Geocoding: {result}")

    if data_type in ("subway", "all"):
        tmap_key = os.getenv("TMAP_APP_KEY")
        if not tmap_key:
            typer.echo("TMAP_APP_KEY not set — subway distance collection skipped.", err=True)
        else:
            from pipeline.collectors.subway_distances import collect_all_subway_distances
            result = collect_all_subway_distances(conn)
            typer.echo(f"Subway distances: {result}")
            from pipeline.collectors.commute_stops import collect_all_commute_stops
            result = collect_all_commute_stops(conn)
            typer.echo(f"Commute stops: {result}")

    conn.close()
    typer.echo("Done.")


@app.command()
def export(
    output: str = typer.Option("output.csv", "--output", "-o", help="CSV 출력 경로"),
    query: Optional[str] = typer.Option(
        None, "--query", "-q", help="커스텀 SQL (기본값: SELECT * FROM apartment_analysis)"
    ),
) -> None:
    """apartment_analysis VIEW를 Excel 호환 UTF-8 BOM CSV로 내보내기"""
    import pandas as pd
    conn = init_db(DB_PATH)
    sql = query or "SELECT * FROM apartment_analysis"
    df = pd.read_sql(sql, conn)
    df.to_csv(output, encoding="utf-8-sig", index=False)
    conn.close()
    typer.echo(f"Exported {len(df):,} rows to {output}")


@app.command()
def status() -> None:
    """지역별 수집 현황 (마지막 수집 월, 레코드 수) 출력"""
    conn = init_db(DB_PATH)
    rows = conn.execute("""
        SELECT lawd_cd, data_type, MAX(deal_ym) AS last_ym,
               SUM(record_count) AS total_records
        FROM collection_log
        GROUP BY lawd_cd, data_type
        ORDER BY lawd_cd, data_type
    """).fetchall()
    if not rows:
        typer.echo("No data collected yet.")
        conn.close()
        return
    typer.echo(f"{'LAWD_CD':<10} {'Type':<10} {'Last YM':<10} {'Records':>10}")
    typer.echo("-" * 44)
    for r in rows:
        typer.echo(
            f"{r['lawd_cd']:<10} {r['data_type']:<10} {r['last_ym']:<10} {r['total_records']:>10,}"
        )
    # Supplementary coverage info
    geocoded = conn.execute(
        "SELECT COUNT(*) FROM apartments WHERE latitude IS NOT NULL"
    ).fetchone()[0]
    total_apt = conn.execute("SELECT COUNT(*) FROM apartments").fetchone()[0]
    subway_covered = conn.execute(
        "SELECT COUNT(DISTINCT apartment_id) FROM subway_distances"
    ).fetchone()[0]
    conn.close()
    typer.echo(f"\nApartments: {total_apt} total, {geocoded} geocoded, {subway_covered} with subway data")


if __name__ == "__main__":
    app()
