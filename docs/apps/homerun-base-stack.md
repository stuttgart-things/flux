# Homerun Base Stack

Core Homerun platform components: Redis Stack, Generic Pitcher webhook receiver, and Text Catcher.

## Prerequisites

Create a secret with Redis password and Generic Pitcher token:

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun-base-stack
  namespace: flux-system
type: Opaque
stringData:
  REDIS_PASSWORD: "your-secure-password"
  GENERIC_PITCHER_TOKEN: "your-token"
EOF
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
  ref:
    tag: v1.0.0
  url: https://github.com/stuttgart-things/flux.git
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun-base-stack
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: homerun-redis-stack
      namespace: homerun
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: homerun-generic-pitcher
      namespace: homerun
  path: ./apps/homerun-base-stack
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN_NAMESPACE: homerun
      HOMERUN_VERSION: v0.1.2
      REDIS_STACK_ENABLED: "true"
      REDIS_SERVICE_TYPE: ClusterIP
      REDIS_STORAGE_CLASS: nfs4-csi
      GENERIC_PITCHER_ENABLED: "true"
      GENERIC_PITCHER_PATH: generic
      GENERIC_PITCHER_STREAM: homerun
      GENERIC_PITCHER_INDEX: homerun
      HOSTNAME: homerun
      DOMAIN: example.sthings-vsphere.labul.sva.de
      ISSUER_TYPE: ClusterIssuer
      ISSUER_NAME: ca-issuer
      TLS_SECRET_NAME: homerun-generic-pitcher-ingress-tls
      TEXT_CATCHER_ENABLED: "true"
      TEXT_CATCHER_STREAM: homerun
    substituteFrom:
      - kind: Secret
        name: homerun-base-stack
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN_NAMESPACE` | `homerun` | Target namespace |
| `HOMERUN_VERSION` | `v0.1.2` | Chart version |
| `REDIS_STACK_ENABLED` | `true` | Enable Redis Stack |
| `REDIS_SERVICE_TYPE` | `ClusterIP` | Redis service type |
| `REDIS_PASSWORD` | *(required, from secret)* | Redis password |
| `REDIS_STORAGE_ENABLED` | `true` | Enable Redis persistence |
| `REDIS_STORAGE_CLASS` | *(required)* | StorageClass for Redis |
| `REDIS_STORAGE_SIZE` | `8Gi` | Redis PVC size |
| `REDIS_PORT` | `6379` | Redis port |
| `GENERIC_PITCHER_ENABLED` | `true` | Enable Generic Pitcher |
| `GENERIC_PITCHER_PATH` | `generic` | Webhook path |
| `GENERIC_PITCHER_STREAM` | `homerun` | Redis stream name |
| `GENERIC_PITCHER_INDEX` | `homerun` | Redis index name |
| `GENERIC_PITCHER_TOKEN` | *(required, from secret)* | Auth token |
| `HOSTNAME` | *(required)* | Ingress hostname prefix |
| `DOMAIN` | *(required)* | Ingress domain suffix |
| `ISSUER_NAME` | *(required)* | cert-manager issuer name |
| `ISSUER_TYPE` | *(required)* | Issuer kind |
| `TLS_SECRET_NAME` | *(required)* | TLS secret name |
| `TEXT_CATCHER_ENABLED` | `true` | Enable Text Catcher |
| `TEXT_CATCHER_STREAM` | `homerun` | Text Catcher stream name |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things`
- Consists of three sub-releases: `redis-stack.yaml`, `generic-pitcher.yaml`, `text-catcher.yaml`
