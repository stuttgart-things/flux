# homerun2 / profiles / cicd

CI/CD-focused homerun2 deployment: core stack plus Git event watching and service discovery.

## Components

| Component | Description |
|-----------|-------------|
| `redis-stack` | Redis Stack with Sentinel |
| `omni-pitcher` | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | Redis Streams consumer with web dashboard |
| `scout` | Service discovery and monitoring agent |
| `git-pitcher` | Watches GitHub repositories and pitches events to Redis Streams |

## Usage

```yaml
path: ./apps/homerun2/profiles/cicd
```

## Required Variables

See component READMEs for full variable reference. Minimum required beyond core:

| Variable | Description |
|----------|-------------|
| `GATEWAY_NAME` | Gateway parentRef name |
| `DOMAIN` | HTTPRoute domain suffix |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | Omni-pitcher HTTPRoute hostname prefix |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | Core-catcher HTTPRoute hostname prefix |
| `HOMERUN2_SCOUT_HOSTNAME` | Scout HTTPRoute hostname prefix |
| `HOMERUN2_GIT_PITCHER_VERSION` | Git-pitcher OCI + image tag |
| `HOMERUN2_REDIS_PASSWORD` | Redis password (from Secret) |
| `HOMERUN2_REDIS_PASSWORD_B64` | Base64-encoded Redis password (from Secret) |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | Omni-pitcher auth token (from Secret) |
| `HOMERUN2_GIT_PITCHER_GITHUB_TOKEN_B64` | Base64-encoded GitHub PAT (from Secret) |

## Additional Resources

The git-pitcher component deletes the KCL-generated watch ConfigMap. You must provide a cluster-side `homerun2-git-pitcher-watch-config` ConfigMap with the watch profile. See the [git-pitcher component README](../../components/git-pitcher/README.md) for details.
