# stuttgart-things/flux/infra/dapr

Installs the [Dapr](https://dapr.io) runtime on the cluster via the official
[Dapr Helm chart](https://artifacthub.io/packages/helm/dapr/dapr). Provides the
workflow engine, state store abstraction, and sidecar injector used by the
workflow apps in this repository (e.g. `backstage-template-execution`).

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
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
EOF
```

</details>

## KUSTOMIZATION

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: dapr
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/dapr
  prune: true
  wait: true
  postBuild:
    substitute:
      DAPR_VERSION: 1.17.4
      DAPR_NAMESPACE: dapr-system
      DAPR_HA_ENABLED: "false"
EOF
```

## VARIABLES

| Variable | Default | Description |
|----------|---------|-------------|
| `DAPR_VERSION` | `1.17.4` | Dapr helm chart version (matches runtime version) |
| `DAPR_NAMESPACE` | `dapr-system` | Namespace for Dapr control-plane components |
| `DAPR_HA_ENABLED` | `false` | High-availability mode for control-plane (3 replicas per component) |

Per-app Dapr components (state stores, pubsub, etc.) are not installed here —
they live with the app that uses them (e.g. `apps/backstage-template-execution/`)
so each app can bring its own Redis / component configuration.
