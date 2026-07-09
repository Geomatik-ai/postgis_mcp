# Architecture

Multi-agent geospatial situational-awareness system with a voice interface.
Full roadmap: see `ROADMAP.md`.

```
Voice (Grok, phone/SIP)      Web console (map + SITREPs)
            \                 /
         LangGraph orchestrator
   [triage] [geo-analyst] [impact] [weather] [report]
                    |
             MCP tool layer
      postgis-mcp · geo-feeds · sentinel-mcp
                    |
   PostGIS (OSM+events) · Mem0 memory · live feeds
   (FIRMS, USGS, Open-Meteo, GDACS, WorldPop)
```

## Core principle

Every capability is an MCP tool built once; text agents, dashboard, and voice all consume
the same tools. Nothing is built twice for a different interface.

## Portability principle

Query templates (the shape of a question) are generic and live in the public repo.
Query bindings (real place names, real amenity types) are discovered live from whichever
database you point the binder at, and stay local per deployment.

## Schema note

This project assumes the classic (non-flex) `osm2pgsql` schema: `planet_osm_point`,
`planet_osm_line`, `planet_osm_polygon`, `planet_osm_roads`. After loading data, verify
with `\dt` in psql — if table names differ (a sign of flex-output), update this note and
the query templates accordingly before Phase 1.

## Data licensing

OpenStreetMap data is ODbL-licensed: attribution required, and any *derivative database*
you redistribute must remain open under ODbL. Verify our usage pattern (querying our own
copy internally, not redistributing the raw database) stays compliant before productizing.
