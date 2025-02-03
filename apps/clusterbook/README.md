# stuttgart-things/flux/clusterbook

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: feature/update-homerun-base #main
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: clusterbook
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2
      kind: HelmRelease
      name: clusterbook
      namespace: clusterbook
  path: ./apps/clusterbook
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERBOOK_NAMESPACE: homerun
      CLUSTERBOOK_VERSION: v1.3.1-chart
      HOSTNAME: homerun
      DOMAIN: homerun-int.sthings-vsphere.labul.sva.de
      ISSUER_TYPE: ClusterIssuer
      ISSUER_NAME: ca-issuer
      TLS_SECRET_NAME: homerun-generic-pitcher-ingress-tls
EOF
```
