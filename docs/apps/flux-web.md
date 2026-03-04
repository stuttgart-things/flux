# Flux Web

Web UI for Flux CD, deployed via the Flux Operator chart.

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
  name: flux-web
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/flux-web
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_WEB_NAMESPACE: flux-system
      FLUX_WEB_VERSION: "0.43.0"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: flux
      DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `FLUX_WEB_NAMESPACE` | `flux-system` | Target namespace |
| `FLUX_WEB_VERSION` | `0.43.0` | Flux Operator chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |

## Notes

- Uses the Flux Operator Helm chart from `oci://ghcr.io/controlplaneio-fluxcd/charts`
- Includes a `NetworkPolicy` for securing access
- Uses Gateway API HTTPRoute for external access
