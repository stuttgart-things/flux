# Prometheus

Standalone Prometheus monitoring with Gateway API HTTPRoute.

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
  name: prometheus
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/prometheus
  prune: true
  wait: true
  postBuild:
    substitute:
      PROMETHEUS_NAMESPACE: monitoring
      PROMETHEUS_VERSION: "28.13.0"
      PROMETHEUS_STORAGE_CLASS: nfs4-csi
      PROMETHEUS_STORAGE_SIZE: 10Gi
      PROMETHEUS_RETENTION: 15d
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: prometheus
      DOMAIN: example.sthings-vsphere.labul.sva.de
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_NAMESPACE` | `monitoring` | Target namespace |
| `PROMETHEUS_VERSION` | `28.13.0` | Helm chart version |
| `PROMETHEUS_STORAGE_CLASS` | `nfs4-csi` | StorageClass for persistent volume |
| `PROMETHEUS_STORAGE_SIZE` | `10Gi` | PVC size |
| `PROMETHEUS_RETENTION` | `15d` | Data retention period |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |

## Useful PromQL Queries

PVC usage (GiB):

```promql
kubelet_volume_stats_used_bytes / 1024 / 1024 / 1024
```

PVC usage percentage:

```promql
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes * 100
```

Node CPU usage:

```promql
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Node memory usage:

```promql
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
```

## Notes

- Uses HelmRepository from `https://prometheus-community.github.io/helm-charts`
- Standalone Prometheus (no Grafana/Alertmanager included)
- Uses Gateway API HTTPRoute for UI access
