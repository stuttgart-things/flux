# stuttgart-things/flux/homerun2

Homerun2 application stack using Kustomize Components pattern. Deploys Redis Stack + homerun2 microservices into a shared namespace.

## Components

| Component | Type | Description |
|-----------|------|-------------|
| `redis-stack` | HelmRelease | Redis Stack with Sentinel (integral dependency) |
| `omni-pitcher` | OCIRepository + Flux Kustomization | HTTP microservice for Redis Stream ingestion |

## SUBSTITUTION VARIABLES

### Global

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_NAMESPACE` | `homerun2` | no | Shared namespace for all components |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |

### Redis Stack

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HOMERUN2_REDIS_PASSWORD` | - | yes | Redis password (use substituteFrom Secret) |
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
| `HOMERUN2_OMNI_PITCHER_VERSION` | `v1.2.0` | no | OCI tag + container image tag |
| `HOMERUN2_OMNI_PITCHER_HOSTNAME` | - | yes | HTTPRoute hostname prefix |

## SECRETS MANIFEST (SOPS ENCRYPTED)

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun2-secrets
  namespace: flux-system
type: Opaque
stringData:
  HOMERUN2_REDIS_PASSWORD: "your-secure-password" #pragma: allowlist secret
```

Encrypt with SOPS:

```bash
sops --encrypt \
  --age <AGE_PUBLIC_KEY> \
  --encrypted-regex '^(data|stringData)$' \
  --input-type yaml --output-type yaml \
  homerun2-secrets.yaml > homerun2-secrets.enc.yaml \
  && mv homerun2-secrets.enc.yaml homerun2-secrets.yaml
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

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun2
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
      HOMERUN2_NAMESPACE: homerun2
      HOMERUN2_OMNI_PITCHER_VERSION: v1.2.0
      HOMERUN2_OMNI_PITCHER_HOSTNAME: homerun2-omni-pitcher
      HOMERUN2_REDIS_VERSION: "17.1.4"
      HOMERUN2_REDIS_STORAGE_CLASS: nfs4-csi
      HOMERUN2_REDIS_STORAGE_SIZE: 8Gi
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: my-cluster.sthings-vsphere.labul.sva.de
    substituteFrom:
      - kind: Secret
        name: homerun2-secrets
EOF
```

## HOW IT WORKS

Uses the Kustomize Components pattern (like `infra/cilium`):

1. **Root kustomization.yaml** composes the components (`redis-stack` + `omni-pitcher`)
2. **Outer Flux Kustomization** (consumer) reads `./apps/homerun2` from GitRepository, substitutes variables
3. **Redis Stack component** deploys Redis via HelmRelease into the shared namespace
4. **Omni Pitcher component** creates an OCIRepository + inner Flux Kustomization that reconciles the kustomize base from OCI, patches the Ingress→HTTPRoute, overrides image tag, and wires Redis connection

Adding more homerun2 services (e.g., catchers) is done by adding new component folders under `components/`.
