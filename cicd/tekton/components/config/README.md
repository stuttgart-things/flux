# tekton/components/config

TektonConfig CR that tells the Tekton Operator which components to install and how to configure them.

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tekton-config
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton/components/config
  prune: true
  wait: true
  dependsOn:
    - name: tekton-operator
  postBuild:
    substitute:
      TEKTON_TARGET_NAMESPACE: tekton-pipelines
      TEKTON_PROFILE: all
      TEKTON_ENABLE_API_FIELDS: beta
      TEKTON_PRUNER_DISABLED: "false"
      TEKTON_PRUNER_SCHEDULE: "0 8 * * *"
      TEKTON_PRUNER_KEEP: "100"
      TEKTON_PRUNER_KEEP_SINCE: "1440"
```

## Resources

| Resource | Kind | Purpose |
|---|---|---|
| `config` | TektonConfig | Controls operator behavior and installed components |

## Dependencies

- **tekton-operator** — Operator CRDs and Deployments must be running before applying TektonConfig
