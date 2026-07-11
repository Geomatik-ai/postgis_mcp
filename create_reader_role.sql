-- create_reader_role.sql

-- 1. Create the login itself.
--    Why LOGIN? A role without LOGIN can't be connected to directly --
--    it's just a permissions bucket. We need this one to actually log in.
--    [FILL IN] the password -- and think about where it should come from.
--    Should it be typed directly into this file? (Hint: this file will
--    live in git. What's a safer place for a real password to live?)
CREATE ROLE gis_reader WITH LOGIN PASSWORD 'dbreader@1234';

-- 2. Cap how long any single query from this role is allowed to run.
--    Why here, on the ROLE, rather than just in application code?
--    Because this way, even a query run manually via psql as gis_reader
--    is still protected -- the limit isn't something the Python code could
--    forget to apply.
ALTER ROLE gis_reader SET statement_timeout = '10s';

-- 3. Let it connect to the database and see the schema at all.
--    (Without these two, it can't do anything, not even SELECT.)
GRANT CONNECT ON DATABASE gis TO gis_reader;
GRANT USAGE ON SCHEMA public TO gis_reader;

-- 4. The actual read access -- SELECT only, nothing else granted.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gis_reader;

-- 5. Make future tables created by gis_admin also inherit the same read access.
--    setup.sh reloads data with --create --drop, meaning osm2pgsql drops and recreates
--    the planet_osm_* tables on every FORCE=1 run. The GRANT above only covers tables
--    that exist right now, so we also set a default privilege for future tables.
ALTER DEFAULT PRIVILEGES FOR ROLE gis_admin IN SCHEMA public
GRANT SELECT ON TABLES TO gis_reader;
