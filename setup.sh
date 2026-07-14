#!/usr/bin/env bash
#
# setup.sh — one-command reproducible database bootstrap (Infrastructure as Code)
#
# What this does, start to finish:
#   1. Checks required tools exist (Docker, osmium, osm2pgsql); installs via Homebrew if missing
#   2. Starts the PostGIS container (docker compose) and waits until it's actually ready
#   3. Downloads a PINNED, dated OSM snapshot (so every teammate gets IDENTICAL data)
#   4. Verifies the download against Geofabrik's published MD5 checksum
#   5. Clips the Punjab region out of the Northern Zone file
#   6. Loads Punjab into PostGIS (skipped if data already loaded — use FORCE=1 to reload)
#   7. Creates the read-only gis_reader role (skipped if it already exists)
#   8. Runs a verification query to PROVE the pipeline worked
#
# To update the team's data version: bump SNAPSHOT below, commit, everyone reruns
# with FORCE=1. Then regenerate eval ground truth (bind_examples.py + generate_golden.py),
# because golden answers are tied to the data version they were generated from.
#
# Snapshot retention note (verified on Geofabrik, Jul 2026): January-1st snapshots are
# kept for YEARS; first-of-month snapshots survive within the current year; daily files
# are pruned after ~a week. Pin to a monthly (fresh) or a Jan-1 file (longest-lived).
# If a pinned URL ever 404s, move to the nearest surviving dated file.

set -euo pipefail   # stop immediately on any error, undefined variable, or failed pipe

# Load .env if present, so GIS_READER_PASSWORD (and anything else) is available
# to this script exactly the way python-dotenv makes it available to db.py.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ---------------- configuration (the ONLY things you should need to edit) ----------------
SNAPSHOT="260701"                                  # YYMMDD — Geofabrik dated snapshot to pin
REGION_URL_BASE="https://download.geofabrik.de/asia/india"
REGION_FILE="northern-zone-${SNAPSHOT}.osm.pbf"    # 221MB zone containing Punjab (vs 1.6GB all-India)
PUNJAB_BBOX="73.8,29.5,76.9,32.5"                  # min_lon,min_lat,max_lon,max_lat (approximate)

DB_NAME="gis"
DB_USER="gis_admin"
DB_PORT="5432"
COMPOSE_SERVICE="postgis"                          # service name in docker-compose.yml
DATA_DIR="./data"                                  # gitignored — large files never enter git
# ------------------------------------------------------------------------------------------

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- 1. prerequisites -----------------------------------------------------------------
log "Checking prerequisites"

command -v brew >/dev/null 2>&1 || fail "Homebrew not found. Install it from https://brew.sh first."

for tool in osmium osm2pgsql; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    # NOTE: the command is "osmium" but the Homebrew PACKAGE is "osmium-tool"
    # (libosmium is a different package - just the underlying library, no CLI).
    # osm2pgsql's command name and package name happen to match, so no mapping needed there.
    case "$tool" in
      osmium) brew_pkg="osmium-tool" ;;
      *)      brew_pkg="$tool" ;;
    esac
    log "Installing missing tool: $tool (brew package: $brew_pkg)"
    brew install "$brew_pkg"
  fi
done

command -v docker >/dev/null 2>&1 || fail "Docker not found. Run: brew install --cask docker, then open Docker.app once."
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Open Docker.app and wait for the whale icon."

# ---- 2. start the database and wait until it's genuinely ready --------------------------
log "Starting PostGIS container"
docker compose up -d --build

log "Waiting for the database to accept connections"
for i in $(seq 1 60); do
  if docker compose exec -T "$COMPOSE_SERVICE" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    break
  fi
  [ "$i" -eq 60 ] && fail "Database did not become ready within 60 seconds."
  sleep 1
done
log "Database is ready"

# ---- 3 + 4. download the pinned snapshot and verify its checksum ------------------------
mkdir -p "$DATA_DIR"

if [ -f "$DATA_DIR/$REGION_FILE" ]; then
  log "Snapshot already downloaded: $REGION_FILE (skipping download)"
else
  log "Downloading pinned snapshot $REGION_FILE (~221MB)"
  # -C - makes the download RESUMABLE if your connection drops halfway
  curl -fL -C - -o "$DATA_DIR/$REGION_FILE" "$REGION_URL_BASE/$REGION_FILE" \
    || fail "Download failed. If it's a 404, this snapshot may have been pruned — pick a newer date or a Jan-1 snapshot."
fi

log "Verifying checksum"
curl -fsL -o "$DATA_DIR/$REGION_FILE.md5" "$REGION_URL_BASE/$REGION_FILE.md5"
expected_md5=$(awk '{print $1}' "$DATA_DIR/$REGION_FILE.md5")
if command -v md5sum >/dev/null 2>&1; then                # Linux
  actual_md5=$(md5sum "$DATA_DIR/$REGION_FILE" | awk '{print $1}')
else                                                       # macOS
  actual_md5=$(md5 -q "$DATA_DIR/$REGION_FILE")
fi
[ "$expected_md5" = "$actual_md5" ] || fail "Checksum mismatch — file is corrupt or incomplete. Delete $DATA_DIR/$REGION_FILE and rerun."
log "Checksum OK"

# ---- 5. clip Punjab out of the zone file -------------------------------------------------
PUNJAB_FILE="$DATA_DIR/punjab-${SNAPSHOT}.osm.pbf"
if [ -f "$PUNJAB_FILE" ]; then
  log "Punjab clip already exists: $PUNJAB_FILE (skipping clip)"
else
  log "Clipping Punjab (bbox: $PUNJAB_BBOX)"
  osmium extract -b "$PUNJAB_BBOX" "$DATA_DIR/$REGION_FILE" -o "$PUNJAB_FILE"
fi

# ---- 6. load into PostGIS (idempotent: skips if already loaded) --------------------------
tables_exist=$(docker compose exec -T "$COMPOSE_SERVICE" \
  psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT to_regclass('public.planet_osm_point');")

if [ "$tables_exist" = "planet_osm_point" ] && [ "${FORCE:-0}" != "1" ]; then
  log "OSM tables already loaded — skipping import. (Rerun with FORCE=1 ./setup.sh to reload.)"
else
  log "Loading Punjab into PostGIS (a few minutes)"
  # --slim keeps import memory low; --drop deletes the intermediate tables afterwards,
  # keeping the final database small. Our update strategy is full reloads, so we don't
  # need the incremental-update tables that --drop removes.
  # --latlong: store geometries in plain lon/lat (EPSG:4326) instead of osm2pgsql's
  # default Web Mercator (EPSG:3857). Every query in this project casts way::geography,
  # which REQUIRES 4326 -- without this flag, that cast fails with:
  # "ERROR: Only lon/lat coordinate systems are supported in geography."
  PGPASSWORD="${PGPASSWORD:-change_me_locally}" osm2pgsql \
    -d "$DB_NAME" -U "$DB_USER" -H localhost -P "$DB_PORT" \
    --create --slim --drop --latlong \
    "$PUNJAB_FILE"
fi

# ---- 7. create the read-only gis_reader role (idempotent: skips if it exists) ------------
role_exists=$(docker compose exec -T "$COMPOSE_SERVICE" \
  psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM pg_roles WHERE rolname='gis_reader';")

if [ "$role_exists" = "1" ]; then
  log "gis_reader role already exists — skipping creation"
  log "(default privileges already ensure it can read tables recreated by future reloads)"
else
  : "${GIS_READER_PASSWORD:?GIS_READER_PASSWORD not set. Copy .env.example to .env and set it before running setup.sh}"
  log "Creating read-only gis_reader role"
  docker compose exec -T "$COMPOSE_SERVICE" \
    psql -U "$DB_USER" -d "$DB_NAME" -v reader_password="$GIS_READER_PASSWORD" \
    < create_reader_role.sql
  log "gis_reader role created"
fi

# ---- 8. verify with a real query ---------------------------------------------------------
log "Verification: hospitals within 5km of Ludhiana Junction"
docker compose exec -T "$COMPOSE_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" -c "
  SELECT p.name,
         round(ST_Distance(p.way::geography, g.way::geography)) AS distance_m
  FROM planet_osm_point p, planet_osm_point g
  WHERE p.amenity = 'hospital'
    AND g.name ILIKE '%Ludhiana Junction%'
    AND ST_DWithin(p.way::geography, g.way::geography, 5000)
  ORDER BY distance_m
  LIMIT 10;"

log "Row counts per table"
docker compose exec -T "$COMPOSE_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" -c "
  SELECT 'points'   AS tbl, count(*) FROM planet_osm_point
  UNION ALL SELECT 'lines',    count(*) FROM planet_osm_line
  UNION ALL SELECT 'polygons', count(*) FROM planet_osm_polygon;"

log "Done. Connection string: postgresql://$DB_USER:<password>@localhost:$DB_PORT/$DB_NAME"
log "Data version: $SNAPSHOT (pinned in this script — bump it to update everyone)"
