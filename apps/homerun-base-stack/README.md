# FLUX/HOMERUN-BASE-STACK

## SECRETS MANIFEST

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
EOT
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: main
EOT
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
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
    name: stuttgart-things-flux
  path: ./apps/homerun-base-stack
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN_NAMESPACE: homerun
      HOMERUN_VERSION: v0.2.1
      REDIS_SERVICE_TYPE: ClusterIP
      REDIS_STORAGE_CLASS: longhorn
    substituteFrom:
      - kind: Secret
        name: homerun-base-stack
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2beta1
      kind: HelmRelease
      name: crossplane-deployment
      namespace: crossplane-system
EOT
```