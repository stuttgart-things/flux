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
| `dashboard-guests.json` | Grafana dashboard "Proxmox VE - tagged guests": only guests with the PVE tag in variable `tag` (default `stuttgart-things`), templates excluded -- status/CPU/RAM/disk table plus CPU, RAM, network and disk I/O per VM |

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

## Capacity queries (placement in machinery-order-service)

machinery-order-service ([stuttgart-things#4296](https://github.com/stuttgart-things/stuttgart-things/issues/4296),
[#4299](https://github.com/stuttgart-things/stuttgart-things/issues/4299)) does not
collect anything itself. For a Proxmox `InfraTarget` it runs the queries below
against the Prometheus that scrapes this exporter, **in the same lab** (one service
instance per lab). `{{node}}` and `{{storage}}` come from the InfraTarget;
`{{job}}` is the scrape job, `monitoring/prometheus-pve-exporter` with the
PodMonitor here. All values are absolute (cores, bytes, counts).

### Which guests count as allocated

- **Running guests only, as the maximum of the last 24 h.** Stopped guests do
  not count: many are dormant (on LabUL ul-pve10 the configured RAM of *all*
  guests is about twice the node's RAM), and the `shutdown-step*` tags are on
  almost every VM, so they do not tell a nightly stop from a dormant VM.
- The 24 h maximum covers the lab's nightly auto-shutdown: an order placed at
  night still sees the room taken by the VMs that ran during the day.
- Templates do not count.

The guest selector `R` (running guests of `{{node}}`) used below:

```promql
pve_guest_info{job="{{job}}",node="{{node}}",template="0",type="qemu"}
  and on(id) (pve_up{job="{{job}}"} == 1)
```

Use `and`, not `*`, for such filters: `pve_up == 0` keeps the value 0 and
would zero out everything it is multiplied with.

### Queries

| Value | Query |
|---|---|
| `fresh` (a result = usable) | `time() - max(timestamp(pve_up{job="{{job}}",id="node/{{node}}"})) < 300 and max(up{job="{{job}}"}) == 1 and max(pve_up{job="{{job}}",id="node/{{node}}"}) == 1` |
| `cpuCores` | `pve_cpu_usage_limit{job="{{job}}",id="node/{{node}}"}` |
| `cpuAllocated` (vCPUs) | `max_over_time((sum(pve_cpu_usage_limit{job="{{job}}",id=~"qemu/.*"} * on(id) group_left() (R)) or vector(0))[24h:5m])` |
| `cpuUsed` (cores busy now) | `pve_cpu_usage_ratio{job="{{job}}",id="node/{{node}}"} * pve_cpu_usage_limit{job="{{job}}",id="node/{{node}}"}` |
| `ramTotal` | `pve_memory_size_bytes{job="{{job}}",id="node/{{node}}"}` |
| `ramAllocated` | `max_over_time((sum(pve_memory_size_bytes{job="{{job}}",id=~"qemu/.*"} * on(id) group_left() (R)) or vector(0))[24h:5m])` |
| `ramUsed` | `pve_memory_usage_bytes{job="{{job}}",id="node/{{node}}"}` |
| `storageFree` | `max((pve_disk_size_bytes{job="{{job}}"} - pve_disk_usage_bytes{job="{{job}}"}) * on(id) group_left() pve_storage_info{job="{{job}}",node="{{node}}",storage="{{storage}}"})` |
| `storageTotal` | `max(pve_disk_size_bytes{job="{{job}}"} * on(id) group_left() pve_storage_info{job="{{job}}",node="{{node}}",storage="{{storage}}"})` |
| `vms` (optional) | `count(R) or vector(0)` |

How the service uses them:

- **Filter on allocation, not on load.** `ramFree = ramTotal - ramAllocated`
  (RAM is not overcommitted). `cpuFree = cpuCores × overcommit - cpuAllocated`.
  The overcommit factor (and a RAM reserve, if any) is policy
  (PlacementPolicy / InfraTarget), not part of the query; LabUL runs at
  1.0–1.6 vCPU per core today. `cpuUsed` and `ramUsed` fluctuate and are only
  used for **scoring**.
- **Storage:** shared storages (`pve_storage_shared == 1`, the SAN LVMs and NFS)
  show up once per node with the same value; `max` collapses them, and
  templating with `node` works for local storages too. On thick LVM the usage is
  the allocated LVs; on NFS (qcow2) it is the written data, so thin disks can grow.
- **Stale or empty → skip the target.** No result for `fresh` means the
  exporter is down, the node is offline or the data is older than 5 min.

### Single scrape target

The PodMonitor scrapes **one** host (`PVE_EXPORTER_TARGET`), which answers for
the whole Proxmox cluster. If that host is down, every node goes stale and
nothing is placed on Proxmox. That is deliberate fail-safe behaviour; adding a
second target would duplicate every series.

### Verified (LabUL, 2026-11-11)

Prometheus on platform-sthings against the Proxmox API (`/cluster/resources`):
identical node cores, RAM size/usage, running vCPU/RAM per node and free/total
space per storage.

| Node | Cores | vCPU running (24 h max) | RAM | RAM running (24 h max) |
|---|---|---|---|---|
| ul-pve01 | 88 | 140 (140) | 755.7 GiB | 402.0 GiB (402) |
| ul-pve02 | 88 | 134 (150) | 503.7 GiB | 313.9 GiB (345) |
| ul-pve10 | 56 | 56 (56) | 251.7 GiB | 165.9 GiB (165) |
| ul-pve11 | 56 | 65 (69) | 251.7 GiB | 143.8 GiB (151) |

Storage V5010-01-1 (where machinery-labul builds): 1977 GiB free of 8192 GiB.
