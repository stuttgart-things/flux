# backstage

Deploys [Backstage](https://backstage.io) (Spotify's developer portal) to Kubernetes via Flux CD.

## What Gets Deployed

This Kustomize overlay creates four groups of resources in this order:

1. **requirements.yaml** - Namespace (`portal` by default) and two OCI HelmRepositories (`backstage` chart from `ghcr.io/backstage/charts`, `sthings-cluster` helper chart from `ghcr.io/stuttgart-things`)
2. **pre-release.yaml** - A HelmRelease (`backstage-configuration`) using the `sthings-cluster` helper chart to create:
   - A ConfigMap (`backstage-app-config`) containing the full Backstage `app-config.extra.yaml` (GitHub integration, auth providers, proxy endpoints, catalog rules, etc.)
   - A Secret (`backstage-secrets`) containing all runtime env vars (URLs, GitHub credentials, backend secret)
3. **release.yaml** - The main Backstage HelmRelease (`backstage-deployment`), which `dependsOn` the pre-release. Deploys the Backstage container with PostgreSQL, mounts the app-config ConfigMap, and injects secrets as environment variables
4. **httproute.yaml** - A HelmRelease (`backstage-httproute`) using `sthings-cluster` to create a Gateway API HTTPRoute + ReferenceGrant for external access at `backstage.<DOMAIN>`

## Prerequisites

Before applying the Flux Kustomization, create these resources manually in the cluster:

### 1. Secrets for Flux Variable Substitution

Flux injects these values into the manifests at deploy time via `substituteFrom`:

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
  BACKSTAGE_GITHUB_TOKEN: "ghp_..."                          #pragma: allowlist secret
  BACKSTAGE_GITHUB_CLIENT_ID: "Ov23..."                      #pragma: allowlist secret
  BACKSTAGE_GITHUB_CLIENT_SECRET: "9c20..."                   #pragma: allowlist secret
  BACKSTAGE_BACKEND_SECRET: "backstage-backend-secret-key-…"  #pragma: allowlist secret
  BACKSTAGE_POSTGRESQL_PASSWORD: "backstage"                  #pragma: allowlist secret
EOF
```

### 2. Helm Overrides ConfigMap

The image tag is passed via a ConfigMap (not via Flux substitution) because Helm treats bare numeric values like `260218.1436` as floats. Using `valuesFrom` with `targetPath` preserves the string type:

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

### 3. Catalog Config ConfigMap

Define which Backstage catalog locations to load. This ConfigMap is mounted as an extra app-config file:

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

### 4. GitRepository Source

Point Flux at this repo so the Kustomization can reference `./apps/backstage`:

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

## Deploy

Apply a Flux Kustomization that references this path and provides all variable values:

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
      DOMAIN: my-cluster.example.com
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
    substituteFrom:
      - kind: Secret
        name: backstage-secrets-subst
EOF
```

## Variables Reference

### Flux Substitution Variables (set in `postBuild.substitute`)

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKSTAGE_NAMESPACE` | `portal` | Target Kubernetes namespace |
| `BACKSTAGE_VERSION` | `2.6.3` | Backstage Helm chart version |
| `BACKSTAGE_IMAGE_REGISTRY` | `ghcr.io` | Container image registry |
| `BACKSTAGE_IMAGE_REPOSITORY` | `stuttgart-things/sthings-backstage` | Container image repository |
| `BACKSTAGE_STORAGE_CLASS` | `nfs4-csi` | StorageClass for PostgreSQL PVC |
| `BACKSTAGE_REPLICAS` | `1` | Number of Backstage pod replicas |
| `BACKSTAGE_APP_TITLE` | `Stuttgart Things Backstage` | Title shown in the Backstage UI |
| `BACKSTAGE_ORGANIZATION_NAME` | `stuttgart-things` | Organization name shown in UI |
| `DOMAIN` | *(required)* | Cluster base domain (Backstage will be at `backstage.<DOMAIN>`) |
| `GATEWAY_NAME` | *(required)* | Name of the existing Gateway API Gateway resource |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |

### Secret Variables (set in `backstage-secrets-subst` Secret)

| Variable | Description |
|----------|-------------|
| `BACKSTAGE_GITHUB_TOKEN` | GitHub Personal Access Token for catalog discovery and scaffolder |
| `BACKSTAGE_GITHUB_CLIENT_ID` | GitHub OAuth App client ID (for user login) |
| `BACKSTAGE_GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `BACKSTAGE_BACKEND_SECRET` | Signing key for Backstage backend auth |
| `BACKSTAGE_POSTGRESQL_PASSWORD` | Password for the bundled PostgreSQL instance |

### Helm Override (set in `backstage-helm-overrides` ConfigMap)

| Key | Description |
|-----|-------------|
| `imageTag` | Container image tag, kept as string to avoid YAML float coercion |

## Verify

```bash
# Check Flux reconciliation status
kubectl get kustomizations -n flux-system backstage

# Check all three HelmReleases
kubectl get helmreleases -n portal

# Check running pods
kubectl get pods -n portal

# Check the HTTPRoute
kubectl get httproutes -n portal
```
