# ingress-nginx

NGINX Ingress Controller for Kubernetes.

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
  name: ingress-nginx
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./infra/ingress-nginx
  prune: true
  wait: true
  postBuild:
    substitute:
      INGRESS_NGINX_NAMESPACE: ingress-nginx
      INGRESS_NGINX_CHART_VERSION: "4.12.0"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `INGRESS_NGINX_NAMESPACE` | `ingress-nginx` | Target namespace |
| `INGRESS_NGINX_CHART_VERSION` | `4.12.0` | Helm chart version |

## Notes

- Uses HelmRepository from `https://kubernetes.github.io/ingress-nginx`
- Consider using [Cilium](cilium.md) with Gateway API as a modern alternative
