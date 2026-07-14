import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import describe_table, get_schema

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_postgis_data():
    return [
        {
            "table_name": "table1",
            "column_name": "col1",
            "data_type": "integer",
            "geometry_type": None,
            "srid": None,
        },
        {
            "table_name": "table1",
            "column_name": "col2",
            "data_type": "text",
            "geometry_type": None,
            "srid": None,
        },
        {
            "table_name": "table2",
            "column_name": "geom",
            "data_type": "USER-DEFINED",
            "geometry_type": "POINT",
            "srid": 4326,
        },
    ]


# ─────────────────────────────────────────────
# Unit tests (mocked — no real DB)
# ─────────────────────────────────────────────


def test_get_schema(monkeypatch, mock_postgis_data):
    def mock_run_read_query(query):
        return mock_postgis_data

    monkeypatch.setattr("server.run_read_query", mock_run_read_query)

    result = get_schema()

    assert isinstance(result, dict)
    assert "table1" in result
    assert "table2" in result
    assert len(result["table1"]) == 2
    assert len(result["table2"]) == 1


def test_describe_table(monkeypatch, mock_postgis_data):
    def mock_run_read_query(query, params):
        table_name = params[0]
        return [row for row in mock_postgis_data if row["table_name"] == table_name]

    monkeypatch.setattr("server.run_read_query", mock_run_read_query)

    result = describe_table("table1")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["column_name"] == "col1"
    assert result[1]["column_name"] == "col2"


# ─────────────────────────────────────────────
# Integration tests (real DB — CI PostGIS container)
# ─────────────────────────────────────────────


def test_get_schema_returns_dict():
    result = get_schema()
    assert isinstance(result, dict)


def test_get_schema_excludes_postgis_system_tables():
    result = get_schema()
    assert "spatial_ref_sys" not in result
    assert "geometry_columns" not in result
    assert "geography_columns" not in result


def test_get_schema_column_structure():
    """Every column entry must have the four expected keys."""
    result = get_schema()
    for table_name, columns in result.items():
        assert isinstance(columns, list), f"{table_name} value should be a list"
        for col in columns:
            assert "column_name" in col
            assert "data_type" in col
            assert "geometry_type" in col
            assert "srid" in col


def test_describe_table_nonexistent_returns_empty():
    """Asking for a table that doesn't exist should return [] not crash."""
    result = describe_table("nonexistent_table_xyz")
    assert isinstance(result, list)
    assert len(result) == 0


def test_describe_table_known_table():
    """
    If planet_osm_point exists (local dev + seeded CI),
    it must have a geometry column called 'way'.
    """
    schema = get_schema()
    if "planet_osm_point" not in schema:
        pytest.skip("planet_osm_point not loaded in this environment")

    result = describe_table("planet_osm_point")

    assert isinstance(result, list)
    assert len(result) > 0

    column_names = [r["column_name"] for r in result]
    assert "way" in column_names

    way_col = next(r for r in result if r["column_name"] == "way")
    assert way_col["geometry_type"] == "POINT"
    assert way_col["srid"] == 4326
