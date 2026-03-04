# Claim Machinery API

OCI kustomize-based app using `OCIRepository` + Flux `Kustomization` with Gateway API `HTTPRoute`.

## Deployment

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: claim-machinery-api
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/claim-machinery-api
  prune: true
  wait: true
  postBuild:
    substitute:
      CLAIM_MACHINERY_API_NAMESPACE: claim-machinery
      CLAIM_MACHINERY_API_VERSION: v0.5.6
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: claim-api
      DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CLAIM_MACHINERY_API_NAMESPACE` | `claim-machinery` | Target namespace |
| `CLAIM_MACHINERY_API_VERSION` | `v0.5.6` | OCI tag + container image tag |
| `GATEWAY_NAME` | *(required)* | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | Gateway parentRef namespace |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |

## How It Works

Two-layer Flux reconciliation:

1. **Outer Kustomization** reads `./apps/claim-machinery-api` from the GitRepository, substitutes variables, and creates the Namespace + OCIRepository + inner Kustomization + HTTPRoute
2. **Inner Kustomization** (`release.yaml`) reconciles the OCI kustomize base from `ghcr.io/stuttgart-things/claim-machinery-api-kustomize`, patches out the Ingress (replaced by HTTPRoute), overrides the container image tag, and applies the resulting manifests

## Notes

- This is the only app using the OCIRepository pattern
- Uses Gateway API HTTPRoute instead of Ingress
