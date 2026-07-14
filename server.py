from collections import defaultdict

from mcp.server.fastmcp import FastMCP

from db import run_read_query

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


if __name__ == "__main__":
    mcp.run(transport="stdio")
