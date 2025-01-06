# stuttgart-things/flux/infra/metallb

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

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
    branch: feature/add-cert-manager
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

## KUSTOMIZATION

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: metallb
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/metallb
  prune: true
  wait: true
  postBuild:
    substitute:
      METALLB_NAMESPACE: ingress-nginx
      METALLB_CHART_VERSION: 4.12.0
      INSTALL_CRDS: "true"
      METALLB_IP_RANGE: 10.31.103.13-10.31.103.14 #EXAMPLE
      METALLB_IP_POOL: ingress

EOF
```
