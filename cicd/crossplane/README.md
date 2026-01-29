# stuttgart-things/flux/crossplane

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: main
EOF
```

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
  path: ./cicd/crossplane
  prune: true
  wait: true
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_TERRAFORM_CONFIG_NAME: terraform-runtime-config
      CROSSPLANE_TERRAFORM_POLL: 30s
      CROSSPLANE_TERRAFORM_PROVIDER_IMAGE: ghcr.io/stuttgart-things/sthings-cptf:1.14.3
      CROSSPLANE_TERRAFORM_PROVIDER_VERSION: v1.0.5
      CROSSPLANE_TERRAFORM_RECONCILE_RATE: 10
      CROSSPLANE_TERRAFORM_S3_SECRET_NAME: terraform-s3
      CROSSPLANE_HELM_PROVIDER_VERSION: v1.0.6
      CROSSPLANE_K8S_PROVIDER_VERSION: v1.2.0
      CROSSPLANE_VERSION: 2.1.3
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: crossplane-deployment
      namespace: crossplane-system
    - apiVersion: apps/v1
      kind: Deployment
      name: crossplane
      namespace: crossplane-system
EOF
```
