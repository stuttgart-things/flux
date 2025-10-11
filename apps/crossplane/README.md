# stuttgart-things/flux/crossplane


```bash
kubectl apply -f - <<EOF
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
  path: ./apps/crossplane
  prune: true
  wait: true
  postBuild:
    substitute:
      CROSSPLANE_VERSION: 1.20.0
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_HELM_PROVIDER_VERSION: "v0.21.0"
      CROSSPLANE_K8S_PROVIDER_VERSION: "v0.18.0"
      CROSSPLANE_TERRAFORM_PROVIDER_VERSION: "v0.21.0"
      CROSSPLANE_TERRAFORM_PROVIDER_IMAGE: "ghcr.io/stuttgart-things/sthings-cptf:1.12.0"
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2beta1
      kind: HelmRelease
      name: crossplane-deployment
      namespace: crossplane-system
    - apiVersion: apps/v1
      kind: Deployment
      name: crossplane
      namespace: crossplane-system
EOF
```