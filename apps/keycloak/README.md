# stuttgart-things/flux/keycloak

## SECRET

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
  ADMIN_USER: "admin" #pragma: allowlist secret
  ADMIN_PASSWORD: "Ataln7is" #pragma: allowlist secret
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux-keycloak-dev
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: feature/add-keycloak
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
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
    name: stuttgart-things-flux-keycloak-dev
  path: ./apps/keycloak
  prune: true
  wait: true
  postBuild:
    substitute:
      INGRESS_CLASS: nginx
      INGRESS_DOMAIN: fluxdev-3.sthings-vsphere.example.com
      INGRESS_HOSTNAME: keycloak
      KEYCLOAK_NAMESPACE: keycloak
      KEYCLOAK_VERSION: 24.4.9
      STORAGE_CLASS: nfs4-csi
      CLUSTER_ISSUER: cluster-issuer-approle
    substituteFrom:
      - kind: Secret
        name: keycloak
EOF
```
