# crossplane/components/functions

Deploys Crossplane Functions via the `sthings-cluster` Helm chart. Installs function-auto-ready, function-go-templating, function-kcl, and function-patch-and-transform.

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-functions
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/components/functions
  prune: true
  wait: true
  dependsOn:
    - name: crossplane-install
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: crossplane-functions
      namespace: crossplane-system
```

## Resources

| Resource | Kind | Purpose |
|---|---|---|
| `crossplane-functions` | HelmRelease | Deploys Crossplane Functions as custom resources |

## Functions installed

| Name | Version | Purpose |
|---|---|---|
| `function-auto-ready` | v0.6.0 | Automatically marks resources as ready |
| `function-go-templating` | v0.11.3 | Go template processing |
| `function-kcl` | v0.12.0 | KCL language support |
| `function-patch-and-transform` | v0.9.3 | Resource patching and transformation |

## Dependencies

- **crossplane-install** - Crossplane core must be running before functions can be deployed (HelmRelease `dependsOn: crossplane-deployment`)
