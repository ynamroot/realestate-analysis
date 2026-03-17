"""
Pure normalization and aggregation functions for MOLIT API responses.
No I/O, no DB calls — all functions accept/return plain Python types.
"""
from collections import defaultdict
from datetime import datetime, timedelta


def _safe_int(s: str) -> int | None:
    """Convert string to int; return None on empty or invalid input."""
    try:
        return int(s.strip()) if s.strip() else None
    except ValueError:
        return None


def _safe_float(s: str) -> float | None:
    """Convert string to float; return None on empty or invalid input."""
    try:
        return float(s.strip()) if s.strip() else None
    except ValueError:
        return None


def get_month_range(start_ym: str = "200601") -> list[str]:
    """Return all YYYYMM strings from start_ym up to previous calendar month."""
    now = datetime.now()
    # Previous month to avoid MOLIT submission lag
    prev = now.replace(day=1) - timedelta(days=1)
    end_y, end_m = prev.year, prev.month

    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    result = []
    y, m = sy, sm
    while (y, m) <= (end_y, end_m):
        result.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return result


def normalize_trade_item(item: dict) -> dict:
    """Normalize a raw MOLIT trade <item> dict. Returns typed fields."""
    deal_amount_raw = item.get("dealAmount", "").replace(",", "").strip()
    exclu_use_ar_raw = item.get("excluUseAr", "").strip()
    deal_month_raw = item.get("dealMonth", "").strip()

    return {
        "apt_nm":       item.get("aptNm", "").strip(),
        "umd_nm":       item.get("umdNm", "").strip(),
        "jibun":        item.get("jibun", "").strip(),
        "road_nm":      item.get("roadNm", "").strip(),
        "build_year":   _safe_int(item.get("buildYear", "")),
        "deal_year":    _safe_int(item.get("dealYear", "")),
        "deal_month":   deal_month_raw.zfill(2),           # PRICE-04 zero-padding
        "deal_ym":      f"{item.get('dealYear','')}{deal_month_raw.zfill(2)}",
        "exclu_use_ar": _safe_float(exclu_use_ar_raw),     # PRICE-04 float conversion
        "price":        _safe_int(deal_amount_raw),         # PRICE-04 comma removal -> int
        "floor":        _safe_int(item.get("floor", "")),
    }


def normalize_rent_item(item: dict) -> dict:
    """Normalize a raw MOLIT rent <item> dict. Returns typed fields."""
    deposit_raw = item.get("deposit", "").replace(",", "").strip()
    deal_month_raw = item.get("dealMonth", "").strip()

    return {
        "apt_nm":       item.get("aptNm", "").strip(),
        "umd_nm":       item.get("umdNm", "").strip(),
        "jibun":        item.get("jibun", "").strip(),
        "road_nm":      item.get("roadNm", "").strip(),
        "build_year":   _safe_int(item.get("buildYear", "")),
        "deal_year":    _safe_int(item.get("dealYear", "")),
        "deal_month":   deal_month_raw.zfill(2),
        "deal_ym":      f"{item.get('dealYear','')}{deal_month_raw.zfill(2)}",
        "exclu_use_ar": _safe_float(item.get("excluUseAr", "")),
        "deposit":      _safe_int(deposit_raw),
        "monthly_rent": _safe_int(item.get("monthlyRent", "").replace(",", "")),
        "floor":        _safe_int(item.get("floor", "")),
    }


def aggregate_monthly(normalized_items: list[dict], deal_type: str) -> list[dict]:
    """
    Group normalized items into one monthly_prices row per (apt_nm, umd_nm, deal_ym, exclu_use_ar).

    For trade: price_min, price_max, price_avg, deal_count.
    For rent:  deposit_min, deposit_max, deposit_avg, deal_count.
    """
    groups: dict[tuple, list] = defaultdict(list)
    for item in normalized_items:
        key = (item["apt_nm"], item["umd_nm"], item["deal_ym"], item["exclu_use_ar"])
        groups[key].append(item)

    rows = []
    for (apt_nm, umd_nm, deal_ym, exclu_use_ar), items in groups.items():
        row = {
            "apt_nm": apt_nm,
            "umd_nm": umd_nm,
            "deal_ym": deal_ym,
            "deal_type": deal_type,
            "exclu_use_ar": exclu_use_ar,
            "deal_count": len(items),
        }
        if deal_type == "trade":
            prices = [i["price"] for i in items if i["price"] is not None]
            row["price_min"] = min(prices) if prices else None
            row["price_max"] = max(prices) if prices else None
            row["price_avg"] = sum(prices) / len(prices) if prices else None
            row["deposit_min"] = row["deposit_max"] = row["deposit_avg"] = None
        else:  # rent
            deposits = [i["deposit"] for i in items if i["deposit"] is not None]
            row["deposit_min"] = min(deposits) if deposits else None
            row["deposit_max"] = max(deposits) if deposits else None
            row["deposit_avg"] = sum(deposits) / len(deposits) if deposits else None
            row["price_min"] = row["price_max"] = row["price_avg"] = None
        rows.append(row)
    return rows
