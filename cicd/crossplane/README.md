
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

## The Configurations need a SECOND Kustomization

`./cicd/crossplane` installs the controller and the Functions. The
`Configuration` CRs live at `./cicd/crossplane/configs` and must be wired
separately, with `dependsOn` on the one above:

```yaml
spec:
  dependsOn:
    - name: crossplane
  path: ./cicd/crossplane/configs
  wait: true
```

`Configuration` is a CRD the chart installs, so applying the CRs in the same
pass dry-runs them against an API that does not know the kind yet. Flux aborts
the whole apply on that -- the HelmRelease included -- so crossplane is never
installed, the CRD never appears, and every retry fails identically. The
deadlock is silent: the namespace exists and nothing else does.

The Functions do NOT need this, because `components/functions` ships them as
`customresources` inside a HelmRelease -- nothing types them at apply time.
