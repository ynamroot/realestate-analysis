"""Shared pytest fixtures for pipeline foundation tests."""
import sqlite3
import pytest


@pytest.fixture
def tmp_db():
    """Return an in-memory sqlite3 connection. Closed after test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
