# OpenLDAP

OpenLDAP HA stack with configurable replication and persistence.

## Prerequisites

Create a secret with admin credentials:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: openldap
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
  name: openldap
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/openldap
  prune: true
  wait: true
  postBuild:
    substitute:
      OPENLDAP_NAMESPACE: openldap
      OPENLDAP_VERSION: v4.3.2
      REPLICAS: "1"
      SERVICE_TYPE: LoadBalancer
      REPLICATION_ENABLED: "false"
      PERSISTENCE_ENABLED: "true"
      STORAGE_SIZE: 8Gi
      STORAGE_CLASS: nfs4-csi
      TEST_ENABLED: "false"
      LTB_PASSWD_ENABLED: "false" # pragma: allowlist secret
      PHP_ADMIN_ENABLED: "false"
      ENABLE_LDAP_PORT: "true"
      ENABLE_LDAPS_PORT: "false"
    substituteFrom:
      - kind: Secret
        name: openldap
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `OPENLDAP_NAMESPACE` | `openldap` | Target namespace |
| `OPENLDAP_VERSION` | `v4.3.2` | Helm chart version |
| `ADMIN_USER` | `admin` | LDAP admin username |
| `ADMIN_PASSWORD` | *(required, from secret)* | LDAP admin password |
| `REPLICAS` | `1` | Number of replicas |
| `SERVICE_TYPE` | `ClusterIP` | Kubernetes service type |
| `REPLICATION_ENABLED` | `false` | Enable LDAP replication |
| `PERSISTENCE_ENABLED` | `true` | Enable persistent storage |
| `STORAGE_SIZE` | `8Gi` | PVC size |
| `STORAGE_CLASS` | *(required)* | StorageClass for persistence |
| `TEST_ENABLED` | `false` | Enable Helm test pods |
| `LTB_PASSWD_ENABLED` | `false` | Enable LDAP Tool Box password change UI |
| `PHP_ADMIN_ENABLED` | `false` | Enable phpLDAPadmin UI |
| `ENABLE_LDAP_PORT` | `true` | Enable LDAP port (389) |
| `ENABLE_LDAPS_PORT` | `false` | Enable LDAPS port (636) |

## Notes

- Uses HelmRepository from `https://jp-gouin.github.io/helm-openldap/`
- Chart: `openldap-stack-ha`
