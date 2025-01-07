# stuttgart-things/flux/infra/ingress-nginx

## REQUIREMENTS

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-infra
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    tag: v1.0.0
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
  name: ingress-nginx
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/ingress-nginx
  prune: true
  wait: true
  postBuild:
    substitute:
      INGRESS_NGINX_NAMESPACE: ingress-nginx
      INGRESS_NGINX_CHART_VERSION: 4.12.0
EOF
```
