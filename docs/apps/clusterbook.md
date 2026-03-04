# Clusterbook

Network and cluster inventory management.

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
  name: clusterbook
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
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
      CLUSTERBOOK_NAMESPACE: clusterbook
      CLUSTERBOOK_VERSION: v1.3.1-chart
      HOSTNAME: clusterbook
      DOMAIN: example.sthings-vsphere.labul.sva.de
      ISSUER_TYPE: ClusterIssuer
      ISSUER_NAME: cluster-issuer-approle
      TLS_SECRET_NAME: clusterbook-ingress-tls
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERBOOK_NAMESPACE` | `clusterbook` | Target namespace |
| `CLUSTERBOOK_VERSION` | `v1.3.1-chart` | Helm chart version |
| `HOSTNAME` | *(required)* | Ingress hostname prefix |
| `DOMAIN` | *(required)* | Ingress domain suffix |
| `ISSUER_NAME` | *(required)* | cert-manager issuer name |
| `ISSUER_TYPE` | *(required)* | Issuer kind (ClusterIssuer/Issuer) |
| `TLS_SECRET_NAME` | *(required)* | TLS secret name for Ingress |

## Notes

- Uses OCI HelmRepository from `oci://ghcr.io/stuttgart-things/clusterbook`
- After deployment, create `NetworkConfig` CRs to register IP ranges and cluster assignments
