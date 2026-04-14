# stuttgart-things/flux/cicd/kro

[kro](https://kro.run) — the Kube Resource Orchestrator — installed via
its upstream Helm chart (`oci://registry.k8s.io/kro/charts/kro`) so you
can ship `ResourceGraphDefinition`s alongside the apps that consume them.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KRO_NAMESPACE` | `kro-system` | Namespace the operator runs in |
| `KRO_VERSION` | `0.9.1` | Helm chart version |

## Wiring into a cluster

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: kro
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./cicd/kro
  prune: true
  wait: true
  postBuild:
    substitute:
      KRO_NAMESPACE: kro-system
      KRO_VERSION: "0.9.1"
```
