# stuttgart-things/flux/homerun-base-stack

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
  REDIS_PASSWORD: "your-secure-password" #pragma: allowlist secret
  GENERIC_PITCHER_TOKEN: "IhrGeheimerToken" #pragma: allowlist secret
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: feature/update-homerun-base #main
EOF
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
      REDIS_STORAGE_CLASS: local-path #longhorn
      GENERIC_PITCHER_ENABLED: "true"
      GENERIC_PITCHER_PATH: generic
      GENERIC_PITCHER_STREAM: homerun
      GENERIC_PITCHER_INDEX: homerun
      HOSTNAME: homerun
      DOMAIN: homerun-int.sthings-vsphere.labul.sva.de
      ISSUER_TYPE: ClusterIssuer
      ISSUER_NAME: ca-issuer
      TLS_SECRET_NAME: homerun-generic-pitcher-ingress-tls
      TEXT_CATCHER_ENABLED: "true"
      TEXT_CATCHER_STREAM: homerun
    substituteFrom:
      - kind: Secret
        name: homerun-base-stack
EOF
```
