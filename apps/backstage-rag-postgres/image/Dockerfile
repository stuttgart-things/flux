# pgvector-enabled operand image for CloudNativePG.
#
# Why this exists: the CNPG community "standard" PostgreSQL images
# (ghcr.io/cloudnative-pg/postgresql:*-standard-bookworm) bundle a useful set
# of extensions but NOT pgvector. The Roadie @roadiehq/rag-ai plugin needs the
# `vector` type/extension to store TechDocs/Catalog embeddings, so we extend the
# standard image with the Debian pgvector package for PostgreSQL 16.
#
# Alternative (not used here): CNPG 1.27+ can mount extensions declaratively via
# the official ghcr.io/cloudnative-pg/pgvector ImageVolume, but that needs the
# Kubernetes ImageVolume feature gate enabled on the kubelet. Building a fat
# operand image keeps this working on any cluster in the fleet.
#
# Build & push (manual — no CI wired yet):
#   docker buildx build \
#     --platform linux/amd64 \
#     -t ghcr.io/stuttgart-things/postgresql-pgvector:16 \
#     --push apps/backstage-rag-postgres/image
#
# Pin PG_MAJOR to match the base image's PostgreSQL major version.
ARG PG_MAJOR=16
FROM ghcr.io/cloudnative-pg/postgresql:${PG_MAJOR}-standard-bookworm

ARG PG_MAJOR

# CNPG runs as uid 26; switch to root only to install the package.
USER root

# DL3008: the pgvector package version tracks the base image's Debian release,
# so pinning it here would break on every base-image bump — intentionally unpinned.
# hadolint ignore=DL3008
RUN apt-get update \
  && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgvector" \
  && rm -rf /var/lib/apt/lists/*

# Drop back to the unprivileged postgres user CNPG expects.
USER 26
