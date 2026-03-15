# homerun2 / demo-pitcher component

Flux component for homerun2-demo-pitcher. Provides a web UI for manually pitching demo messages to Redis Streams.

## Architecture

```
Browser → demo-pitcher Web UI → Redis Streams → core-catcher / light-catcher
```

## Substitution Variables

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_DEMO_PITCHER_VERSION` | `v1.4.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_DEMO_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |
| `HOMERUN2_REDIS_PASSWORD_B64` | - | yes | Base64-encoded Redis password (from `substituteFrom` Secret) |

## Resources

| Kind | Name | Description |
|------|------|-------------|
| OCIRepository | `homerun2-demo-pitcher-kustomize` | OCI source for the kustomize base |
| Kustomization | `homerun2-demo-pitcher` | Flux Kustomization reconciling the base with patches |
| HTTPRoute | `homerun2-demo-pitcher` | Gateway API ingress route |

## Patches Applied

| Target | Patch |
|--------|-------|
| Ingress (`homerun2-demo-pitcher`) | Delete (replaced by Gateway API HTTPRoute) |
| HTTPRoute (`homerun2-demo-pitcher`) | Delete KCL-generated route (replaced by component-level HTTPRoute) |
| Deployment | Override container image tag |
| Secret (`homerun2-demo-pitcher-redis`) | Override Redis password from variable |
| Deployment | Override `REDIS_ADDR` and `REDIS_PORT` to point to co-deployed redis-stack |

## Example

```yaml
postBuild:
  substitute:
    HOMERUN2_DEMO_PITCHER_VERSION: v1.4.0
    HOMERUN2_DEMO_PITCHER_HOSTNAME: demo-pitcher
  substituteFrom:
    - kind: Secret
      name: homerun2-flux-secrets
```

Resulting endpoint: `https://demo-pitcher.<DOMAIN>`
