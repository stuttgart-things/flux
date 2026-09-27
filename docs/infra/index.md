# Infrastructure

Infrastructure components for Kubernetes clusters.

## Components

| Component | Chart | Default Version | Description |
|---|---|---|---|
| [cert-manager](cert-manager.md) | `cert-manager` | `v1.18.2` | TLS certificate management with Vault PKI integration |
| [Cilium](cilium.md) | `cilium` | `1.18.5` | eBPF-based CNI with Gateway API and L2 announcements |
| [NFS CSI Driver](nfs-csi.md) | `csi-driver-nfs` | `v4.13.1` | NFS CSI driver with StorageClass provisioning |
| [OpenEBS](openebs.md) | `openebs` | `4.2.0` | Container-attached storage (hostpath) |
| [Prometheus](prometheus.md) | `prometheus` | `28.13.0` | Monitoring with Gateway API HTTPRoute |
| [Velero](velero.md) | `velero` | `9.0.0` | Cluster + PV backup/restore, S3-compatible (MinIO) |

## Deployment Order

For a new cluster, a typical deployment order is:

1. **Cilium** — CNI, Gateway API and L2 load balancer IPs
2. **OpenEBS** or **NFS CSI** — storage
3. **cert-manager** — TLS certificates
4. **Prometheus** — monitoring
5. **Vault** ([apps/vault](../apps/vault.md)) — secrets management
