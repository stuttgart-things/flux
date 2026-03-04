# Crossplane

Universal control plane with Terraform, Helm, and Kubernetes providers.

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
  name: crossplane
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane
  prune: true
  wait: true
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_VERSION: "2.1.3"
      CROSSPLANE_HELM_PROVIDER_VERSION: v1.0.6
      CROSSPLANE_K8S_PROVIDER_VERSION: v1.2.0
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: crossplane-deployment
      namespace: crossplane-system
    - apiVersion: apps/v1
      kind: Deployment
      name: crossplane
      namespace: crossplane-system
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CROSSPLANE_NAMESPACE` | `crossplane-system` | Target namespace |
| `CROSSPLANE_VERSION` | `2.1.3` | Crossplane Helm chart version |
| `CROSSPLANE_HELM_PROVIDER_VERSION` | `v1.0.6` | Crossplane Helm provider version |
| `CROSSPLANE_K8S_PROVIDER_VERSION` | `v1.2.0` | Crossplane Kubernetes provider version |

## Notes

- Uses HelmRepository from `https://charts.crossplane.io/stable`
- Includes `functions.yaml` for Crossplane provider configuration (Helm and Kubernetes providers)
- Terraform provider configuration is also available but requires additional variables for S3 backend and provider image
