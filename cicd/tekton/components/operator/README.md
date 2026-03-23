# tekton/components/operator

Tekton Operator v0.79.0 — installs the operator that manages Tekton Pipelines, Triggers, Dashboard, and Chains.

Vendored from: `https://infra.tekton.dev/tekton-releases/operator/previous/v0.79.0/release.yaml`

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tekton-operator
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton/components/operator
  prune: true
  wait: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator
      namespace: tekton-operator
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator-webhook
      namespace: tekton-operator
```

## Resources

| File | Contents |
|---|---|
| `namespace.yaml` | `tekton-operator` Namespace |
| `crds.yaml` | 13 CRDs (TektonConfig, TektonPipeline, TektonTrigger, etc.) |
| `rbac.yaml` | ServiceAccount, Roles, ClusterRoles, Bindings (13 resources) |
| `config.yaml` | ConfigMaps + webhook Secret (7 resources) |
| `deployment.yaml` | Operator + Webhook Deployments and Services (4 resources) |

## Dependencies

None — this is the base component.
