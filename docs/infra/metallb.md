# MetalLB

Bare-metal load balancer with L2 advertisement and IP pool configuration.

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
      METALLB_NAMESPACE: metallb-system
      METALLB_CHART_VERSION: "6.4.2"
      METALLB_INSTALL_CRDS: "true"
      METALLB_IP_RANGE: "10.31.103.13-10.31.103.14"
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `METALLB_NAMESPACE` | `metallb-system` | Target namespace |
| `METALLB_CHART_VERSION` | `6.4.2` | Helm chart version |
| `METALLB_INSTALL_CRDS` | `true` | Install CRDs |
| `METALLB_IP_RANGE` | *(required)* | IP address range for the pool (e.g., `10.0.0.10-10.0.0.20`) |

## Notes

- Uses Bitnami chart from `oci://registry-1.docker.io/bitnamicharts`
- Includes `post-release.yaml` that creates an `IPAddressPool` and `L2Advertisement` via the `sthings-cluster` helper chart
- The `metallb-configuration` HelmRelease depends on `metallb` (waits for CRDs)
- Consider using [Cilium](cilium.md) with L2 announcements as an alternative
