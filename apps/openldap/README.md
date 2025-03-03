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
    tag: v1.2.1
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
      OPENLDAP_VERSION: v4.3.2
      OPENLDAP_NAMESPACE: openldap
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
EOF
```
