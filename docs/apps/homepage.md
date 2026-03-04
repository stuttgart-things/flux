# Homepage

Customizable dashboard with Gateway API support.

## Prerequisites

Create a `homepage-config` ConfigMap in the target namespace with cluster-specific configuration:

- `services.yaml` — Service definitions displayed on the dashboard
- `settings.yaml` — Title, favicon, layout configuration
- `bookmarks.yaml` — Bookmark links
- `kubernetes.yaml` — Kubernetes integration mode
- `widgets.yaml` — Dashboard widgets (cluster/node stats)

See [gethomepage.dev/configs/services](https://gethomepage.dev/configs/services/) for reference.

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
  name: homepage
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homepage
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMEPAGE_NAMESPACE: homepage
      HOMEPAGE_VERSION: "4.8.0"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: home
      DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMEPAGE_NAMESPACE` | `homepage` | Target namespace |
| `HOMEPAGE_VERSION` | `4.8.0` | Helm chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/m0nsterrr/helm-charts`
- Chart-native Gateway API HTTPRoute support via `route.main`
