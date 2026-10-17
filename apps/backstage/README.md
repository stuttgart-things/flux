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
5. **catalog-config.yaml** - The `backstage-catalog-config` ConfigMap mounted as `app-config.catalog.yaml`, pointing at the `${BACKSTAGE_CATALOG_ORG}` entity files

## Selecting it from the platform bundle

`apps/platform/components/backstage` wraps this path as one line in a cluster's
`apps-platform` Kustomization, mapping the bundle-wide `INFRA_DOMAIN` /
`INFRA_GATEWAY_*` onto the `DOMAIN` / `GATEWAY_*` names below. Everything in
this README still applies — the sections a bundle consumer still has to act on
are the GitHub OAuth app and the substitution Secret.

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

The image tag is passed via a ConfigMap (not via Flux substitution) because Helm treats bare numeric values like `260218.1436` as floats. Using `valuesFrom` with `targetPath` preserves the string type.

**Only numeric tags need it.** The `valuesFrom` entry is `optional: true`, so a
cluster running a `v1.5.1` sets `BACKSTAGE_IMAGE_TAG` and creates no ConfigMap
at all. Where the ConfigMap does exist it still wins over the substituted tag:

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

### 4. Catalog Config ConfigMap — no longer required

`catalog-config.yaml` above now ships this ConfigMap, with the org selected by
`BACKSTAGE_CATALOG_ORG` (default `sthings-dev`). It was a prerequisite because
the Deployment mounts it as a volume: absent, the pod stays in
ContainerCreating while every HelmRelease and Kustomization reports Ready.

A cluster that needs different locations still overrides it, by replacing the
ConfigMap with its own. The shape:

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
| `BACKSTAGE_CPU_REQUEST` | `100m` | CPU request |
| `BACKSTAGE_MEMORY_REQUEST` | `512Mi` | Memory request. Without one the pod is BestEffort: counted as free by the scheduler, evicted first under pressure |
| `BACKSTAGE_CPU_LIMIT` | `1000m` | CPU limit |
| `BACKSTAGE_MEMORY_LIMIT` | `1Gi` | Memory limit. Raise `BACKSTAGE_NODE_OPTIONS` with it, and never below the heap size |
| `BACKSTAGE_NODE_OPTIONS` | `--max-old-space-size=768 --no-node-snapshot` | V8 sizes its heap from the machine's physical memory, not from the cgroup limit, so a Node process on a 16 GB node grows past a 1Gi limit and is OOMKilled instead of collecting garbage. ~75% of the limit is the usual headroom. `--no-node-snapshot` is required by the scaffolder backend on Node 20+: without it every scaffolder template run and dry-run fails with "the scaffolder backend plugin requires that it be started with the --no-node-snapshot option". Override this variable only by keeping BOTH flags |
| `BACKSTAGE_APP_TITLE` | `Stuttgart Things Backstage` | Title shown in the Backstage UI |
| `BACKSTAGE_ORGANIZATION_NAME` | `stuttgart-things` | Organization name shown in UI |
| `DOMAIN` | *(required)* | Cluster base domain (Backstage will be at `backstage.<DOMAIN>`) |
| `GATEWAY_NAME` | *(required)* | Name of the existing Gateway API Gateway resource |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `BACKSTAGE_RAG_AI_ENABLED` | `false` | Turn on Roadie RAG-AI ("Ask AI", image >= `v1.9.0`), see [RAG-AI](#optional-rag-ai) |
| `BACKSTAGE_RAG_PG_HOST` | `rag-postgres-rw` | RAG database service (apps/backstage-rag-postgres) |
| `BACKSTAGE_RAG_PG_PORT` | `5432` | RAG database port |
| `BACKSTAGE_RAG_PG_DATABASE` | `backstage_rag` | RAG database name |
| `BACKSTAGE_RAG_PG_SECRET` | `rag-postgres-creds` | Secret with the RAG owner `username`/`password` |
| `BACKSTAGE_LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint for chat and embeddings (OpenRouter, Ollama `/v1`, vLLM, LiteLLM) |
| `BACKSTAGE_LLM_MODEL` | three free models | Comma-separated chat models, most reliable first |
| `BACKSTAGE_LLM_EMBEDDINGS_MODEL` | `nvidia/nemotron-3-embed-1b:free` | Embeddings model; changing it means re-indexing |
| `BACKSTAGE_LLM_MAX_TOKENS` | `4000` | Max answer tokens |
| `BACKSTAGE_TECHDOCS_BUILDER` | `local` | `external`: Backstage builds no docs, it reads what CI published, see [TechDocs from CI](#optional-techdocs-from-ci) |
| `BACKSTAGE_TECHDOCS_PUBLISHER` | `local` | `awsS3`: read the docs from S3/MinIO |
| `BACKSTAGE_TECHDOCS_S3_BUCKET` | `techdocs` | Bucket CI publishes to |
| `BACKSTAGE_TECHDOCS_S3_ENDPOINT` | *(none)* | S3 endpoint; required with `awsS3`, e.g. the in-cluster MinIO `http://minio-deployment.minio.svc.cluster.local:9000` |
| `BACKSTAGE_TECHDOCS_S3_REGION` | `us-east-1` | Region; MinIO accepts any |

### Secret Variables (set in `backstage-secrets-subst` Secret)

| Variable | Description |
|----------|-------------|
| `BACKSTAGE_GITHUB_TOKEN` | GitHub Personal Access Token for catalog discovery and scaffolder |
| `BACKSTAGE_GITHUB_CLIENT_ID` | GitHub OAuth App client ID (for user login) |
| `BACKSTAGE_GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `BACKSTAGE_BACKEND_SECRET` | Signing key for Backstage backend auth |
| `BACKSTAGE_POSTGRESQL_PASSWORD` | Password for the bundled PostgreSQL instance |
| `BACKSTAGE_EXTERNAL_ACCESS_TOKEN` | Static external-access token for the `dapr-workflow-service` subject (restricted to `scaffolder` + `catalog` plugins). Consumed by the dapr-workflows/backstage-template-execution app. |
| `BACKSTAGE_LLM_API_KEY` | Optional. API key of the LLM endpoint (OpenRouter by default) for RAG-AI; without it RAG-AI answers 503 and the rest of Backstage is unaffected |
| `BACKSTAGE_TECHDOCS_S3_ACCESS_KEY_ID` | Optional. Read-only S3 user for TechDocs from CI (`awsS3` publisher) |
| `BACKSTAGE_TECHDOCS_S3_SECRET_ACCESS_KEY` | Optional. Its secret key |

### Helm Override (set in `backstage-helm-overrides` ConfigMap)

| Key | Description |
|-----|-------------|
| `imageTag` | Container image tag, kept as string to avoid YAML float coercion |

## Optional: RAG-AI

sthings-backstage ships the Roadie RAG-AI plugin (questions on catalog and
TechDocs, "Ask AI" in the sidebar). It is off by default; nothing changes for a
cluster that does not set `BACKSTAGE_RAG_AI_ENABLED`, whatever the image.

Turning it on needs image **`>= v1.9.0`**: this config uses the `LLM_*` names
and the backend module `llm` of sthings-backstage#170. On `v1.8.0` the module
was still called `openrouter`, so `backend.startup` would not cover it and a
missing key would stop the backend.

To turn it on:

1. Deploy [`apps/backstage-rag-postgres`](../backstage-rag-postgres) into the
   same namespace. Its `rag-postgres-creds` Secret is read directly by the
   Backstage pod (`RAG_PG_USER` / `RAG_PG_PASSWORD`).
2. Add `BACKSTAGE_LLM_API_KEY` to the substitution Secret.
3. Set `BACKSTAGE_RAG_AI_ENABLED: "true"` and an image tag `>= v1.9.0`. Through
   the platform bundle (`apps/platform/components/backstage`) the variable is
   passed on, so setting it on the cluster is enough.
4. **Restart Backstage once rag-postgres is Ready.** On the first rollout
   Backstage starts before it: `backstage-rag-postgres` `dependsOn: backstage`
   (which owns the namespace), so `rag-postgres-creds` does not exist yet, the
   optional env vars stay empty, the plugin fails at boot and `continue` keeps
   that quiet -- "Ask AI" then answers 503 until the next restart. After the
   first sync of backstage-rag-postgres:

   ```bash
   kubectl -n portal wait cluster.postgresql.cnpg.io/rag-postgres --for=condition=Ready --timeout=15m
   kubectl -n portal rollout restart deploy/backstage-deployment
   kubectl -n portal logs deploy/backstage-deployment | grep 'RAG-AI enabled'
   ```

   Later restarts need nothing: the Secret and the database are there.
5. Index once (and after documentation changes). RAG-AI does not index on its
   own; the call needs a Backstage user token (the static external-access
   token is restricted to scaffolder and catalog):

   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     https://backstage.<DOMAIN>/api/rag-ai/embeddings/tech-docs \
     -H 'Content-Type: application/json' -d '{"entityFilter":{"kind":"component"}}'
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     https://backstage.<DOMAIN>/api/rag-ai/embeddings/catalog \
     -H 'Content-Type: application/json' -d '{"entityFilter":{"kind":"component"}}'
   ```

**Data privacy:** every question and every indexing run sends catalog entities
and TechDocs pages to the LLM endpoint -- the content leaves the cluster. With
the default free OpenRouter models it goes to third-party providers that may log
prompts or train on them. Acceptable for public/demo content (`sthings-dev`);
for internal documentation turn RAG-AI on only as a conscious decision, or point
`BACKSTAGE_LLM_BASE_URL` at an endpoint you run (e.g. Ollama:
`http://ollama.<ns>.svc:11434/v1`, `BACKSTAGE_LLM_API_KEY` any non-empty value,
then re-index after changing `BACKSTAGE_LLM_EMBEDDINGS_MODEL`).

If the database or the key is missing, the backend starts without RAG-AI
(`backend.startup ... onPluginBootFailure: continue`) instead of failing.
Details: the sthings-backstage README, section "RAG-AI".

## Optional: TechDocs from CI

By default Backstage builds every repo's TechDocs itself, in its own pod
(`builder: local`, mkdocs in the image), on the first visit and again after
each restart. With `builder: external` it builds nothing: each repo's CI builds
its docs with the [techdocs Dagger module](https://github.com/stuttgart-things/dagger/tree/main/techdocs)
and uploads them to a bucket, and Backstage only reads the HTML.

1. Create a bucket (default `techdocs`) and two scoped users on the MinIO:
   one CI user (read, write, delete on the bucket), one read-only user for
   Backstage.
2. In each repo with docs, call the reusable workflow
   `stuttgart-things/github-workflow-templates/.github/workflows/call-techdocs.yaml`:
   `publish: false` on pull requests (a broken `mkdocs.yml` fails the PR),
   `publish: true` on `main` with the CI user's keys.
3. Put the read-only user's keys into the substitution Secret as
   `BACKSTAGE_TECHDOCS_S3_ACCESS_KEY_ID` / `BACKSTAGE_TECHDOCS_S3_SECRET_ACCESS_KEY`.
4. Set on the cluster:
   ```yaml
   BACKSTAGE_TECHDOCS_BUILDER: external
   BACKSTAGE_TECHDOCS_PUBLISHER: awsS3
   BACKSTAGE_TECHDOCS_S3_ENDPOINT: http://minio-deployment.minio.svc.cluster.local:9000
   ```
   In-cluster plain HTTP needs no CA; an external `https://` endpoint signed by
   Vault PKI needs [Internal CA Trust](#optional-internal-ca-trust-vault-pki).

A repo whose CI has not published yet shows "documentation not found" instead
of building on the spot. Docs are found under `<bucket>/<namespace>/<kind>/<name>/`,
lower-cased, from the entity in `catalog-info.yaml` that carries
`backstage.io/techdocs-ref`.

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
