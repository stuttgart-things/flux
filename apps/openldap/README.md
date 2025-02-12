# stuttgart-things/flux/openldap

## SECRET

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
  ADMIN_USER: "admin" #pragma: allowlist secret
  ADMIN_PASSWORD: "tobeset" #pragma: allowlist secret
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-openldap
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    tag: v1.2.0
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
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
    name: stuttgart-things-openldap
  path: ./apps/openldap
  prune: true
  wait: true
  postBuild:
    substitute:
      REPLICAS: 1
      SERVICE_TYPE: ClusterIP
      REPLICATION_ENABLED: false
      PERSISTENCE_ENABLED: true
      STORAGE_SIZE: 8Gi
      STORAGE_CLASS: nfs4-csi
      TEST_ENABLED: false
      LTB_PASSWD_ENABLED: false
      PHP_ADMIN_ENABLED: false
      ENABLE_LDAP_PORT: true
      ENABLE_LDAPS_PORT: false
    substituteFrom:
      - kind: Secret
        name: openldap
EOF
```
