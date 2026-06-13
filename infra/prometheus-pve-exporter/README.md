# prometheus-pve-exporter

Pull-based Proxmox VE monitoring. The kube-prometheus-stack Prometheus scrapes
[`prometheus-pve-exporter`](https://github.com/prometheus-pve/prometheus-pve-exporter)
at `/pve?target=<host>`; the exporter queries the Proxmox API **read-only** and
returns cluster, node, guest and storage metrics. A Grafana dashboard is shipped
as a ConfigMap and auto-imported by the kps Grafana sidecar.

## Resources

| File | Purpose |
|------|---------|
| `deployment.yaml` | exporter (non-root, read-only rootfs); credentials via `envFrom` secret `prometheus-pve-exporter` |
| `service.yaml` | ClusterIP `:9221` (debugging / port-forward) |
| `podmonitor.yaml` | scrape config; labelled `app.kubernetes.io/component: monitoring` to match the kps `podMonitorSelector` |
| `dashboard.json` | Grafana dashboard (ConfigMap label `grafana_dashboard: "1"`) |

## Required substitutions (Flux `postBuild.substitute`)

Set by the consuming `Kustomization` in the cluster repo:

| Variable | Example | Meaning |
|----------|---------|---------|
| `PVE_EXPORTER_VERSION` | `3.9.0` | container image tag |
| `PVE_EXPORTER_TARGET` | `ul-pve01.labul.sva.de` | Proxmox host scraped via `?target=` |

## Required secret

A `Secret/prometheus-pve-exporter` (namespace `monitoring`) with keys
`PVE_USER`, `PVE_TOKEN_NAME`, `PVE_TOKEN_VALUE` — a read-only PVE API token
(role `PVEAuditor`). Provided SOPS-encrypted from the cluster repo.
