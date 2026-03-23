# crossplane/components/install

Installs the Crossplane core: namespace, Helm repositories, and the `crossplane-deployment` HelmRelease with providers (Helm, Kubernetes, OpenTofu).

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-install
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/components/install
  prune: true
  wait: true
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_VERSION: "2.2.0"
      CROSSPLANE_HELM_PROVIDER_VERSION: v1.2.0
      CROSSPLANE_K8S_PROVIDER_VERSION: v1.2.1
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

## Resources

| Resource | Kind | Purpose |
|---|---|---|
| `crossplane-system` | Namespace | Target namespace |
| `crossplane-stable` | HelmRepository | Official Crossplane charts |
| `stuttgart-things` | HelmRepository (OCI) | Custom stuttgart-things packages |
| `crossplane-deployment` | HelmRelease | Crossplane core + providers |

## Dependencies

None - this is the base component.
