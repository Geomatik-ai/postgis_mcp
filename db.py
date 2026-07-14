"""
db.py -- the single, shared way every MCP tool talks to the database.

Every tool (get_schema, run_spatial_query, geocode_place, ...) imports
run_read_query from here. Nothing else in this project should import
psycopg directly -- this module is the only place that knows how to
connect to Postgres.
"""

import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Fail loudly at import time if the password isn't configured -- a broken
# connection string should surface immediately when the server starts,
# not three tool-calls deep during an actual agent run at 2am.
_PASSWORD = os.environ.get("GIS_READER_PASSWORD")
if not _PASSWORD:
    raise RuntimeError(
        "GIS_READER_PASSWORD is not set. Export it before starting the "
        "server, e.g.: export GIS_READER_PASSWORD='...'"
    )

_DSN = f"host=localhost port=5432 dbname=gis " f"user=gis_reader password={_PASSWORD}"

# One pool, shared for the server's whole lifetime. Created lazily on first
# use (not at import time) so just importing this module in a test file
# doesn't immediately try to open a real network connection.
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_DSN,
            min_size=1,
            max_size=5,  # one agent, used locally -- 5 gives headroom for
            # a couple of concurrent tool calls without
            # over-provisioning connections for no reason
            open=True,
        )
    return _pool


def run_read_query(sql: str, params: tuple = ()) -> list[dict]:
    """
    Run one read-only query, return rows as a list of dicts.

    Example:
        run_read_query(
            "SELECT name FROM planet_osm_point WHERE amenity = %s LIMIT %s",
            ("hospital", 10),
        )
        -> [{"name": "Railway Hospital"}, {"name": "Anand Scan Hospital"}]

    Deliberately does NOT catch or reword database errors. Issue 3's agent
    loop needs the RAW Postgres error message ("column x does not exist")
    to read and self-correct -- prettifying the error here would silently
    break that retry loop.
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


@contextmanager
def get_connection():
    """
    Escape hatch for tools needing more than one bound-parameter query --
    specifically Issue 3's run_spatial_query, which validates and runs a
    fully dynamic SQL string handed to it by the agent, rather than a
    fixed query like the one above.
    """
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
