# stuttgart-things/flux/cicd/komoplane

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
    branch: main
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
  name: komoplane
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/komoplane
  prune: true
  wait: true
  postBuild:
    substitute:
      KOMOPLANE_NAMESPACE: komoplane
      KOMOPLANE_VERSION: "0.1.6"
      KOMOPLANE_HOSTNAME: komoplane
      DOMAIN: example.com
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
EOF
```
