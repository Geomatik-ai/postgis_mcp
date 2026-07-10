# PostGIS ships without pgvector by default -- this layers it on.
# postgis/postgis is Debian-based with the PGDG apt repo already configured,
# so the pgvector package is a one-line install.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
