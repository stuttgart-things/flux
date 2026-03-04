# Infrastructure

Infrastructure components for Kubernetes clusters.

## Components

| Component | Chart | Default Version | Description |
|---|---|---|---|
| [cert-manager](cert-manager.md) | `cert-manager` | `v1.18.2` | TLS certificate management with Vault PKI integration |
| [Cilium](cilium.md) | `cilium` | `1.18.5` | eBPF-based CNI with Gateway API and L2 announcements |
| [ingress-nginx](ingress-nginx.md) | `ingress-nginx` | `4.12.0` | NGINX Ingress Controller |
| [MetalLB](metallb.md) | `metallb` | `6.4.2` | Bare-metal load balancer with IP pool configuration |
| [NFS CSI Driver](nfs-csi.md) | `csi-driver-nfs` | `v4.13.1` | NFS CSI driver with StorageClass provisioning |
| [OpenEBS](openebs.md) | `openebs` | `4.2.0` | Container-attached storage (hostpath) |
| [Prometheus](prometheus.md) | `prometheus` | `28.13.0` | Monitoring with Gateway API HTTPRoute |
| [Vault](vault.md) | `vault` | `1.9.0` | HashiCorp Vault (infra-focused, minimal config) |

## Deployment Order

For a new cluster, a typical deployment order is:

1. **Cilium** or **ingress-nginx** — CNI / ingress controller
2. **MetalLB** — load balancer IPs (if bare-metal)
3. **OpenEBS** or **NFS CSI** — storage
4. **cert-manager** — TLS certificates
5. **Prometheus** — monitoring
6. **Vault** — secrets management
