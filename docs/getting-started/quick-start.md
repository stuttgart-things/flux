# Quick Start

Deploy your first component from this repository in three steps.

## 1. Bootstrap Flux

If Flux is not already running on your cluster, see [Bootstrap Overview](../bootstrap/overview.md). The quickest method:

```bash
export GITHUB_TOKEN=<your-token>

flux bootstrap github \
  --owner=stuttgart-things \
  --repository=stuttgart-things \
  --path=clusters/my-cluster
```

## 2. Add the GitRepository

Point Flux at this repository:

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

## 3. Deploy a Component

Create a `Kustomization` referencing the component path. Example deploying Tekton:

```bash
kubectl apply -f - <<EOF
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
      TEKTON_PIPELINE_NAMESPACE: tektoncd
      TEKTON_VERSION: v0.60.4
EOF
```

## Via Git (Recommended for Production)

Instead of `kubectl apply`, commit the resources to your cluster's Git path:

```yaml
# clusters/my-cluster/app-repo.yaml
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
```

```yaml
# clusters/my-cluster/apps.yaml
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
      TEKTON_PIPELINE_NAMESPACE: tektoncd
      TEKTON_VERSION: v0.60.4
```

## Next Steps

- Browse [Apps](../apps/index.md), [Infrastructure](../infra/index.md), and [CI/CD](../cicd/index.md) for available components
- Check each component's doc page for its variables and configuration
- See [Variable Substitution](../development/conventions.md#variable-substitution) for how variables work
