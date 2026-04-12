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

Before applying the Flux Kustomization, create these resources in the cluster (either manually or via GitOps in a cluster config repo):

### 1. GitHub OAuth App

The `usernameMatchingUserEntityName` sign-in resolver requires a GitHub OAuth App **and** matching `User` entities in the Backstage catalog.

Create a GitHub OAuth App at **GitHub > Settings > Developer settings > OAuth Apps > New OAuth App**:

| Field | Value |
|-------|-------|
| Application name | `Backstage <cluster-name>` |
| Homepage URL | `https://backstage.<DOMAIN>` |
| Authorization callback URL | `https://backstage.<DOMAIN>/api/auth/github/handler/frame` |

Copy the **Client ID** and **Client Secret** into the substitution secret (see below).

### 2. Secrets for Flux Variable Substitution

Flux injects these values into the manifests at deploy time via `substituteFrom`. For SOPS-encrypted secrets in a GitOps repo, create a file like `backstage-secrets.yaml`, fill in the values, then encrypt with SOPS:

```yaml
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
  BACKSTAGE_EXTERNAL_ACCESS_TOKEN: "c2Wc7O/7EAxNhMd9…"            #pragma: allowlist secret
```

```bash
# Encrypt with SOPS (replace with your age recipient)
sops --encrypt --age age1... backstage-secrets.yaml > backstage-secrets.enc.yaml
rm backstage-secrets.yaml
```

### 3. Helm Overrides ConfigMap

The image tag is passed via a ConfigMap (not via Flux substitution) because Helm treats bare numeric values like `260218.1436` as floats. Using `valuesFrom` with `targetPath` preserves the string type:

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-helm-overrides
  namespace: backstage
data:
  imageTag: "260218.1436"
```

### 4. Catalog Config ConfigMap

Define which Backstage catalog locations to load. This ConfigMap is mounted as an extra app-config file. The catalog must contain `User` entities whose `metadata.name` matches GitHub usernames for sign-in to work:

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-catalog-config
  namespace: backstage
data:
  app-config.catalog.yaml: |
    catalog:
      locations:
        - type: url
          target: https://github.com/your-org/backstage-resources/blob/main/org/your-instance/org.yaml
          rules:
            - allow: [User, Group]
        - type: url
          target: https://github.com/your-org/backstage-resources/blob/main/services/your-instance/catalog-index.yaml
          rules:
            - allow: [Component, Location, System, API, Resource, Template]
```

### 5. GitRepository Source

Point Flux at this repo so the Kustomization can reference `./apps/backstage`:

```yaml
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
```

## Deploy

Apply a Flux Kustomization that references this path and provides all variable values:

```yaml
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
      BACKSTAGE_NAMESPACE: backstage
      BACKSTAGE_VERSION: "2.6.3"
      BACKSTAGE_IMAGE_REGISTRY: ghcr.io
      BACKSTAGE_IMAGE_REPOSITORY: stuttgart-things/sthings-backstage
      BACKSTAGE_STORAGE_CLASS: nfs4-csi
      BACKSTAGE_REPLICAS: "1"
      BACKSTAGE_APP_TITLE: Stuttgart Things Backstage
      BACKSTAGE_ORGANIZATION_NAME: stuttgart-things
      DOMAIN: sthings-platform.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: sthings-platform-gateway
      GATEWAY_NAMESPACE: default
    substituteFrom:
      - kind: Secret
        name: backstage-secrets-subst
```

## Example: GitOps Deployment (sthings-platform)

This example shows how Backstage was deployed to the `sthings-platform` cluster using the `stuttgart-things` GitOps repo. All files live in `clusters/labul/vsphere/sthings-platform/apps/`:

### backstage-prereqs.yaml

Creates the namespace and the two prerequisite ConfigMaps (applied by the root Flux sync before the Backstage Kustomization reconciles):

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: backstage
  labels:
    toolkit.fluxcd.io/tenant: sthings-team
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-helm-overrides
  namespace: backstage
data:
  imageTag: "260218.1436"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-catalog-config
  namespace: backstage
data:
  app-config.catalog.yaml: |
    catalog:
      locations:
        - type: url
          target: https://github.com/stuttgart-things/backstage-resources/blob/main/org/sthings-dev/org.yaml
          rules:
            - allow: [User, Group]
        - type: url
          target: https://github.com/stuttgart-things/backstage-resources/blob/main/services/sthings-dev/catalog-index.yaml
          rules:
            - allow: [Component, Location, System, API, Resource, Template]
```

### backstage-secrets.enc.yaml

SOPS-encrypted secret with GitHub credentials (encrypted with age):

```yaml
# Before encryption:
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
  BACKSTAGE_GITHUB_CLIENT_SECRET: "..."                       #pragma: allowlist secret
  BACKSTAGE_BACKEND_SECRET: "..."                             #pragma: allowlist secret
  BACKSTAGE_POSTGRESQL_PASSWORD: "..."                        #pragma: allowlist secret
  BACKSTAGE_EXTERNAL_ACCESS_TOKEN: "..."                         #pragma: allowlist secret
```

### backstage.yaml

The Flux Kustomization with all substitution variables:

```yaml
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
      BACKSTAGE_NAMESPACE: backstage
      BACKSTAGE_VERSION: "2.6.3"
      BACKSTAGE_IMAGE_REGISTRY: ghcr.io
      BACKSTAGE_IMAGE_REPOSITORY: stuttgart-things/sthings-backstage
      BACKSTAGE_STORAGE_CLASS: nfs4-csi
      BACKSTAGE_REPLICAS: "1"
      BACKSTAGE_APP_TITLE: Stuttgart Things Backstage
      BACKSTAGE_ORGANIZATION_NAME: stuttgart-things
      DOMAIN: sthings-platform.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: sthings-platform-gateway
      GATEWAY_NAMESPACE: default
    substituteFrom:
      - kind: Secret
        name: backstage-secrets-subst
```

### GitHub OAuth App Settings

| Field | Value |
|-------|-------|
| Application name | `Backstage sthings-platform` |
| Homepage URL | `https://backstage.sthings-platform.sthings-vsphere.labul.sva.de` |
| Authorization callback URL | `https://backstage.sthings-platform.sthings-vsphere.labul.sva.de/api/auth/github/handler/frame` |

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
| `BACKSTAGE_EXTERNAL_ACCESS_TOKEN` | Static external-access token for the `dapr-workflow-service` subject (restricted to `scaffolder` + `catalog` plugins). Consumed by the dapr-workflows/backstage-template-execution app. |

### Helm Override (set in `backstage-helm-overrides` ConfigMap)

| Key | Description |
|-----|-------------|
| `imageTag` | Container image tag, kept as string to avoid YAML float coercion |

## Optional: Internal CA Trust (Vault PKI)

When Backstage needs to call internal services over HTTPS with certificates issued by a private CA (e.g. Vault PKI via cert-manager), Node.js must be configured to trust the CA. This is done by mounting the trust-manager `cluster-trust-bundle` ConfigMap and setting `NODE_EXTRA_CA_CERTS`.

### 1. Create a ConfigMap for the env var

Add to your cluster's `backstage-prereqs.yaml`:

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backstage-ca-env
  namespace: backstage
data:
  NODE_EXTRA_CA_CERTS: /etc/ssl/custom/trust-bundle.pem
```

### 2. Patch the HelmRelease via Kustomization

Add a `patches` block to your cluster's `backstage.yaml` Kustomization:

```yaml
  patches:
    - target:
        kind: HelmRelease
        name: backstage-deployment
      patch: |
        apiVersion: helm.toolkit.fluxcd.io/v2
        kind: HelmRelease
        metadata:
          name: backstage-deployment
        spec:
          values:
            backstage:
              extraVolumes:
                - name: trust-bundle
                  configMap:
                    name: cluster-trust-bundle
                    optional: true
              extraVolumeMounts:
                - name: trust-bundle
                  mountPath: /etc/ssl/custom/trust-bundle.pem
                  subPath: trust-bundle.pem
                  readOnly: true
              extraEnvVarsCM:
                - backstage-ca-env
```

This requires trust-manager to be deployed on the cluster with a `Bundle` resource that populates the `cluster-trust-bundle` ConfigMap.

## Verify

```bash
# Check Flux reconciliation status
kubectl get kustomizations -n flux-system backstage

# Check all three HelmReleases
kubectl get helmreleases -n backstage

# Check running pods
kubectl get pods -n backstage

# Check the HTTPRoute
kubectl get httproutes -n backstage
```
