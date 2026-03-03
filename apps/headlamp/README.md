# stuttgart-things/flux/headlamp

## Deployment

```bash
kubectl apply -f - <<EOF
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
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HEADLAMP_NAMESPACE` | `headlamp` | Target namespace |
| `HEADLAMP_VERSION` | `0.40.0` | Helm chart version |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Authentication

Headlamp requires a ServiceAccount token for login. A `ClusterRoleBinding` granting `cluster-admin` to the `headlamp` ServiceAccount is included in this app (rbac.yaml).

Generate a token:

```bash
kubectl create token headlamp -n headlamp --duration=8760h
```

Paste the token into the headlamp login screen.

## Components

- **release.yaml** - HelmRelease from `https://kubernetes-sigs.github.io/headlamp/` with chart-native Gateway API HTTPRoute support
- **rbac.yaml** - ClusterRoleBinding granting `cluster-admin` to the headlamp ServiceAccount
- **requirements.yaml** - Namespace and HelmRepository
