# vCluster

Virtual Kubernetes clusters using the Loft vCluster chart.

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
  name: vcluster
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/vcluster
  prune: true
  wait: true
  postBuild:
    substitute:
      VCLUSTER_NAMESPACE: vcluster
      VCLUSTER_VERSION: "0.29.1"
      VCLUSTER_STORAGE_ENABLED: "true"
      VCLUSTER_STORAGE_SIZE: 10Gi
      VCLUSTER_STORAGE_CLASS: longhorn
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `VCLUSTER_NAMESPACE` | `vcluster` | Target namespace |
| `VCLUSTER_VERSION` | `0.29.1` | Helm chart version |
| `VCLUSTER_STORAGE_ENABLED` | `true` | Enable persistent storage |
| `VCLUSTER_STORAGE_SIZE` | `10Gi` | PVC size |
| `VCLUSTER_STORAGE_CLASS` | *(required)* | StorageClass for persistence |

## Notes

- Uses HelmRepository from `https://charts.loft.sh`
- Creates an isolated virtual Kubernetes cluster within the host cluster
