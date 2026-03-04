# Tekton

Cloud-native CI/CD pipelines.

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
  name: tekton
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton
  prune: true
  wait: true
  postBuild:
    substitute:
      TEKTON_NAMESPACE: tekton-pipelines
      TEKTON_VERSION: "0.76.1"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `TEKTON_NAMESPACE` | `tekton-pipelines` | Target namespace |
| `TEKTON_NAME` | `tekton-pipelines` | Release name |
| `TEKTON_VERSION` | `0.76.1` | Helm chart version |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things/tekton`
- Deploys Tekton Pipelines for running CI/CD TaskRuns and PipelineRuns
