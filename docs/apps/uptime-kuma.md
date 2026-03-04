# Uptime Kuma

Uptime monitoring with auto-configured monitors and Gateway API HTTPRoute.

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
  name: uptime-kuma
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/uptime-kuma
  prune: true
  wait: true
  postBuild:
    substitute:
      UPTIME_KUMA_NAMESPACE: uptime-kuma
      UPTIME_KUMA_VERSION: "4.0.0"
      UPTIME_KUMA_STORAGE_CLASS: nfs4-csi
      UPTIME_KUMA_STORAGE_SIZE: 4Gi
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: uptime
      DOMAIN: example.sthings-vsphere.labul.sva.de
      UPTIME_KUMA_ADMIN_USER: admin
      FLUX_HOSTNAME: flux
      VAULT_HOSTNAME: vault
      CLAIM_API_HOSTNAME: claim-api
      UPTIME_HOSTNAME: uptime
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `UPTIME_KUMA_NAMESPACE` | `uptime-kuma` | Target namespace |
| `UPTIME_KUMA_VERSION` | `4.0.0` | Helm chart version |
| `UPTIME_KUMA_STORAGE_CLASS` | `nfs4-csi` | StorageClass for persistent volume |
| `UPTIME_KUMA_STORAGE_SIZE` | `4Gi` | PVC size |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | HTTPRoute hostname prefix |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |
| `UPTIME_KUMA_ADMIN_USER` | `admin` | Admin username for setup job |
| `FLUX_HOSTNAME` | *(required)* | Hostname of Flux Web UI (for monitor) |
| `VAULT_HOSTNAME` | *(required)* | Hostname of Vault (for monitor) |
| `CLAIM_API_HOSTNAME` | *(required)* | Hostname of Claim Machinery API (for monitor) |
| `UPTIME_HOSTNAME` | *(required)* | Hostname of Uptime Kuma (for monitor) |

## Components

- **release.yaml** — HelmRelease from `https://dirsigler.github.io/uptime-kuma-helm`
- **httproute.yaml** — Gateway API HTTPRoute
- **setup-job.yaml** — Job that auto-generates an admin password (stored in Secret `uptime-kuma-admin`), creates the admin account, and configures HTTP monitors for cluster services using the `uptime-kuma-api` Python library
