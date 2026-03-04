# Homerun IoT Stack

IoT components for the Homerun platform, including the Light Catcher WLED controller.

## Prerequisites

Create a secret with Redis password:

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
  REDIS_PASSWORD: "your-secure-password"
EOF
```

Optionally create a `wled-config` ConfigMap in the Homerun namespace with effect mappings for different event types and systems.

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
  name: homerun-iot-stack
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
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `HOMERUN_NAMESPACE` | `homerun` | Target namespace |
| `HOMERUN_VERSION` | `v0.2.0` | Chart version |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | *(required, from secret)* | Redis password |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things`
- Deploys the `light-catcher` component for WLED LED strip control based on CI/CD events
- Requires the [Homerun Base Stack](homerun-base-stack.md) to be deployed first for Redis
