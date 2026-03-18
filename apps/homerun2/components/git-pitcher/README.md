# homerun2 / git-pitcher component

Flux component for homerun2-git-pitcher. Watches configured GitHub repositories for events and pitches them to Redis Streams.

## Architecture

```
GitHub API ──poll──> git-pitcher ──pitch──> Redis Streams ──consume──> catchers
```

## Substitution Variables

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_GIT_PITCHER_VERSION` | `v0.4.0` | no | OCI KCL base + container image tag |
| `HOMERUN2_REDIS_PASSWORD_B64` | - | yes | Base64-encoded Redis password (from `substituteFrom` Secret) |
| `HOMERUN2_GIT_PITCHER_GITHUB_TOKEN_B64` | - | yes | Base64-encoded GitHub PAT (from `substituteFrom` Secret) |
| `HOMERUN2_GIT_PITCHER_TRUST_BUNDLE_CM` | `cluster-trust-bundle` | no | ConfigMap name for TLS trust bundle |

## Resources

| Kind | Name | Description |
|------|------|-------------|
| OCIRepository | `homerun2-git-pitcher-kcl` | OCI source for the KCL base |
| Kustomization | `homerun2-git-pitcher` | Flux Kustomization reconciling the base with patches |

## Patches Applied

| Target | Patch |
|--------|-------|
| Deployment | Override container image tag |
| Secret (`homerun2-git-pitcher-redis`) | Override Redis password from variable |
| Secret (`homerun2-git-pitcher-github`) | Override GitHub token from variable |
| Deployment | Mount trust-manager CA bundle |
| Deployment | Override `REDIS_ADDR` and `REDIS_PORT` to point to co-deployed redis-stack |

## Example

```yaml
postBuild:
  substitute:
    HOMERUN2_GIT_PITCHER_VERSION: v0.4.0
  substituteFrom:
    - kind: Secret
      name: homerun2-flux-secrets
```
