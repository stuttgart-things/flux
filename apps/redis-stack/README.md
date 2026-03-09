# stuttgart-things/flux/redis-stack

## SECRETS MANIFEST (SOPS ENCRYPTED)

Create a plaintext secret file (e.g., `homerun2-secrets.yaml`):

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun2-secrets
  namespace: flux-system
type: Opaque
stringData:
  REDIS_STACK_PASSWORD: "your-secure-password" #pragma: allowlist secret
```

Encrypt with SOPS using age (via local sops):

```bash
sops --encrypt \
  --age <AGE_PUBLIC_KEY> \
  --encrypted-regex '^(data|stringData)$' \
  --input-type yaml --output-type yaml \
  homerun2-secrets.yaml > homerun2-secrets.enc.yaml \
  && mv homerun2-secrets.enc.yaml homerun2-secrets.yaml
```

Or encrypt via Dagger:

```bash
# encrypt
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 encrypt \
  --age-key env:AGE_PUB \
  --plaintext-file homerun2-secrets.yaml \
  --file-extension yaml \
  export --path=homerun2-secrets.yaml

# decrypt (for verification)
dagger call -m github.com/stuttgart-things/dagger/sops@v0.82.1 decrypt \
  --age-key env:SOPS_AGE_KEY \
  --encrypted-file homerun2-secrets.yaml \
  export --path=/tmp/homerun2-secrets.decrypted.yaml
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
