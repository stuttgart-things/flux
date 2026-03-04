# Cilium

eBPF-based CNI with Gateway API, L2 announcements, and kube-proxy replacement.

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
  name: cilium
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/cilium
  prune: true
  wait: true
  postBuild:
    substitute:
      CILIUM_NAMESPACE: kube-system
      CILIUM_CHART_VERSION: "1.18.5"
      CILIUM_KUBE_PROXY_REPLACEMENT: "true"
      CILIUM_API_SERVER_HOST: 10.31.101.8
      CILIUM_API_SERVER_PORT: "6443"
      CILIUM_OPERATOR_REPLICAS: "1"
      CILIUM_GATEWAY_API_ENABLED: "true"
      CILIUM_L2_ANNOUNCEMENTS_ENABLED: "true"
      CILIUM_EXTERNAL_IPS_ENABLED: "true"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CILIUM_NAMESPACE` | `kube-system` | Target namespace |
| `CILIUM_CHART_VERSION` | `1.18.5` | Helm chart version |
| `CILIUM_KUBE_PROXY_REPLACEMENT` | `true` | Replace kube-proxy with Cilium |
| `CILIUM_API_SERVER_HOST` | *(required)* | Kubernetes API server host |
| `CILIUM_API_SERVER_PORT` | `6443` | Kubernetes API server port |
| `CILIUM_OPERATOR_REPLICAS` | `1` | Number of Cilium operator replicas |
| `CILIUM_GATEWAY_API_ENABLED` | `true` | Enable Gateway API support |
| `CILIUM_L2_ANNOUNCEMENTS_ENABLED` | `true` | Enable L2 announcements (replaces MetalLB) |
| `CILIUM_EXTERNAL_IPS_ENABLED` | `true` | Enable external IPs |

## Notes

- Uses HelmRepository from `https://helm.cilium.io`
- Modular kustomization with components: `install`, `lb`, `gateway`
- When using Cilium with Gateway API and L2 announcements, MetalLB is not needed
- `CILIUM_API_SERVER_HOST` must be set to the control plane IP/hostname
