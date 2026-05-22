# stuttgart-things/flux/kube-prometheus-stack

Full observability stack — Prometheus + Alertmanager + Grafana + node-exporter
+ kube-state-metrics + prometheus-operator — from the
[`kube-prometheus-stack`](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
chart.

Replaces the standalone `infra/prometheus` component (see [Cutover](#cutover)).

## Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: kube-prometheus-stack
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 15m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/kube-prometheus-stack
  prune: true
  wait: true
  postBuild:
    substitute:
      KPS_NAMESPACE: monitoring
      KPS_VERSION: "85.2.1"
      KPS_PROMETHEUS_STORAGE_CLASS: nfs4-csi
      KPS_PROMETHEUS_STORAGE_SIZE: 10Gi
      KPS_PROMETHEUS_RETENTION: 15d
      KPS_SCRAPE_INTERVAL: 60s
      KPS_GRAFANA_ADMIN_PASSWORD: prom-operator
      GATEWAY_NAME: platform-sthings-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: grafana
      DOMAIN: platform.sthings-vsphere.labul.sva.de
EOF
```

Grafana is then reachable at `https://grafana.platform.sthings-vsphere.labul.sva.de`
(login `admin` / `KPS_GRAFANA_ADMIN_PASSWORD`).

## Variables

| Variable | Default | Description |
|---|---|---|
| `KPS_NAMESPACE` | `monitoring` | Target namespace |
| `KPS_VERSION` | `85.2.1` | Helm chart version |
| `KPS_PROMETHEUS_STORAGE_CLASS` | `nfs4-csi` | StorageClass for the Prometheus TSDB PVC |
| `KPS_PROMETHEUS_STORAGE_SIZE` | `10Gi` | Prometheus PVC size |
| `KPS_PROMETHEUS_RETENTION` | `15d` | Metrics retention period |
| `KPS_SCRAPE_INTERVAL` | `60s` | Global scrape + rule evaluation interval |
| `KPS_GRAFANA_ADMIN_PASSWORD` | `prom-operator` | Grafana admin password (see note below) |
| `GATEWAY_NAME` | *(required)* | Cilium Gateway resource name for the HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for the Grafana HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for the Grafana HTTPRoute |

## Design notes — keeping it lean

- **One replica each** for Prometheus, Alertmanager, Grafana and the operator.
- **`scrapeInterval: 60s`** (chart default is 30s) — roughly halves scrape CPU
  and TSDB write volume.
- **Grafana is ephemeral** (`persistence.enabled: false`) — the bundled
  dashboards are re-provisioned from ConfigMaps on every start, so no PVC is
  needed.
- **Alertmanager is ephemeral** (emptyDir) — silences do not survive a restart.
- **Control-plane scrape jobs disabled** (`kubeProxy`, `kubeControllerManager`,
  `kubeScheduler`, `kubeEtcd`) — Cilium runs kube-proxy-replacement and RKE2
  binds control-plane metrics to localhost, so these would only generate
  `TargetDown` noise.
- Modest CPU/memory **requests + limits** on every component. Total resource
  *requests* are ≈ 200m CPU / ≈ 800Mi memory across the cluster.

### Pods this deploys

| Component | Pods |
|---|---|
| prometheus-operator | 1 |
| Prometheus | 1 (StatefulSet) |
| Alertmanager | 1 (StatefulSet) |
| Grafana | 1 |
| kube-state-metrics | 1 |
| node-exporter | 1 per node (DaemonSet) |

On a 4-node cluster: **9 pods**. The replaced `infra/prometheus` ran 6
(prometheus-server + kube-state-metrics + 4× node-exporter), so the net
addition is 3 pods (operator, Alertmanager, Grafana) for full dashboards +
alerting.

## Predefined dashboards

`grafana.defaultDashboardsEnabled: true` ships the standard set: Kubernetes
Compute Resources (Cluster / Namespace / Node / Pod / Workload), Node Exporter
(Nodes / USE Method), kube-apiserver, Kubelet, Persistent Volumes, CoreDNS,
Prometheus and Alertmanager overviews. The Prometheus datasource is
auto-provisioned. Add more dashboards by creating a ConfigMap labelled
`grafana_dashboard: "1"` in the namespace — the Grafana sidecar imports it.

## Alerting

The chart's `defaultRules` are enabled, so alerts like `KubePodCrashLooping`,
`TargetDown` and `KubePersistentVolumeFillingUp` evaluate out of the box.
**Alertmanager currently routes to a null receiver** — wire real receivers
(Slack / email / webhook) by adding an `alertmanager.config` block to
`release.yaml`.

## Cutover

`kube-prometheus-stack` **cannot run alongside** the old `infra/prometheus`:
both deploy a node-exporter DaemonSet that binds host port `9100`, and both
manage a `prometheus-community` `HelmRepository` in `monitoring`. Cut over in
order:

1. Merge this component.
2. Remove the **old** `prometheus` Flux Kustomization (with `prune: true` it
   tears down the old release):
   ```bash
   flux delete kustomization prometheus -n flux-system
   ```
3. Apply the `kube-prometheus-stack` Kustomization (see [Deployment](#deployment)).
4. **Repoint Headlamp** at the new Prometheus service. The old service was
   `prometheus-server.monitoring.svc:80`; the new one is
   `kube-prometheus-stack-prometheus.monitoring.svc:9090`.
5. Once verified, delete the `infra/prometheus` directory from this repo.

## CRD note

The prometheus-operator CRDs are large. If a chart upgrade ever fails with
`metadata.annotations: Too long`, install the CRDs via a dedicated Flux
Kustomization (raw manifests from the chart's `charts/crds`) and set
`crds.enabled: false` in `release.yaml`.

## Components

- **requirements.yaml** — Namespace + `prometheus-community` HelmRepository
- **release.yaml** — `kube-prometheus-stack` HelmRelease (tuned values)
- **httproute.yaml** — Gateway API HTTPRoute exposing Grafana
