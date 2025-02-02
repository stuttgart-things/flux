# stuttgart-things/flux/homerun-iot-stack

## SECRETS MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: homerun-iot-stack
  namespace: flux-system
type: Opaque
stringData:
  REDIS_PASSWORD: "your-secure-password" #pragma: allowlist secret
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

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: wled-config
  namespace: homerun
data:
  config.yaml: |
    ---
    effects:
      error-git:
        systems:
          - gitlab
          - github
        severity:
          - ERROR
        fx: Blurz
        effect_mode: 13
        duration: 3 # seconds
        color: sunset
        segments:
          - 0
        endpoint: localhost:8080

      info:
        systems:
          - flux # * = All systems
        severity:
          - INFO
        fx: DJ Light
        effect_mode: 5
        duration: 3 # seconds
        color: ocean
        segments:
          - 0
        endpoint: localhost:8080

      success:
        systems:
          - ansible
        severity:
          - SUCCESS
        fx: Aurora
        effect_mode: 5
        duration: 3 # seconds
        color: forest
        segments:
          - 0
        endpoint: localhost:8080
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: homerun-iot-stack
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
      name: homerun-light-catcher
      namespace: homerun
  path: ./apps/homerun-iot-stack
  prune: true
  wait: true
  postBuild:
    substitute:
      HOMERUN_NAMESPACE: homerun
      HOMERUN_VERSION: v0.2.0
    substituteFrom:
      - kind: Secret
        name: homerun-iot-stack
EOF
```
