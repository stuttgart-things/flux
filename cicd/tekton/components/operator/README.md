# tekton/components/operator

Tekton Operator v0.81.2 — installs the operator that manages Tekton Pipelines, Triggers, Dashboard, and Chains.

Vendored from: `https://infra.tekton.dev/tekton-releases/operator/previous/v0.81.2/release.yaml`
(the Kubernetes `release.yaml`), split by `hack/vendor-tekton-operator.py v0.81.2` --
do not edit these files by hand, re-run the script.

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
| `crd-<plural>.yaml` | 13 CRDs, one per file (TektonConfig, TektonPipeline, TektonTrigger, etc.) -- a single file would exceed pre-commit's 500 KB limit |
| `rbac.yaml` | ServiceAccount, Roles, ClusterRoles, Bindings (13 resources) |
| `config.yaml` | ConfigMaps + webhook Secret (7 resources) |
| `deployment.yaml` | Operator + Webhook Deployments and Services (4 resources) |

## Dependencies

None — this is the base component.
