# stuttgart-things/flux/redis-stack

## SECRETS MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: redis-stack
  namespace: flux-system
type: Opaque
stringData:
  REDIS_STACK_PASSWORD: "your-secure-password" #pragma: allowlist secret
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

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: redis-stack
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/redis-stack
  prune: true
  wait: true
  postBuild:
    substitute:
      REDIS_STACK_NAMESPACE: redis-stack
      REDIS_STACK_VERSION: "17.1.4"
      REDIS_STACK_SERVICE_TYPE: ClusterIP
      REDIS_STACK_PERSISTENCE_ENABLED: "true"
      REDIS_STACK_STORAGE_CLASS: nfs4-csi
      REDIS_STACK_STORAGE_SIZE: 8Gi
      REDIS_STACK_IMAGE_REGISTRY: ghcr.io
      REDIS_STACK_IMAGE_REPOSITORY: stuttgart-things/redis-stack-server
      REDIS_STACK_IMAGE_VERSION: 7.2.0-v18
      REDIS_STACK_SENTINEL_REGISTRY: ghcr.io
      REDIS_STACK_SENTINEL_REPOSITORY: stuttgart-things/redis-sentinel
      REDIS_STACK_SENTINEL_VERSION: 7.4.2-debian-12-r9
    substituteFrom:
      - kind: Secret
        name: redis-stack
EOF
```
