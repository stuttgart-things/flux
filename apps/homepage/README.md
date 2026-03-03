# stuttgart-things/flux/homepage

## Deployment

```bash
kubectl apply -f - <<EOF
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
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMEPAGE_NAMESPACE` | `homepage` | Target namespace |
| `HOMEPAGE_VERSION` | `4.8.0` | Helm chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Prerequisites

This app expects a ConfigMap named `homepage-config` to exist in the target namespace. The ConfigMap is cluster-specific and should be created on the cluster side (not in this repo). It must contain the following keys:

- `services.yaml` - Service definitions displayed on the dashboard
- `settings.yaml` - Title, favicon, layout configuration
- `bookmarks.yaml` - Bookmark links
- `kubernetes.yaml` - Kubernetes integration mode (e.g. `mode: cluster`)
- `widgets.yaml` - Dashboard widgets (cluster/node stats)

See [gethomepage.dev/configs/services](https://gethomepage.dev/configs/services/) for service configuration reference.

## Components

- **release.yaml** - HelmRelease from `oci://ghcr.io/m0nsterrr/helm-charts` with chart-native Gateway API HTTPRoute support (`route.main`)
- **requirements.yaml** - Namespace and OCI HelmRepository
