import pytest

from server import describe_table, get_schema


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


def test_get_schema(monkeypatch, mock_postgis_data):
    # Mock the run_read_query function to return mock data
    def mock_run_read_query(query):
        return mock_postgis_data

    monkeypatch.setattr("server.run_read_query", mock_run_read_query)

    # Call the get_schema function
    result = get_schema()

    # Assert the structure of the result
    assert isinstance(result, dict)
    assert "table1" in result
    assert "table2" in result
    assert len(result["table1"]) == 2
    assert len(result["table2"]) == 1


def test_describe_table(monkeypatch, mock_postgis_data):
    # Mock the run_read_query function to return filtered mock data
    def mock_run_read_query(query, params):
        table_name = params[0]
        return [row for row in mock_postgis_data if row["table_name"] == table_name]

    monkeypatch.setattr("server.run_read_query", mock_run_read_query)

    # Call the describe_table function
    result = describe_table("table1")

    # Assert the structure of the result
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["column_name"] == "col1"
    assert result[1]["column_name"] == "col2"
