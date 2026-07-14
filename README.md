# postgis-mcp

An MCP (Model Context Protocol) server that lets AI agents answer plain-English
questions about PostGIS data by generating, safely executing, and self-correcting
spatial SQL — without giving the agent write access to anything.

**Status:** early development (Phase 1 of a larger project). Not production-ready.
Built one small GitHub issue at a time — see [Issues](../../issues) and
[Milestones](../../milestones) for exactly what's done and what's next.

## What problem this solves

Spatial SQL is genuinely hard, even for people who already know SQL — coordinate
systems, geography casts, and PostGIS-specific functions trip up experienced
developers regularly (see **Gotchas** below; every one of them was hit for real
while building this). Text-to-SQL agents are an increasingly common pattern, but
most aren't safe enough to hand to an autonomous AI: if the model writes a wrong
or malicious query, application-level checks can be buggy or bypassed.

This project's core idea: **safety enforced by the database itself, not just by
application code.** The AI connects through a role that is *structurally* incapable
of writing data — not "the code checks and refuses," but "the login itself has no
write permission, full stop." Even a successful prompt injection against the agent
can't do damage through this connection.

## Tools

**Planned / in progress:**
| Tool | Purpose | Status |
|---|---|---|
| `get_schema` / `describe_table` | Let the agent see tables, columns, geometry types before querying | Issue #2 |
| `run_spatial_query` | Execute agent-generated SQL safely (validated, capped, timed out) | Issue #3 |
| `geocode_place` | Resolve a place name to coordinates | Issue #4 |

**Currently built:** the read-only database role and pooled connection module
(`db.py`) everything above is built on — proven via automated tests, not just
assumed (see `tests/`).

This project originated as the geospatial-query foundation for a larger
multi-agent disaster-monitoring system, but is designed to be useful on its own
for anyone working with PostGIS and AI agents.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package/project manager)
- `osmium-tool` and `osm2pgsql` (installed automatically by `setup.sh` via Homebrew if missing)
- ~1-2GB free disk space (for the OSM extract + loaded database)

## Getting started

```bash
git clone <this-repo-url>
cd postgis-mcp
uv sync --all-groups                # installs exact dependency versions from uv.lock
cp .env.example .env                # then edit .env with your own local values
./setup.sh                          # builds PostGIS + loads OSM data (~15 min first run)
```

Then create the read-only role (see **known gap** below — this should become
part of `setup.sh` itself):
```bash
docker compose exec -T postgis psql -U gis_admin -d gis < create_reader_role.sql
```

Confirm everything works:
```bash
uv run pytest -v
```

## What you'll need to change, and where

| What | Where | Why you'd change it |
|---|---|---|
| Region and data date | `SNAPSHOT` / `PUNJAB_BBOX` in `setup.sh` | Load a different region, or refresh to newer data |
| Local passwords | `.env` (never commit -- already gitignored) | Your own local secrets |
| Reader role password | `create_reader_role.sql` | Must match `.env`'s `GIS_READER_PASSWORD` exactly |
| Table/column names | query templates (Issue #5+) | Only if you're not using the classic (non-flex) `osm2pgsql` schema |

## What to expect once set up

- A local PostGIS database with real regional OSM data (Punjab by default: ~130k
  points, ~180k polygons, ~677k lines)
- A `gis_reader` role, proven by automated tests to reject writes and enforce a
  query timeout -- not just configured, actually verified
- (as later issues land) an MCP server your LLM client can connect to and query

## Known gotchas (hard-won, worth reading before you hit them yourself)

- **`osm2pgsql` defaults to EPSG:3857** (Web Mercator). Every query in this
  project casts `::geography`, which requires plain lon/lat (EPSG:4326) -- hence
  `--latlong` in `setup.sh`. Skipping it fails with *"Only lon/lat coordinate
  systems are supported in geography."*
- **Homebrew's package is `osmium-tool`, not `osmium`** -- the command is
  `osmium`, but the installable package has a different name than the binary.
- **Apple Silicon platform warning is cosmetic.** The official `postgis/postgis`
  image is amd64-only; Docker runs it via emulation. Safe to ignore at this data scale.
- **India's `admin_level` tagging, verified against real loaded data, not assumed:**
  `4` = state, `5` = district, `6` = tehsil. Don't trust a generic convention --
  check your own data before writing boundary-dependent queries.
- **No Punjab-only extract exists on Geofabrik** -- clip it yourself from the
  Northern Zone or all-India file (`setup.sh` does this automatically).

## Data licensing

OpenStreetMap data is ODbL-licensed: attribution required, and any *derivative
database* you redistribute must remain open under ODbL. This project queries its
own local copy internally rather than redistributing raw OSM data.

## Contributing

This follows a public, phase-based roadmap tracked in GitHub Issues and
Milestones. Each issue is small and scoped to one PR. See open issues for
what's being worked on next.

## License

Apache License 2.0 -- see `LICENSE`.
