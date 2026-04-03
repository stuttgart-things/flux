# homerun2 / profiles / core

Minimal homerun2 deployment: message ingestion, Redis persistence, and web dashboard.

## Components

| Component | Description |
|-----------|-------------|
| `redis-stack` | Redis Stack with Sentinel |
| `omni-pitcher` | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | Redis Streams consumer with web dashboard |
| `scout` | Service discovery and monitoring agent |

## Usage

```yaml
path: ./apps/homerun2/profiles/core
```

## Required Variables

See component READMEs for full variable reference. Minimum required:

| Variable | Description |
|----------|-------------|
| `GATEWAY_NAME` | Gateway parentRef name |
| `DOMAIN` | HTTPRoute domain suffix |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | Omni-pitcher HTTPRoute hostname prefix |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | Core-catcher HTTPRoute hostname prefix |
| `HOMERUN2_SCOUT_HOSTNAME` | Scout HTTPRoute hostname prefix |
| `HOMERUN2_REDIS_PASSWORD` | Redis password (from Secret) |
| `HOMERUN2_REDIS_PASSWORD_B64` | Base64-encoded Redis password (from Secret) |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | Omni-pitcher auth token (from Secret) |
