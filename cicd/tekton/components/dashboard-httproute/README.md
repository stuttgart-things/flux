# tekton/components/dashboard-httproute

Exposes the Tekton Dashboard via Gateway API HTTPRoute.

## Flux Kustomization

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tekton-dashboard-httproute
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton/components/dashboard-httproute
  prune: true
  wait: true
  dependsOn:
    - name: tekton
  postBuild:
    substitute:
      TEKTON_DASHBOARD_NAMESPACE: tekton-pipelines
      TEKTON_DASHBOARD_HOSTNAME: tekton
      TEKTON_DASHBOARD_DOMAIN: example.sthings-vsphere.labul.sva.de
      GATEWAY_NAME: my-gateway
      GATEWAY_NAMESPACE: default
```

## Resources

| Resource | Kind | Purpose |
|---|---|---|
| `tekton-dashboard` | HTTPRoute | Gateway API route to Tekton Dashboard (port 9097) |

## Dependencies

- **tekton** — Tekton Operator and Dashboard must be running
