# stuttgart-things/flux/backstage

## SECRET

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: backstage-secrets-subst
  namespace: flux-system
type: Opaque
stringData:
  BACKSTAGE_GITHUB_TOKEN: "ghp_..." #pragma: allowlist secret
  BACKSTAGE_GITHUB_CLIENT_ID: "Ov23..." #pragma: allowlist secret
  BACKSTAGE_GITHUB_CLIENT_SECRET: "9c20..." #pragma: allowlist secret
  BACKSTAGE_BACKEND_SECRET: "backstage-backend-secret-key-..." #pragma: allowlist secret
  BACKSTAGE_POSTGRESQL_PASSWORD: "backstage" #pragma: allowlist secret
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: main
EOF
```

## HELM OVERRIDES

Create a ConfigMap for values that must stay as strings (e.g. numeric image tags):

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-helm-overrides
  namespace: portal
data:
  imageTag: "260218.1436"
EOF
```

## CATALOG CONFIG

Create a ConfigMap with your catalog locations in the target namespace. Add as many locations as needed:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-catalog-config
  namespace: portal
data:
  app-config.catalog.yaml: |
    catalog:
      locations:
        - type: url
          target: https://github.com/your-org/backstage-resources/blob/main/org/org.yaml
          rules:
            - allow: [User, Group]
        - type: url
          target: https://github.com/your-org/backstage-resources/blob/main/services/catalog-index.yaml
          rules:
            - allow: [Component, Location, System, API, Resource, Template]
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: backstage
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/backstage
  prune: true
  wait: true
  postBuild:
    substitute:
      BACKSTAGE_NAMESPACE: portal
      BACKSTAGE_VERSION: "2.6.3"
      BACKSTAGE_IMAGE_REGISTRY: ghcr.io
      BACKSTAGE_IMAGE_REPOSITORY: stuttgart-things/sthings-backstage
      BACKSTAGE_STORAGE_CLASS: nfs4-csi
      BACKSTAGE_REPLICAS: "1"
      BACKSTAGE_APP_TITLE: Stuttgart Things Backstage
      BACKSTAGE_ORGANIZATION_NAME: stuttgart-things
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
    substituteFrom:
      - kind: Secret
        name: backstage-secrets-subst
EOF
```

## VARIABLES

| Variable | Default | Source | Description |
|----------|---------|--------|-------------|
| `BACKSTAGE_NAMESPACE` | `portal` | substitute | Target namespace |
| `BACKSTAGE_VERSION` | `2.6.3` | substitute | Backstage Helm chart version |
| `BACKSTAGE_IMAGE_TAG` | - | ConfigMap `backstage-helm-overrides` | Container image tag (via `valuesFrom`) |
| `BACKSTAGE_IMAGE_REGISTRY` | `ghcr.io` | substitute | Container image registry |
| `BACKSTAGE_IMAGE_REPOSITORY` | `stuttgart-things/sthings-backstage` | substitute | Container image repository |
| `BACKSTAGE_STORAGE_CLASS` | `nfs4-csi` | substitute | Kubernetes storage class |
| `BACKSTAGE_REPLICAS` | `1` | substitute | Number of replicas |
| `BACKSTAGE_APP_TITLE` | `Stuttgart Things Backstage` | substitute | App title shown in UI |
| `BACKSTAGE_ORGANIZATION_NAME` | `stuttgart-things` | substitute | Organization name |
| `DOMAIN` | - | substitute | Cluster FQDN |
| `GATEWAY_NAME` | - | substitute | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | substitute | Gateway namespace |
| `BACKSTAGE_GITHUB_TOKEN` | - | Secret | GitHub PAT |
| `BACKSTAGE_GITHUB_CLIENT_ID` | - | Secret | GitHub OAuth client ID |
| `BACKSTAGE_GITHUB_CLIENT_SECRET` | - | Secret | GitHub OAuth client secret |
| `BACKSTAGE_BACKEND_SECRET` | - | Secret | Backstage backend auth secret |
| `BACKSTAGE_POSTGRESQL_PASSWORD` | `backstage` | Secret | PostgreSQL password |

## COMPONENTS

| File | Description |
|------|-------------|
| `requirements.yaml` | Namespace + HelmRepositories (backstage, stuttgart-things) |
| `pre-release.yaml` | ConfigMap (app-config) + Secret (env vars) via sthings-cluster chart |
| `httproute.yaml` | HTTPRoute + ReferenceGrant via sthings-cluster chart |
| `release.yaml` | Main Backstage HelmRelease (depends on pre-release) |

## VERIFY

```bash
kubectl get kustomizations -n flux-system backstage
kubectl get helmreleases -n portal
kubectl get pods -n portal
```
