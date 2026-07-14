import os
import time
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

READER_DSN = (
    f"host=localhost port=5432 dbname=gis "
    f"user=gis_reader password={os.environ['GIS_READER_PASSWORD']}"
)


def test_reader_role_script_sets_default_privileges_for_future_tables():
    sql_path = Path(__file__).resolve().parents[1] / "create_reader_role.sql"
    sql_text = sql_path.read_text()
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE gis_admin IN SCHEMA public" in sql_text
    assert "GRANT SELECT ON TABLES TO gis_reader" in sql_text


def test_reader_cannot_delete():
    """The core promise of this issue: gis_reader must not be able to write."""
    with psycopg.connect(READER_DSN) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("DELETE FROM planet_osm_point WHERE name = 'test';")


def test_reader_cannot_update():
    with psycopg.connect(READER_DSN) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "UPDATE planet_osm_point SET name = 'hacked' WHERE amenity = 'hospital';"
                )


def test_statement_timeout_kills_slow_query():
    """statement_timeout is set to 10s on the role -- pg_sleep(15) must get killed
    before it finishes, proving the timeout is real and not just configured on paper."""
    with psycopg.connect(READER_DSN) as conn:
        with conn.cursor() as cur:
            start = time.time()
            with pytest.raises(psycopg.errors.QueryCanceled):
                cur.execute("SELECT pg_sleep(15);")
            elapsed = time.time() - start
            assert elapsed < 15, "query ran to completion instead of being cut off early"
