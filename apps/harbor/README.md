# stuttgart-things/flux/apps/harbor

Deploys Harbor container registry via the Bitnami Helm chart (`harbor` v27.0.3).

## Structure

```
harbor/
├── kustomization.yaml          # Base: namespace + certs + deployment
├── requirements.yaml           # Namespace + HelmRepositories (Bitnami + OCI)
├── pre-release.yaml            # cert-manager Certificate (incl. wildcard for proxy)
├── release.yaml                # Harbor HelmRelease
└── components/
    └── project-proxy/          # Optional: harbor-project-proxy for mirror access
        ├── kustomization.yaml
        ├── requirements.yaml   # HelmRepository for harbor-project-proxy (OCI)
        └── release.yaml        # harbor-project-proxy HelmRelease
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
  name: harbor-secrets
  namespace: flux-system
type: Opaque
stringData:
  HARBOR_ADMIN_PASSWORD: "your-harbor-password" # pragma: allowlist secret
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
  name: harbor
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/harbor
  prune: true
  wait: true
  postBuild:
    substitute:
      HARBOR_NAMESPACE: harbor
      HARBOR_VERSION: "27.0.3"
      HARBOR_HOSTNAME: harbor
      HARBOR_DOMAIN: demo-infra.sthings-vsphere.labul.example.com
      INGRESS_CLASS_NAME: nginx
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
      STORAGE_CLASS: nfs4-csi
      HARBOR_PV_SIZE_REGISTRY: 12Gi
      HARBOR_PV_SIZE_TRIVY: 5Gi
      HARBOR_PV_SIZE_JOBSERVICE: 1Gi
    substituteFrom:
      - kind: Secret
        name: harbor-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: harbor
      namespace: harbor
EOF
```

## Deployment (with nginx Ingress + Project Proxy)

Deploy the base Harbor plus the project-proxy component for mirror access via wildcard subdomains:

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: harbor
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/harbor
  prune: true
  wait: true
  postBuild:
    substitute:
      HARBOR_NAMESPACE: harbor
      HARBOR_VERSION: "27.0.3"
      HARBOR_HOSTNAME: harbor
      HARBOR_DOMAIN: demo-infra.sthings-vsphere.labul.example.com
      INGRESS_CLASS_NAME: nginx
      ISSUER_NAME: cluster-issuer-approle
      ISSUER_KIND: ClusterIssuer
      STORAGE_CLASS: nfs4-csi
      HARBOR_PV_SIZE_REGISTRY: 12Gi
      HARBOR_PV_SIZE_TRIVY: 5Gi
      HARBOR_PV_SIZE_JOBSERVICE: 1Gi
    substituteFrom:
      - kind: Secret
        name: harbor-secrets
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: harbor
      namespace: harbor
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: harbor-project-proxy
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/harbor/components/project-proxy
  prune: true
  wait: true
  dependsOn:
    - name: harbor
  postBuild:
    substitute:
      HARBOR_NAMESPACE: harbor
      HARBOR_HOSTNAME: harbor
      HARBOR_DOMAIN: demo-infra.sthings-vsphere.labul.example.com
      INGRESS_CLASS_NAME: nginx
      HARBOR_PROJECT_PROXY_VERSION: "0.0.1"
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: harbor-project-proxy
      namespace: harbor
EOF

# Harbor UI: https://harbor.demo-infra.sthings-vsphere.labul.example.com
# Default credentials: admin / <HARBOR_ADMIN_PASSWORD>
# Pull via proxy: docker pull <project>.harbor.demo-infra.sthings-vsphere.labul.example.com/library/nginx:latest
# NOTE: Wildcard DNS *.harbor.<domain> must resolve to the ingress LB IP
```

## Parameters

### Base

| Variable | Default | Description |
|---|---|---|
| `HARBOR_NAMESPACE` | `harbor` | Target namespace |
| `HARBOR_VERSION` | `27.0.3` | Bitnami Harbor Helm chart version |
| `HARBOR_HOSTNAME` | *(required)* | Hostname prefix |
| `HARBOR_DOMAIN` | *(required)* | Domain suffix |
| `HARBOR_ADMIN_PASSWORD` | *(from Secret)* | Harbor admin password |
| `INGRESS_CLASS_NAME` | `nginx` | IngressClassName |
| `ISSUER_NAME` | *(required)* | cert-manager ClusterIssuer name |
| `ISSUER_KIND` | `ClusterIssuer` | cert-manager issuer kind |
| `STORAGE_CLASS` | `nfs4-csi` | StorageClass for persistent volumes |
| `HARBOR_PERSISTENCE_ENABLED` | `true` | Enable persistence |
| `HARBOR_PV_SIZE_REGISTRY` | `12Gi` | Registry PV size |
| `HARBOR_PV_SIZE_TRIVY` | `5Gi` | Trivy PV size |
| `HARBOR_PV_SIZE_JOBSERVICE` | `1Gi` | JobService PV size |

### Project Proxy Component

| Variable | Default | Description |
|---|---|---|
| `HARBOR_NAMESPACE` | `harbor` | Target namespace |
| `HARBOR_HOSTNAME` | *(required)* | Hostname prefix (same as base) |
| `HARBOR_DOMAIN` | *(required)* | Domain suffix (same as base) |
| `INGRESS_CLASS_NAME` | `nginx` | IngressClassName |
| `HARBOR_PROJECT_PROXY_VERSION` | `0.0.1` | harbor-project-proxy chart version |

## Verify Deployment

```bash
# Kustomizations
kubectl get kustomizations -n flux-system harbor harbor-project-proxy

# HelmReleases
kubectl get helmreleases -n harbor

# Pods
kubectl get pods -n harbor

# TLS Certificates
kubectl get certificates -n harbor

# Ingresses
kubectl get ingress -n harbor

# Test Harbor UI
curl -sk -o /dev/null -w "%{http_code}" https://<HARBOR_HOSTNAME>.<HARBOR_DOMAIN>

# Test proxy mirror (requires wildcard DNS)
curl -sk -o /dev/null -w "%{http_code}" https://<project>.<HARBOR_HOSTNAME>.<HARBOR_DOMAIN>/v2/
```
