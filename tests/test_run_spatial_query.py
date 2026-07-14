import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import psycopg
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import run_spatial_query

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def make_mock_connection(rows):
    """Build a fake get_connection() context manager that returns preset rows."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = rows

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def mock_get_connection():
        yield mock_conn

    return mock_get_connection


# ─────────────────────────────────────────────
# Unit tests (monkeypatched — no real DB)
# ─────────────────────────────────────────────


def test_valid_select_executes(monkeypatch):
    fake_rows = [{"name": "Civil Hospital", "amenity": "hospital"}]
    monkeypatch.setattr("server.get_connection", make_mock_connection(fake_rows))

    result = run_spatial_query("SELECT name, amenity FROM planet_osm_point")

    assert isinstance(result, list)
    assert result == fake_rows


def test_insert_raises_valueerror():
    with pytest.raises(ValueError):
        run_spatial_query("INSERT INTO planet_osm_point VALUES (1)")


def test_update_raises_valueerror():
    with pytest.raises(ValueError):
        run_spatial_query("UPDATE planet_osm_point SET name='x'")


def test_drop_raises_valueerror():
    with pytest.raises(ValueError):
        run_spatial_query("DROP TABLE planet_osm_point")


def test_row_cap_enforced_in_sql(monkeypatch):
    """The wrapped SQL sent to the cursor must contain LIMIT 100."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def mock_get_connection():
        yield mock_conn

    monkeypatch.setattr("server.get_connection", mock_get_connection)

    run_spatial_query("SELECT name FROM planet_osm_point")

    executed_sql = mock_cur.execute.call_args[0][0]
    assert "LIMIT 100" in executed_sql


def test_original_sql_wrapped_as_subquery(monkeypatch):
    """The agent's SQL must appear as a subquery, not be executed directly."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def mock_get_connection():
        yield mock_conn

    monkeypatch.setattr("server.get_connection", mock_get_connection)

    original_sql = "SELECT name FROM planet_osm_point"
    run_spatial_query(original_sql)

    executed_sql = mock_cur.execute.call_args[0][0]
    assert original_sql in executed_sql
    assert executed_sql.startswith("SELECT * FROM (")


# ─────────────────────────────────────────────
# Integration tests (real PostGIS container)
# ─────────────────────────────────────────────


def test_basic_select_returns_results():
    result = run_spatial_query("SELECT name FROM planet_osm_point LIMIT 5")

    assert isinstance(result, list)
    assert len(result) <= 5


def test_result_rows_are_dicts():
    result = run_spatial_query("SELECT name, amenity FROM planet_osm_point LIMIT 1")

    assert isinstance(result, list)
    if result:
        assert isinstance(result[0], dict)
        assert "name" in result[0]


def test_syntax_error_propagates():
    """Raw Postgres errors must not be caught — the agent reads them to self-correct."""
    with pytest.raises(psycopg.Error):
        run_spatial_query("SELECT * FROM nonexistent_table_xyz")


def test_no_limit_query_capped_at_100():
    """Even with no LIMIT in the agent's SQL, results must never exceed 100."""
    result = run_spatial_query("SELECT name FROM planet_osm_point")

    assert len(result) <= 100


def test_raw_error_propagates():
    """
    The raw Postgres error message must reach the agent unmodified.
    If this fails, someone added a try/except that breaks the
    agent's self-correction loop.
    """
    with pytest.raises(psycopg.Error) as exc_info:
        run_spatial_query("SELECT * FROM nonexistent_table_xyz")
    assert "nonexistent_table_xyz" in str(exc_info.value)
