# stuttgart-things/flux/clusterbook

Flux app for clusterbook — GitOps-based IP address management for Kubernetes clusters. Deploys via OCI kustomize base (built from KCL manifests) with Gateway API HTTPRoute.

## Kustomization Example

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
  path: ./apps/clusterbook
  prune: true
  wait: true
  postBuild:
    substitute:
      CLUSTERBOOK_NAMESPACE: clusterbook
      CLUSTERBOOK_VERSION: v1.11.0
      CLUSTERBOOK_HOSTNAME: clusterbook
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
      PDNS_ENABLED: "true"
      PDNS_URL: https://pdns.sthings-vsphere.labul.sva.de
      PDNS_ZONE: sthings.io
    substituteFrom:
      - kind: Secret
        name: clusterbook-pdns-vars
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERBOOK_NAMESPACE` | `clusterbook` | Target namespace |
| `CLUSTERBOOK_VERSION` | `v1.11.0` | Image + kustomize OCI tag |
| `CLUSTERBOOK_HOSTNAME` | `clusterbook` | HTTPRoute hostname prefix |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |
| `PDNS_ENABLED` | `false` | Enable PowerDNS integration |
| `PDNS_URL` | *(empty)* | PowerDNS API base URL |
| `PDNS_ZONE` | *(empty)* | PowerDNS DNS zone |
| `PDNS_TOKEN` | *(required if PDNS enabled)* | PowerDNS API key (via `substituteFrom` Secret) |

## NetworkConfig CR

The NetworkConfig CR is **environment-specific data** and should be placed in the cluster config folder (e.g., `clusters/<env>/clusterbook-networkconfig.yaml`), not in this generic Flux app. Use these annotations so Flux seeds it once but never overwrites runtime changes:

```yaml
annotations:
  kustomize.toolkit.fluxcd.io/prune: disabled
  kustomize.toolkit.fluxcd.io/reconcile: disabled
```

## Example NetworkConfig CR

```bash
kubectl apply -f - <<EOF
---
apiVersion: github.stuttgart-things.com/v1
kind: NetworkConfig
metadata:
  name: networks-labul
  namespace: clusterbook
spec:
  networks:
    10.31.101:
    - 5:ASSIGNED:rancher-mgmt
    - "6"
    - "7"
    - 8:ASSIGNED:fluxdev-3
    - 9:ASSIGNED:fluxdev-3
    10.31.103:
    - "3"
    - 4:ASSIGNED:sandiego
    - 5:ASSIGNED:skyami
    - "6"
    - 7:ASSIGNED:martino
    - "8"
    - 9:PENDING:cicd
    - "10"
EOF
```

## Endpoints

| Endpoint | Description |
|---|---|
| `https://<hostname>.<domain>/` | HTMX dashboard |
| `https://<hostname>.<domain>/api/v1/networks` | REST API — list networks |
| `https://<hostname>.<domain>/api/v1/networks/{key}/ips` | REST API — list IPs in network |
| `<hostname>.<domain>:50051` | gRPC API |
