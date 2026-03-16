# stuttgart-things/flux/flux-web

## Deployment

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: flux-web
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/flux-web
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_WEB_NAMESPACE: flux-system
      FLUX_WEB_VERSION: "0.43.0"
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: flux-web
      DOMAIN: example.sthings-vsphere.labul.sva.de
EOF
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `FLUX_WEB_NAMESPACE` | `flux-system` | Target namespace |
| `FLUX_WEB_VERSION` | `0.43.0` | Helm chart version (flux-operator) |
| `GATEWAY_NAME` | *(required)* | Gateway resource name for HTTPRoute |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway resource |
| `HOSTNAME` | *(required)* | Hostname prefix for HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute |

## Components

- **release.yaml** - HelmRelease deploying the Flux Operator web UI in server-only mode from `oci://ghcr.io/controlplaneio-fluxcd/charts`
- **networkpolicy.yaml** - NetworkPolicy allowing ingress on port 9080 for the flux-web pod
- **requirements.yaml** - HelmRepository pointing to the flux-operator OCI registry
