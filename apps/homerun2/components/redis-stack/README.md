# homerun2/redis-stack

Shared Redis data store with Sentinel HA, RediSearch, RedisJSON, RedisTimeSeries, and Bloom modules. Infrastructure dependency for all other homerun2 services.

## Pattern

HelmRepository + HelmRelease

- **Source:** `oci://ghcr.io/stuttgart-things/charts/redis`
- **Chart:** `redis`

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Target namespace |
| `HOMERUN2_REDIS_VERSION` | `17.1.4` | Helm chart version |
| `HOMERUN2_REDIS_PASSWORD` | *(required)* | Redis password (plaintext) |
| `HOMERUN2_REDIS_SERVICE_TYPE` | `ClusterIP` | Service type |
| `HOMERUN2_REDIS_SENTINEL_REGISTRY` | `ghcr.io` | Sentinel image registry |
| `HOMERUN2_REDIS_SENTINEL_REPOSITORY` | `stuttgart-things/redis-sentinel` | Sentinel image repository |
| `HOMERUN2_REDIS_SENTINEL_VERSION` | `7.4.2-debian-12-r9` | Sentinel image tag |
| `HOMERUN2_REDIS_IMAGE_REGISTRY` | `ghcr.io` | Redis image registry |
| `HOMERUN2_REDIS_IMAGE_REPOSITORY` | `stuttgart-things/redis-stack-server` | Redis image repository |
| `HOMERUN2_REDIS_IMAGE_VERSION` | `7.2.0-v18` | Redis image tag |
| `HOMERUN2_REDIS_PERSISTENCE_ENABLED` | `true` | Enable persistent storage |
| `HOMERUN2_REDIS_STORAGE_CLASS` | `standard` | StorageClass for PVCs |
| `HOMERUN2_REDIS_STORAGE_SIZE` | `8Gi` | PVC size |

## Features

- Master-replica setup with Sentinel for high availability (quorum=1)
- Custom startup scripts loading Redis Stack modules (search, JSON, timeseries, bloom)
- Configurable persistence with StorageClass and size
