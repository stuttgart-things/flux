# Keycloak

Identity and access management with TLS certificate support.

## Prerequisites

Create a secret with admin credentials:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: keycloak
  namespace: flux-system
type: Opaque
stringData:
  ADMIN_USER: "admin"
  ADMIN_PASSWORD: "your-secure-password" # pragma: allowlist secret
EOF
```

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
  name: keycloak
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/keycloak
  prune: true
  wait: true
  postBuild:
    substitute:
      KEYCLOAK_NAMESPACE: keycloak
      KEYCLOAK_VERSION: "24.4.9"
      INGRESS_CLASS: nginx
      INGRESS_HOSTNAME: keycloak
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      STORAGE_CLASS: nfs4-csi
      CLUSTER_ISSUER: cluster-issuer-approle
    substituteFrom:
      - kind: Secret
        name: keycloak
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `KEYCLOAK_NAMESPACE` | `keycloak` | Target namespace |
| `KEYCLOAK_VERSION` | `24.4.9` | Helm chart version |
| `ADMIN_USER` | *(required, from secret)* | Admin username |
| `ADMIN_PASSWORD` | *(required, from secret)* | Admin password |
| `INGRESS_CLASS` | `nginx` | Ingress class |
| `INGRESS_HOSTNAME` | `keycloak` | Ingress hostname prefix |
| `INGRESS_DOMAIN` | *(required)* | Ingress domain suffix |
| `STORAGE_CLASS` | *(required)* | StorageClass for PostgreSQL persistence |
| `CLUSTER_ISSUER` | *(required)* | cert-manager ClusterIssuer name |

## Notes

- Uses Bitnami chart from `oci://registry-1.docker.io/bitnamicharts`
- Includes a `certificate.yaml` for TLS via `sthings-cluster` helper chart
- `keycloak-deployment` depends on `keycloak-certificate-configuration`
