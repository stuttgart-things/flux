# stuttgart-things/flux/apps/minio

Deploys MinIO object storage via the stuttgart-things Helm chart (`charts/minio/minio` v16.0.10).

## Structure

```
minio/
├── kustomization.yaml          # Base: namespace + certs + deployment
├── requirements.yaml           # Namespace + HelmRepository (OCI)
├── pre-release.yaml            # cert-manager Certificates (console + API)
├── release.yaml                # MinIO HelmRelease
└── components/
    └── httproute/              # Optional: Gateway API HTTPRoutes (console + API)
        ├── kustomization.yaml
        └── httproute.yaml
```

## Requirements

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>CREATE SECRET</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: minio-secrets
  namespace: flux-system
type: Opaque
stringData:
  MINIO_ADMIN_USER: "your-username" # pragma: allowlist secret
  MINIO_ADMIN_PASSWORD: "your-password" # pragma: allowlist secret
EOF
```

</details>

## Deployment (with nginx Ingress)

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
    name: flux-apps
  path: ./apps/minio
  prune: true
  wait: true
  postBuild:
    substitute:
      MINIO_NAMESPACE: minio
      MINIO_VERSION: "16.0.10"
      MINIO_INGRESS_ENABLED: "true"
      MINIO_INGRESS_CLASS: nginx
      CLUSTER_ISSUER: cluster-issuer-approle
      INGRESS_HOSTNAME_CONSOLE: artifacts-console
      INGRESS_HOSTNAME_API: artifacts
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      STORAGE_CLASS: nfs4-csi
      MINIO_STORAGE_SIZE: 10Gi
    substituteFrom:
      - kind: Secret
        name: minio-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: minio-deployment
      namespace: minio
EOF
```

## Deployment (with Gateway API HTTPRoute)

For clusters using Cilium Gateway API instead of nginx ingress, deploy the base with ingress disabled plus the httproute component:

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
    name: flux-apps
  path: ./apps/minio
  prune: true
  wait: true
  postBuild:
    substitute:
      MINIO_NAMESPACE: minio
      MINIO_VERSION: "16.0.10"
      MINIO_INGRESS_ENABLED: "false"
      CLUSTER_ISSUER: cluster-issuer-approle
      INGRESS_HOSTNAME_CONSOLE: artifacts-console
      INGRESS_HOSTNAME_API: artifacts
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      STORAGE_CLASS: nfs4-csi
      MINIO_STORAGE_SIZE: 10Gi
    substituteFrom:
      - kind: Secret
        name: minio-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: minio-deployment
      namespace: minio
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: minio-httproute
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/minio/components/httproute
  prune: true
  wait: true
  dependsOn:
    - name: minio
  postBuild:
    substitute:
      MINIO_NAMESPACE: minio
      INGRESS_HOSTNAME_CONSOLE: artifacts-console
      INGRESS_HOSTNAME_API: artifacts
      INGRESS_DOMAIN: example.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
EOF
```

## Optional: OpenID Integration

To enable Keycloak/OpenID authentication, create a ConfigMap before deploying:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: minio-env-config
  namespace: minio
data:
  MINIO_IDENTITY_OPENID_CONFIG_URL: "https://keycloak.example.com/realms/master/.well-known/openid-configuration"
  MINIO_IDENTITY_OPENID_REDIRECT_URI: "https://artifacts-console.example.com/oauth_callback"
  MINIO_IDENTITY_OPENID_CLIENT_ID: minio
  MINIO_IDENTITY_OPENID_SCOPES: openid,profile,email,groups
  MINIO_IDENTITY_OPENID_CLAIM_NAME: preferred_username
EOF
```

Then add `EXTRA_CONFIG_MAP: minio-env-config` to the Kustomization substitutions and uncomment `extraEnvVarsCM` in `release.yaml`.

## Parameters

### Base

| Variable | Default | Description |
|---|---|---|
| `MINIO_NAMESPACE` | `minio` | Target namespace |
| `MINIO_VERSION` | `16.0.10` | Helm chart version (stuttgart-things) |
| `MINIO_REGISTRY` | `ghcr.io` | Container image registry |
| `MINIO_REPOSITORY` | `stuttgart-things/minio` | Container image repository |
| `MINIO_IMAGE_TAG` | `2025.4.22-debian-12-r1` | Container image tag |
| `CLUSTER_ISSUER` | *(required)* | cert-manager ClusterIssuer name |
| `INGRESS_HOSTNAME_CONSOLE` | *(required)* | Console hostname prefix |
| `INGRESS_HOSTNAME_API` | *(required)* | API hostname prefix |
| `INGRESS_DOMAIN` | *(required)* | Base domain |
| `MINIO_INGRESS_ENABLED` | `false` | Enable nginx Ingress (disable when using HTTPRoute) |
| `MINIO_INGRESS_CLASS` | `nginx` | IngressClassName (when ingress enabled) |
| `STORAGE_CLASS` | `nfs4-csi` | StorageClass for persistent volumes |
| `MINIO_STORAGE_SIZE` | `10Gi` | Persistent volume size |
| `MINIO_ADMIN_USER` | *(from Secret)* | MinIO root user |
| `MINIO_ADMIN_PASSWORD` | *(from Secret)* | MinIO root password |

### HTTPRoute Component

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `INGRESS_HOSTNAME_CONSOLE` | *(required)* | Console hostname prefix |
| `INGRESS_HOSTNAME_API` | *(required)* | API hostname prefix |
| `INGRESS_DOMAIN` | *(required)* | Base domain |
| `MINIO_NAMESPACE` | `minio` | Namespace for HTTPRoute resources |

## Endpoints

| Endpoint | Port | Description |
|---|---|---|
| Console | 9001 | MinIO web console UI |
| API (S3) | 9000 | S3-compatible API |

## Claims CLI

```bash
# Render Kustomization
claims render --non-interactive \
-t flux-kustomization-minio \
-p sourceRefName=flux-apps \
-p minioClusterIssuer=vault-pki \
-p minioIngressHostnameConsole=artifacts-console \
-p minioIngressHostnameApi=artifacts \
-p minioIngressDomain=example.sthings-vsphere.labul.sva.de \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"

# Render HTTPRoute
claims render --non-interactive \
-t flux-kustomization-minio-httproute \
-p sourceRefName=flux-apps \
-p minioIngressHostnameConsole=artifacts-console \
-p minioIngressHostnameApi=artifacts \
-p minioIngressDomain=example.sthings-vsphere.labul.sva.de \
-p minioGatewayName=my-gateway \
-o ./apps/ \
--filename-pattern "{{.name}}.yaml"

# Create SOPS-encrypted secret
claims encrypt --non-interactive \
-t flux-kustomization-minio \
--name minio-secrets \
--namespace flux-system \
--param MINIO_ADMIN_USER=admin \
--param MINIO_ADMIN_PASSWORD=<your-password> \
-o ./secrets/
```

See also: [claims CLI](https://github.com/stuttgart-things/claims) | [claim-machinery-api](https://github.com/stuttgart-things/claim-machinery-api)

## Verify Deployment

```bash
# Kustomizations
kubectl get kustomizations -n flux-system minio minio-httproute

# HelmReleases
kubectl get helmreleases -n minio

# Pods
kubectl get pods -n minio

# HTTPRoutes
kubectl get httproutes -n minio

# TLS Certificates
kubectl get certificates -n minio

# Services
kubectl get svc -n minio

# Test S3 API connectivity
curl -sk https://<INGRESS_HOSTNAME_API>.<INGRESS_DOMAIN>/minio/health/live

# Test Console access
curl -sk -o /dev/null -w "%{http_code}" https://<INGRESS_HOSTNAME_CONSOLE>.<INGRESS_DOMAIN>
```
