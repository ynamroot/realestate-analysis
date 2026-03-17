"""
Idempotency helpers for the collection_log table.

Prevents re-fetching (lawd_cd, deal_ym, data_type) combinations that have
already been collected. The UNIQUE constraint on collection_log is the source
of truth -- these helpers are lightweight wrappers around it.
"""
import sqlite3


def is_collected(
    conn: sqlite3.Connection,
    lawd_cd: str,
    deal_ym: str,
    data_type: str,
) -> bool:
    """
    Return True if this (lawd_cd, deal_ym, data_type) has already been collected.

    Args:
        conn: Open sqlite3 connection (collection_log table must exist).
        lawd_cd: 5-digit district code, e.g. "11680".
        deal_ym: Year-month string, e.g. "202401".
        data_type: One of "trade", "rent", "building".

    Returns:
        True if a matching row exists in collection_log, False otherwise.
    """
    row = conn.execute(
        "SELECT 1 FROM collection_log WHERE lawd_cd=? AND deal_ym=? AND data_type=?",
        (lawd_cd, deal_ym, data_type),
    ).fetchone()
    return row is not None


def mark_collected(
    conn: sqlite3.Connection,
    lawd_cd: str,
    deal_ym: str,
    data_type: str,
    record_count: int = 0,
) -> None:
    """
    Record that (lawd_cd, deal_ym, data_type) has been collected.

    Uses INSERT OR IGNORE so calling this twice with the same key is safe --
    the second call is a no-op. The UNIQUE constraint on collection_log
    enforces deduplication at the DB level.

    Args:
        conn: Open sqlite3 connection (collection_log table must exist).
        lawd_cd: 5-digit district code.
        deal_ym: Year-month string.
        data_type: One of "trade", "rent", "building".
        record_count: Number of records inserted during this collection run.
    """
    conn.execute(
        "INSERT OR IGNORE INTO collection_log "
        "(lawd_cd, deal_ym, data_type, record_count) VALUES (?,?,?,?)",
        (lawd_cd, deal_ym, data_type, record_count),
    )
    conn.commit()
