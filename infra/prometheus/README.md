# stuttgart-things/flux/prometheus

## Deployment

```bash
kubectl apply -f - <<EOF
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
    name: flux-infra
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
EOF
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
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Useful PromQL Queries

### PVC / NFS Volume Usage

Used space per PVC (in GiB):

```promql
kubelet_volume_stats_used_bytes / 1024 / 1024 / 1024
```

Usage percentage per PVC:

```promql
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes * 100
```

Available space per PVC (in GiB):

```promql
kubelet_volume_stats_available_bytes / 1024 / 1024 / 1024
```

Filter by namespace:

```promql
kubelet_volume_stats_used_bytes{namespace="vault"} / 1024 / 1024 / 1024
```

Filter by specific PVC:

```promql
kubelet_volume_stats_used_bytes{persistentvolumeclaim="data-vault-server-0"} / 1024 / 1024 / 1024
```

### Cluster Overview

Node CPU usage:

```promql
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Node memory usage percentage:

```promql
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
```

Pod restart count:

```promql
kube_pod_container_status_restarts_total > 0
```

## Components

- **release.yaml** - HelmRelease from `https://prometheus-community.github.io/helm-charts` (standalone prometheus, no Grafana/alertmanager)
- **httproute.yaml** - Gateway API HTTPRoute for Prometheus UI access
- **requirements.yaml** - Namespace and HelmRepository
