# stuttgart-things/flux/claim-machinery-api

OCI kustomize-based app using `OCIRepository` + Flux `Kustomization` with Gateway API `HTTPRoute`.

## SUBSTITUTION VARIABLES

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `CLAIM_MACHINERY_API_NAMESPACE` | `claim-machinery` | no | Target namespace |
| `CLAIM_MACHINERY_API_VERSION` | `v0.5.6` | no | OCI tag + container image tag |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `HOSTNAME` | - | yes | HTTPRoute hostname prefix |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    tag: v1.1.0
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
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
    name: stuttgart-things-flux
  path: ./apps/claim-machinery-api
  prune: true
  wait: true
  postBuild:
    substitute:
      CLAIM_MACHINERY_API_NAMESPACE: claim-machinery
      CLAIM_MACHINERY_API_VERSION: v0.5.6
      GATEWAY_NAME: whatever-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: claim-api
      DOMAIN: whatever.sthings-vsphere.labul.sva.de
EOF
```

## HOW IT WORKS

Two-layer Flux reconciliation:

1. **Outer Kustomization** (above) reads `./apps/claim-machinery-api` from the GitRepository, substitutes variables, and creates the Namespace + OCIRepository + inner Kustomization + HTTPRoute on the cluster
2. **Inner Kustomization** (`release.yaml`) reconciles the OCI kustomize base from `ghcr.io/stuttgart-things/claim-machinery-api-kustomize`, patches out the Ingress (replaced by HTTPRoute), overrides the container image tag, and applies the resulting manifests
