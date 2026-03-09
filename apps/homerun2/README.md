# stuttgart-things/flux/homerun2

Homerun2 application stack using Kustomize Components pattern. Deploys Redis Stack + homerun2 microservices into a shared namespace.

## Components

| Component | Type | Description |
|-----------|------|-------------|
| `redis-stack` | HelmRelease | Redis Stack with Sentinel (integral dependency) |
| `omni-pitcher` | OCIRepository + Flux Kustomization | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer with web dashboard |

## SUBSTITUTION VARIABLES

### Global

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_NAMESPACE` | `homerun2` | no | Shared namespace for all components |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |
| `FLUX_SOURCE_API_VERSION` | `v1` | no | OCIRepository API version (`v1` or `v1beta2`) |

### Redis Stack

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_REDIS_PASSWORD` | - | yes | Redis password (use substituteFrom Secret) |
| `HOMERUN2_REDIS_PASSWORD_B64` | - | yes | Base64-encoded Redis password (for patching KCL secrets) |
| `HOMERUN2_REDIS_VERSION` | `17.1.4` | no | Helm chart version |
| `HOMERUN2_REDIS_SERVICE_TYPE` | `ClusterIP` | no | Redis service type |
| `HOMERUN2_REDIS_PERSISTENCE_ENABLED` | `true` | no | Enable persistence |
| `HOMERUN2_REDIS_STORAGE_CLASS` | `standard` | no | Storage class |
| `HOMERUN2_REDIS_STORAGE_SIZE` | `8Gi` | no | PVC size |
| `HOMERUN2_REDIS_IMAGE_REGISTRY` | `ghcr.io` | no | Redis image registry |
| `HOMERUN2_REDIS_IMAGE_REPOSITORY` | `stuttgart-things/redis-stack-server` | no | Redis image repository |
| `HOMERUN2_REDIS_IMAGE_VERSION` | `7.2.0-v18` | no | Redis image tag |
| `HOMERUN2_REDIS_SENTINEL_REGISTRY` | `ghcr.io` | no | Sentinel image registry |
| `HOMERUN2_REDIS_SENTINEL_REPOSITORY` | `stuttgart-things/redis-sentinel` | no | Sentinel image repository |
| `HOMERUN2_REDIS_SENTINEL_VERSION` | `7.4.2-debian-12-r9` | no | Sentinel image tag |

### Omni Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_OMNI_PITCHER_VERSION` | `v1.2.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### Core Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_CORE_CATCHER_VERSION` | `v0.5.0` | no | Container image tag |
| `HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION` | `v0.5.0` | no | OCI kustomize base tag (use `-web` suffix for web mode) |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

## SECRETS MANIFEST (SOPS ENCRYPTED)

Create a plaintext secret file (e.g., `homerun2-flux-secrets.yaml`):

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun2-flux-secrets
  namespace: flux-system
type: Opaque
stringData:
  HOMERUN2_REDIS_PASSWORD: "your-secure-password" #pragma: allowlist secret
  HOMERUN2_REDIS_PASSWORD_B64: "<base64-encoded-password>" #pragma: allowlist secret
```

Generate the base64 value:

```bash
echo -n 'your-secure-password' | base64
```

Encrypt with SOPS using age (via local sops):

```bash
sops --encrypt \
  --age <AGE_PUBLIC_KEY> \
  --encrypted-regex '^(data|stringData)$' \
  --input-type yaml --output-type yaml \
  homerun2-flux-secrets.yaml > homerun2-flux-secrets.enc.yaml \
  && mv homerun2-flux-secrets.enc.yaml homerun2-flux-secrets.yaml
```

Or encrypt via Dagger:

```bash
# encrypt
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 encrypt \
  --age-key env:SOPS_AGE_KEY \
  --unencrypted-file homerun2-flux-secrets.yaml \
  --encrypted-regex '^(data|stringData)$' \
  export --path=homerun2-flux-secrets.yaml

# decrypt (for verification)
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 decrypt \
  --age-key env:SOPS_AGE_KEY \
  --encrypted-file homerun2-flux-secrets.yaml \
  export --path=/tmp/homerun2-flux-secrets.decrypted.yaml
```

Commit the encrypted file to the cluster repo. Flux will decrypt it at reconciliation time using the `sops-age` secret.

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

## KUSTOMIZATION EXAMPLE

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2-flux
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homerun2
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN2_NAMESPACE: homerun2-flux
      FLUX_SOURCE_API_VERSION: v1beta2
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: my-cluster.example.com
      HOMERUN2_OMNI_PITCHER_VERSION: v1.2.0
      HOMERUN2_OMNI_PITCHER_HOSTNAME: pitcher
      HOMERUN2_CORE_CATCHER_VERSION: v0.5.0
      HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION: v0.5.0-web
      HOMERUN2_CORE_CATCHER_HOSTNAME: catcher
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_SERVICE_TYPE: ClusterIP
      HOMERUN2_REDIS_PERSISTENCE_ENABLED: "true"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
    substituteFrom:
      - kind: Secret
        name: homerun2-flux-secrets
```

## COMPLETE EXAMPLE: MOVIE-SCRIPTS CLUSTER

Full deployment of the homerun2 stack on the `movie-scripts` cluster:

**Cluster config** (`clusters/labul/vsphere/movie-scripts/homerun2-flux.yaml`):

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2-flux
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/homerun2
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN2_NAMESPACE: homerun2-flux
      FLUX_SOURCE_API_VERSION: v1beta2
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
      HOMERUN2_OMNI_PITCHER_VERSION: v1.2.0
      HOMERUN2_OMNI_PITCHER_HOSTNAME: pitcher
      HOMERUN2_CORE_CATCHER_VERSION: v0.5.0
      HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION: v0.5.0-web
      HOMERUN2_CORE_CATCHER_HOSTNAME: catcher
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_SERVICE_TYPE: ClusterIP
      HOMERUN2_REDIS_PERSISTENCE_ENABLED: "true"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
      HOMERUN2_REDIS_IMAGE_REGISTRY: ghcr.io
      HOMERUN2_REDIS_IMAGE_REPOSITORY: stuttgart-things/redis-stack-server
      HOMERUN2_REDIS_IMAGE_VERSION: 7.2.0-v18
      HOMERUN2_REDIS_SENTINEL_REGISTRY: ghcr.io
      HOMERUN2_REDIS_SENTINEL_REPOSITORY: stuttgart-things/redis-sentinel
      HOMERUN2_REDIS_SENTINEL_VERSION: 7.4.2-debian-12-r9
    substituteFrom:
      - kind: Secret
        name: homerun2-flux-secrets
```

**Resulting endpoints:**

| Service | URL |
|---------|-----|
| Omni Pitcher | `https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Core Catcher | `https://catcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Redis Stack | `redis-stack.homerun2-flux.svc.cluster.local:6379` (internal) |

## HOW IT WORKS

Uses the Kustomize Components pattern:

1. **Root kustomization.yaml** composes the components (`redis-stack` + `omni-pitcher` + `core-catcher`)
2. **Outer Flux Kustomization** (consumer) reads `./apps/homerun2` from GitRepository, substitutes variables
3. **Redis Stack component** deploys Redis via HelmRelease into the shared namespace
4. **Omni Pitcher component** creates an OCIRepository + inner Flux Kustomization that reconciles the kustomize base from OCI, patches secrets, overrides image tag, and wires Redis connection
5. **Core Catcher component** same pattern as pitcher — patches secrets, sets `CATCHER_MODE=web`, removes KCL-generated HTTPRoute (replaced by component-level HTTPRoute with custom hostname)

Adding more homerun2 services is done by adding new component folders under `components/`.

## RELATED DOCUMENTATION

- [homerun2-omni-pitcher](https://stuttgart-things.github.io/homerun2-omni-pitcher/) — API gateway docs
- [homerun2-core-catcher](https://stuttgart-things.github.io/homerun2-core-catcher/) — Consumer/dashboard docs
