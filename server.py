from collections import defaultdict

import httpx
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row

from db import get_connection, run_read_query

mcp = FastMCP("PostGIS")


@mcp.tool()
def get_schema() -> dict[str, list[dict]]:
    """
    Returns a full map of the database: every table in the public schema with
    its column names, data types, and geometry type/SRID for spatial columns.
    Call this first at the start of every session to understand what tables
    are available before writing any query.
    """
    query = """
    SELECT
        c.table_name ,
        c.column_name,
        c.data_type,
        g.type AS geometry_type,
        g.srid
    FROM
        information_schema.columns AS c
    LEFT JOIN
        geometry_columns AS g
    ON
        c.table_name = g.f_table_name
        AND c.column_name = g.f_geometry_column
    WHERE
        c.table_schema = 'public'
        AND c.table_name NOT IN ('spatial_ref_sys', 'geometry_columns', 'geography_columns')
    ORDER BY
        c.table_name,
        c.ordinal_position;
    """

    rows = run_read_query(query)

    results = defaultdict(list)

    for row in rows:
        table_name = row["table_name"]
        results[table_name].append(
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "geometry_type": row["geometry_type"],
                "srid": row["srid"],
            }
        )
    return dict(results)


@mcp.tool()
def describe_table(table_name: str) -> list[dict]:
    """

    Returns column-level detail for a single named table: column names, data
    types, and geometry type/SRID for any spatial columns. Call this after
    get_schema to zoom into a specific table before writing a query against it.
    """

    query = """
    SELECT
        c.table_name ,
        c.column_name,
        c.data_type,
        g.type AS geometry_type,
        g.srid
    FROM
        information_schema.columns AS c
    LEFT JOIN
        geometry_columns AS g
    ON
        c.table_name = g.f_table_name
        AND c.column_name = g.f_geometry_column
    WHERE
        c.table_schema = 'public'
        AND c.table_name NOT IN ('spatial_ref_sys', 'geometry_columns', 'geography_columns')
        AND c.table_name = %s
    ORDER BY
        c.table_name,
        c.ordinal_position;
    """

    results = []
    rows = run_read_query(query, (table_name,))
    for row in rows:
        results.append(
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "geometry_type": row["geometry_type"],
                "srid": row["srid"],
            }
        )

    return results


@mcp.tool()
def run_spatial_query(sql: str) -> list[dict]:
    """
    Execute a read-only spatial SQL query against the PostGIS
    database and return the results as a list of rows.

    Use this after calling get_schema or describe_table to run
    a query you have constructed. Only SELECT statements are
    permitted. Results are capped at 100 rows — use LIMIT in
    your query if you need fewer.
    """
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")

    wrapped = f"SELECT * FROM ({sql}) AS _q LIMIT 100"
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(wrapped)
            rows = cur.fetchall()

    return rows


@mcp.tool()
def geocode_place(place_name: str) -> dict:
    """
    Geocode a place name to latitude and longitude using the
    Nominatim API (OpenStreetMap). Returns a dict with lat, lon,
    and display_name. Call this when you have a place name from
    the user and need coordinates to use in a spatial query.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place_name, "format": "json", "limit": 1}
    headers = {"User-Agent": "GeoWatch/0.1 (geowatch@geomatik.ai)"}

    response = httpx.get(url, params=params, headers=headers, timeout=10.0)
    data = response.json()
    if not data:
        raise ValueError(f"No results found for place name: {place_name}")
    result = data[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result["display_name"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
