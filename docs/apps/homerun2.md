# Homerun2

Homerun2 application stack using the Kustomize Components pattern. Deploys Redis Stack + omni-pitcher + core-catcher microservices into a shared namespace.

## Prerequisites

Create a SOPS-encrypted secret with Redis credentials:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun2-flux-secrets
  namespace: flux-system
type: Opaque
stringData:
  HOMERUN2_REDIS_PASSWORD: "your-secure-password" # pragma: allowlist secret
  HOMERUN2_REDIS_PASSWORD_B64: "<base64-encoded-password>"
EOF
```

Generate the base64 value:

```bash
echo -n 'your-secure-password' | base64
```

## Deployment

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

## Variables

### Global

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_NAMESPACE` | `homerun2` | Shared namespace for all components |
| `GATEWAY_NAME` | *(required)* | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | Gateway parentRef namespace |
| `DOMAIN` | *(required)* | HTTPRoute domain suffix |
| `FLUX_SOURCE_API_VERSION` | `v1` | OCIRepository API version (`v1` or `v1beta2`) |

### Redis Stack

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_REDIS_PASSWORD` | *(required, from secret)* | Redis password |
| `HOMERUN2_REDIS_PASSWORD_B64` | *(required, from secret)* | Base64-encoded Redis password |
| `HOMERUN2_REDIS_VERSION` | `17.1.4` | Helm chart version |
| `HOMERUN2_REDIS_SERVICE_TYPE` | `ClusterIP` | Redis service type |
| `HOMERUN2_REDIS_PERSISTENCE_ENABLED` | `true` | Enable persistence |
| `HOMERUN2_REDIS_STORAGE_CLASS` | `standard` | Storage class |
| `HOMERUN2_REDIS_STORAGE_SIZE` | `8Gi` | PVC size |

### Omni Pitcher

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_OMNI_PITCHER_VERSION` | `v1.2.0` | OCI kustomize base + container image tag |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | *(required)* | HTTPRoute hostname prefix |

### Core Catcher

| Variable | Default | Description |
|---|---|---|
| `HOMERUN2_CORE_CATCHER_VERSION` | `v0.5.0` | Container image tag |
| `HOMERUN2_CORE_CATCHER_KUSTOMIZE_VERSION` | `v0.5.0` | OCI kustomize base tag (use `-web` suffix for web mode) |
| `HOMERUN2_CORE_CATCHER_HOSTNAME` | *(required)* | HTTPRoute hostname prefix |

## Testing

Send test events to the omni-pitcher `/pitch` endpoint:

```bash
# minimal event
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Test Message",
    "message": "This is a test message"
  }'

# full event
curl -X POST https://pitcher.<DOMAIN>/pitch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUTH_TOKEN>" \
  -d '{
    "title": "Deployment Notification",
    "message": "Service xyz deployed successfully to production",
    "severity": "success",
    "author": "ci-pipeline",
    "system": "demo-system",
    "tags": "deployment,production,success"
  }'

# health check
curl https://pitcher.<DOMAIN>/health
```

## Notes

- Uses the Kustomize Components pattern (`redis-stack` + `omni-pitcher` + `core-catcher`)
- Each component is composed via the root `kustomization.yaml`
- Omni Pitcher and Core Catcher use OCIRepository + inner Flux Kustomization
- Gateway API HTTPRoutes are used for external access (no Ingress)
- See [homerun2-omni-pitcher docs](https://stuttgart-things.github.io/homerun2-omni-pitcher/) and [homerun2-core-catcher docs](https://stuttgart-things.github.io/homerun2-core-catcher/)
