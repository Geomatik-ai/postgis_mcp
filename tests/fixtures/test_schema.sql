-- tests/fixtures/test_schema.sql
--
-- A minimal schema stub for CI -- NOT real OSM data. Local development tests
-- run against the real Punjab database built by setup.sh; CI can't afford
-- that (slow, depends on an external download succeeding on every PR).
--
-- This exists purely so permission tests fail for the RIGHT reason: without
-- this table, "DELETE FROM planet_osm_point" would error with "relation does
-- not exist" instead of "permission denied" -- a false failure that looks
-- like a bug in gis_reader when it's really just a missing table.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS planet_osm_point (
    osm_id bigint,
    name text,
    amenity text,
    way geometry(Point, 4326)
);
