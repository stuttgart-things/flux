# stuttgart-things/flux/minio

## SECRET

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
  MINIO_ADMIN_USER: "your-secure-username" #pragma: allowlist secret
  MINIO_ADMIN_PASSWORD: "your-secure-password" #pragma: allowlist secret
EOF
```

## EXTRA CONFIG

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Namespace
metadata:
  name: minio
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: minio-env-config
  namespace: minio
data:
  MINIO_IDENTITY_OPENID_CONFIG_URL: "https://keycloak.fluxdev-3.sthings-vsphere.labul.example.com/realms/master/.well-known/openid-configuration"
  MINIO_IDENTITY_OPENID_REDIRECT_URI: "https://artifacts-console.fluxdev-3.sthings-vsphere.labul.example.com/oauth_callback"
  MINIO_IDENTITY_OPENID_CLIENT_ID: minio
  MINIO_IDENTITY_OPENID_SCOPES: openid,profile,email,groups
  MINIO_IDENTITY_OPENID_CLAIM_NAME: preferred_username
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux-minio-dev
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: feat/add-minio
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
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
    name: stuttgart-things-flux-minio-dev
  path: ./apps/minio
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTER_ISSUER: cluster-issuer-approle
      INGRESS_DOMAIN: fluxdev-3.sthings-vsphere.labul.example.com
      INGRESS_HOSTNAME_API: artifacts
      INGRESS_HOSTNAME_CONSOLE: artifacts-console
      MINIO_NAMESPACE: minio
      MINIO_VERSION: 14.8.0
      STORAGE_CLASS: nfs4-csi
      EXTRA_CONFIG_MAP: minio-env-config
    substituteFrom:
      - kind: Secret
        name: minio
EOF
```
