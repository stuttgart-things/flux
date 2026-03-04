# MinIO

S3-compatible object storage with TLS and optional OpenID Connect integration.

## Prerequisites

Create a secret with admin credentials:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: minio
  namespace: flux-system
type: Opaque
stringData:
  MINIO_ADMIN_USER: "your-username"
  MINIO_ADMIN_PASSWORD: "your-password"
EOF
```

Optionally create a `minio-env-config` ConfigMap in the MinIO namespace for OpenID Connect integration with Keycloak.

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
  name: minio
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/minio
  prune: true
  wait: true
  postBuild:
    substitute:
      MINIO_NAMESPACE: minio
      MINIO_VERSION: "16.0.10"
      MINIO_REGISTRY: ghcr.io
      MINIO_REPOSITORY: stuttgart-things/minio
      MINIO_IMAGE_TAG: RELEASE.2024-06-11T00-09-59Z
      INGRESS_HOSTNAME_API: artifacts
      INGRESS_HOSTNAME_CONSOLE: artifacts-console
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      STORAGE_CLASS: nfs4-csi
      CLUSTER_ISSUER: cluster-issuer-approle
      EXTRA_CONFIG_MAP: minio-env-config
    substituteFrom:
      - kind: Secret
        name: minio
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `MINIO_NAMESPACE` | `minio` | Target namespace |
| `MINIO_VERSION` | `16.0.10` | Helm chart version |
| `MINIO_REGISTRY` | `ghcr.io` | Container image registry |
| `MINIO_REPOSITORY` | `stuttgart-things/minio` | Container image repository |
| `MINIO_IMAGE_TAG` | `RELEASE.2024-06-11T00-09-59Z` | Container image tag |
| `MINIO_ADMIN_USER` | *(required, from secret)* | Admin username |
| `MINIO_ADMIN_PASSWORD` | *(required, from secret)* | Admin password |
| `INGRESS_HOSTNAME_API` | *(required)* | API ingress hostname |
| `INGRESS_HOSTNAME_CONSOLE` | *(required)* | Console ingress hostname |
| `INGRESS_DOMAIN` | *(required)* | Ingress domain suffix |
| `STORAGE_CLASS` | `longhorn` | StorageClass for persistence |
| `CLUSTER_ISSUER` | *(required)* | cert-manager ClusterIssuer name |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things`
- Includes a `pre-release.yaml` for TLS certificate via `sthings-cluster` helper chart
- `minio-deployment` depends on `minio-certificate-configuration`
