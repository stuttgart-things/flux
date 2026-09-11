# homerun2 / profiles / base

Minimal homerun2 deployment: message ingestion, Redis persistence, notification
fan-out, and the web dashboard.

## Components

| Component | Description |
|-----------|-------------|
| `redis-stack` | Redis Stack with Sentinel |
| `omni-pitcher` | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | Redis Streams consumer with web dashboard |
| `notification-catcher` | Redis Streams consumer that forwards messages as notifications |
| `scout` | Service discovery and monitoring agent |

## Usage

Two Flux Kustomizations: the stack, then its HTTPRoutes from
[`profiles/base-routes`](../base-routes/kustomization.yaml) once the stack is
Ready.

```yaml
# homerun2-base-stack
path: ./apps/homerun2/profiles/base
wait: true
---
# homerun2-base-routes
path: ./apps/homerun2/profiles/base-routes
dependsOn:
  - name: homerun2-base-stack
wait: true
```

The routes cannot ride along. Cilium resolves an HTTPRoute's backendRefs once;
the Services here are created by child Kustomizations seconds after the parent
applies, and a route that got there first serves HTTP 500 for good while
everything reports Ready. The stack Kustomization is Ready only when its
children are, so `dependsOn` covers the Services.

**Moving an existing install** (routes were in this profile before): the stack
Kustomization prunes them before `base-routes` recreates them -- a short 404.
Annotate the live routes with `kustomize.toolkit.fluxcd.io/prune=disabled`
first and `base-routes` adopts them instead (platform-sthings, 2026-09-11: no
404). Flux strips the kubectl-set annotation itself on its next apply.

To add Git event watching, deploy [`profiles/cicd`](../cicd/README.md) as a
**second** Flux Kustomization alongside this one — it is an add-on that carries
only `git-pitcher`, not a superset of this profile.

## Required Variables

See component READMEs for full variable reference. Minimum required:

| Variable | Description |
|----------|-------------|
| `GATEWAY_NAME` | Gateway parentRef name (base-routes) |
| `DOMAIN` | HTTPRoute domain suffix (base-routes) |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | Omni-pitcher HTTPRoute hostname prefix |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | Core-catcher HTTPRoute hostname prefix |
| `HOMERUN2_SCOUT_HOSTNAME` | Scout HTTPRoute hostname prefix |
| `HOMERUN2_REDIS_PASSWORD` | Redis password (from Secret) |
| `HOMERUN2_REDIS_PASSWORD_B64` | Base64-encoded Redis password (from Secret) |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | Omni-pitcher auth token (from Secret) |
