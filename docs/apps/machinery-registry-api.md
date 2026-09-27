# machinery-registry-api

Read-only REST API over the claim inventory: a `registry.yaml` in a GitHub
repo, polled every `SYNC_INTERVAL` and served at `/api/v1/claims`. Source:
[stuttgart-things/machinery-registry-api](https://github.com/stuttgart-things/machinery-registry-api).

Backstage's `RegistryClaimPicker` (the claim-deletion template) reads it through
the `/machinery-registry` proxy, which `apps/backstage` points at
`CLAIM_MACHINERY_REGISTRY_URL`.

## What gets deployed

- `requirements.yaml`: the namespace and an `OCIRepository` for
  `ghcr.io/stuttgart-things/machinery-registry-api-kustomize`, the app's own KCL
  module rendered at release time.
- `release.yaml`: a Flux `Kustomization` over that artifact. It pins the image
  to the same version, sets the registry source, adds the Reloader annotation,
  and drops the artifact's own `Namespace`.
- `httproute.yaml`: Gateway API route to the Service on port 8090.

## Selecting it

Through the `cicd/platform` bundle, beside `claim-machinery-api`:

```yaml
spec:
  path: ./cicd/platform/root
  components:
    - ../components/machinery-registry-api
```

With `apps/platform`'s `backstage` on the same cluster, the proxy is wired with
no override: both default to `machinery-registry-api.<INFRA_DOMAIN>`.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `MACHINERY_REGISTRY_API_NAMESPACE` | `machinery-registry` | |
| `MACHINERY_REGISTRY_API_VERSION` | `v1.0.0` | Image **and** kustomize artifact tag |
| `MACHINERY_REGISTRY_REPO` | `stuttgart-things/harvester` | GitHub repo slug; must be public (no token is provided) |
| `MACHINERY_REGISTRY_PATH` | `claims/registry.yaml` | |
| `MACHINERY_REGISTRY_BRANCH` | `main` | |
| `MACHINERY_REGISTRY_SYNC_INTERVAL` | `60s` | |
| `HOSTNAME` / `DOMAIN` | *(required)* | Route host; the bundle maps them from `MACHINERY_REGISTRY_API_HOSTNAME` / `INFRA_DOMAIN` |
| `GATEWAY_NAME` / `GATEWAY_NAMESPACE` | *(required)* / `default` | |

## Verify

```bash
curl https://machinery-registry-api.<domain>/health
curl https://machinery-registry-api.<domain>/api/v1/claims
# through Backstage
curl https://backstage.<domain>/api/proxy/machinery-registry/api/v1/claims
```
