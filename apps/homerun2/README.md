# stuttgart-things/flux/homerun2

Homerun2 application stack using Kustomize Components pattern. Deploys Redis Stack + homerun2 microservices into a shared namespace.

## Components

| Component | Type | Description |
|-----------|------|-------------|
| `redis-stack` | HelmRelease | Redis Stack with Sentinel (integral dependency) |
| `omni-pitcher` | OCIRepository + Flux Kustomization | HTTP gateway for Redis Stream ingestion |
| `core-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer with web dashboard |
| `k8s-pitcher` | OCIRepository + Flux Kustomization | K8s cluster watcher (informers + collectors) |
| `scout` | OCIRepository + Flux Kustomization | Scout service with web dashboard |
| `light-catcher` | OCIRepository + Flux Kustomization | Redis Streams consumer triggering WLED light effects |
| `wled-mock` | OCIRepository + Flux Kustomization | WLED mock server with dashboard (for dev/testing) |
| `demo-pitcher` | OCIRepository + Flux Kustomization | Web UI for manually pitching demo messages to Redis Streams |

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
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | no | Bearer auth token for the `/pitch` endpoint (use substituteFrom Secret) |

### Core Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_CORE_CATCHER_VERSION` | `v0.5.0` | no | Container image tag |
| `HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION` | `v0.5.0` | no | OCI kustomize base tag (use `-web` suffix for web mode) |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### K8s Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_K8S_PITCHER_VERSION` | `v0.4.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_K8S_PITCHER_NAMESPACE` | `homerun2-flux` | no | Namespace (can differ from shared namespace) |
| `HOMERUN2_OMNI_PITCHER_AUTH_TOKEN` | `changeme` | no | Bearer auth token (shared with omni-pitcher, from substituteFrom Secret) |
| `HOMERUN2_K8S_PITCHER_TRUST_BUNDLE_CM` | `cluster-trust-bundle` | no | ConfigMap name with CA bundle for TLS trust |
| `HOMERUN2_K8S_PITCHER_PROFILE_CM` | `homerun2-k8s-pitcher-profile` | no | ConfigMap name containing the K8sPitcherProfile YAML |

### Light Catcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_LIGHT_CATCHER_VERSION` | `v0.3.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_LIGHT_CATCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### WLED Mock

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_WLED_MOCK_VERSION` | `v0.3.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_WLED_MOCK_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

### Demo Pitcher

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_DEMO_PITCHER_VERSION` | `v1.4.0` | no | OCI kustomize base + container image tag |
| `HOMERUN2_DEMO_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

The WLED mock provides a dashboard simulating a WLED device. Use it during development/testing instead of a real WLED device. The light-catcher's profile should point its endpoints to `homerun2-wled-mock.NAMESPACE.svc.cluster.local`.

The k8s-pitcher component **deletes** the KCL-generated profile ConfigMap. The calling side must provide its own profile ConfigMap with cluster-specific configuration (pitcher address, collectors, informers). For CRD watching, add the CRD API group to the ClusterRole on the calling side.

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
  HOMERUN2_OMNI_PITCHER_AUTH_TOKEN: "your-auth-token" #pragma: allowlist secret
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
  --age-key env:AGE_PUB \
  --plaintext-file homerun2-flux-secrets.yaml \
  --file-extension yaml \
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
      # K8s Pitcher
      HOMERUN2_K8S_PITCHER_VERSION: v0.4.0
      HOMERUN2_K8S_PITCHER_NAMESPACE: homerun2-flux
      HOMERUN2_K8S_PITCHER_PROFILE_CM: homerun2-k8s-pitcher-profile
      # Light Catcher + WLED Mock
      HOMERUN2_LIGHT_CATCHER_VERSION: v0.3.0
      HOMERUN2_LIGHT_CATCHER_HOSTNAME: light-catcher
      HOMERUN2_WLED_MOCK_VERSION: v0.3.0
      HOMERUN2_WLED_MOCK_HOSTNAME: wled-mock
      # Demo Pitcher
      HOMERUN2_DEMO_PITCHER_VERSION: v1.4.0
      HOMERUN2_DEMO_PITCHER_HOSTNAME: demo-pitcher
      # Redis Stack
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
      # K8s Pitcher
      HOMERUN2_K8S_PITCHER_VERSION: v0.4.0
      HOMERUN2_K8S_PITCHER_NAMESPACE: homerun2-flux
      HOMERUN2_K8S_PITCHER_PROFILE_CM: homerun2-k8s-pitcher-profile
      # Light Catcher + WLED Mock
      HOMERUN2_LIGHT_CATCHER_VERSION: v0.3.0
      HOMERUN2_LIGHT_CATCHER_HOSTNAME: light-catcher
      HOMERUN2_WLED_MOCK_VERSION: v0.3.0
      HOMERUN2_WLED_MOCK_HOSTNAME: wled-mock
      # Demo Pitcher
      HOMERUN2_DEMO_PITCHER_VERSION: v1.4.0
      HOMERUN2_DEMO_PITCHER_HOSTNAME: demo-pitcher
      # Redis Stack
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

**K8s Pitcher profile ConfigMap** (calling side defines this separately):

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: homerun2-k8s-pitcher-profile
  namespace: homerun2-flux
data:
  profile.yaml: |
    apiVersion: homerun2.sthings.io/v1alpha1
    kind: K8sPitcherProfile
    metadata:
      name: movie-scripts
    spec:
      pitcher:
        addr: https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de/pitch
        insecure: false
      auth:
        tokenFrom:
          secretKeyRef:
            name: homerun2-k8s-pitcher-token
            namespace: homerun2-flux
            key: auth-token
      collectors:
        - kind: Node
          interval: 60s
        - kind: Pod
          namespace: "*"
          interval: 30s
        - kind: Event
          namespace: "*"
          interval: 15s
      informers:
        - group: ""
          version: v1
          resource: pods
          namespace: "*"
          events: [add, update, delete]
        - group: apps
          version: v1
          resource: deployments
          namespace: homerun2-flux
          events: [add, update, delete]
```

**Resulting endpoints:**

| Service | URL |
|---------|-----|
| Omni Pitcher | `https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Core Catcher | `https://catcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Light Catcher | `https://light-catcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| WLED Mock | `https://wled-mock.movie-scripts2.sthings-vsphere.labul.sva.de` |
| Demo Pitcher | `https://demo-pitcher.movie-scripts2.sthings-vsphere.labul.sva.de` |
| K8s Pitcher | *(cluster-internal, watches K8s API and pitches to Omni Pitcher)* |
| Redis Stack | `redis-stack.homerun2-flux.svc.cluster.local:6379` (internal) |

## HOW IT WORKS

Uses the Kustomize Components pattern:

1. **Root kustomization.yaml** composes the components (`redis-stack` + `omni-pitcher` + `core-catcher` + `k8s-pitcher` + `scout` + `light-catcher` + `wled-mock` + `demo-pitcher`)
2. **Outer Flux Kustomization** (consumer) reads `./apps/homerun2` from GitRepository, substitutes variables
3. **Redis Stack component** deploys Redis via HelmRelease into the shared namespace
4. **Omni Pitcher component** creates an OCIRepository + inner Flux Kustomization that reconciles the kustomize base from OCI, patches secrets, overrides image tag, and wires Redis connection
5. **Core Catcher component** same pattern as pitcher — patches secrets, sets `CATCHER_MODE=web`, removes KCL-generated HTTPRoute (replaced by component-level HTTPRoute with custom hostname)
6. **K8s Pitcher component** watches the K8s API via informers/collectors and sends events to omni-pitcher. Mounts CA trust bundle for TLS. Profile ConfigMap is defined on the calling side (cluster-specific config)
7. **Light Catcher component** consumes messages from Redis Streams and triggers WLED light effects based on configurable YAML profiles. Exposes an HTMX dashboard via HTTPRoute
8. **WLED Mock component** provides a mock WLED device with dashboard for development/testing. The light-catcher profile endpoints should point to `homerun2-wled-mock.NAMESPACE.svc.cluster.local` when using the mock
9. **Demo Pitcher component** provides a web UI for manually composing and pitching demo messages directly to Redis Streams. Useful for testing and demos without needing curl or the omni-pitcher API

Adding more homerun2 services is done by adding new component folders under `components/`.

## TESTING WITH CURL

Send test events to the omni-pitcher `/pitch` endpoint:

**Minimal event:**

```bash
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Test Message",
    "message": "This is a test message"
  }'
```

**Full event with all fields:**

```bash
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Deployment Notification",
    "message": "Service xyz deployed successfully to production",
    "severity": "success",
    "author": "ci-pipeline",
    "system": "demo-system",
    "tags": "deployment,production,success",
    "assigneeaddress": "ops-team@example.com",
    "assigneename": "Ops Team",
    "artifacts": "docker://registry.example.com/xyz:1.0.0",
    "url": "http://example.com/deployment/xyz"
  }'
```

**Example using the movie-scripts cluster:**

```bash
curl -X POST https://pitcher.movie-scripts2.sthings-vsphere.labul.sva.de/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Infrastructure Alert",
    "message": "CPU usage exceeded 90% on node-3",
    "severity": "warning",
    "author": "monitoring",
    "system": "movie-scripts",
    "tags": "infra,cpu,alert"
  }'
```

**Health check:**

```bash
curl https://pitcher.<DOMAIN>/health
```

**Payload fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | yes | - | Short title of the message |
| `message` | string | yes | - | Message content |
| `severity` | string | no | `info` | `info`, `warning`, `error`, `success` |
| `author` | string | no | `unknown` | Creator of the message |
| `system` | string | no | `homerun2-omni-pitcher` | Originating system |
| `tags` | string | no | - | Comma-separated tags |
| `assigneeaddress` | string | no | - | Assignee email/address |
| `assigneename` | string | no | - | Assignee name |
| `artifacts` | string | no | - | Related artifacts (e.g., container image) |
| `url` | string | no | - | Related URL |

**Response:**

```json
{
  "objectId": "550e8400-e29b-41d4-a716-446655440000-demo-system",
  "streamId": "messages",
  "status": "success",
  "message": "Message successfully enqueued"
}
```

## RELATED DOCUMENTATION

- [homerun2-omni-pitcher](https://stuttgart-things.github.io/homerun2-omni-pitcher/) — API gateway docs
- [homerun2-core-catcher](https://stuttgart-things.github.io/homerun2-core-catcher/) — Consumer/dashboard docs
- [homerun2-demo-pitcher](https://stuttgart-things.github.io/homerun2-demo-pitcher/) — Demo pitcher web UI docs
- [homerun2-light-catcher](https://stuttgart-things.github.io/homerun2-light-catcher/) — WLED light effects consumer docs
