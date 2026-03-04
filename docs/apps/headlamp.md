# Headlamp

Kubernetes web UI with Gateway API support.

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
  name: headlamp
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/headlamp
  prune: true
  wait: true
  postBuild:
    substitute:
      HEADLAMP_NAMESPACE: headlamp
      HEADLAMP_VERSION: "0.40.0"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: headlamp
      DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HEADLAMP_NAMESPACE` | `headlamp` | Target namespace |
| `HEADLAMP_VERSION` | `0.40.0` | Helm chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |

## Authentication

Headlamp requires a ServiceAccount token for login. A `ClusterRoleBinding` granting `cluster-admin` to the `headlamp` ServiceAccount is included.

Generate a token:

```bash
kubectl create token headlamp -n headlamp --duration=8760h
```

Paste the token into the Headlamp login screen.

## Notes

- Uses HelmRepository from `https://kubernetes-sigs.github.io/headlamp/`
- Includes `rbac.yaml` with ClusterRoleBinding for cluster-admin access
- Chart-native Gateway API HTTPRoute support
