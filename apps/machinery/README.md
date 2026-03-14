# stuttgart-things/flux/machinery

Flux app for machinery — gRPC + HTMX service for watching Crossplane-managed Kubernetes custom resources. Deploys via OCI kustomize base (built from KCL manifests) with Gateway API HTTPRoute.

## Kustomization Example

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: machinery
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/machinery
  prune: true
  wait: true
  postBuild:
    substitute:
      MACHINERY_NAMESPACE: machinery
      MACHINERY_VERSION: latest
      MACHINERY_HOSTNAME: machinery
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `MACHINERY_NAMESPACE` | `machinery` | Target namespace |
| `MACHINERY_VERSION` | `latest` | Image + kustomize OCI tag |
| `MACHINERY_HOSTNAME` | `machinery` | HTTPRoute hostname prefix |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `<hostname>.<domain>:50051` | gRPC API |
