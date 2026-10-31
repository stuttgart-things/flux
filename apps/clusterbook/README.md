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
      CLUSTERBOOK_VERSION: v1.25.7
      CLUSTERBOOK_HOSTNAME: clusterbook
      GATEWAY_NAME: movie-scripts2-gateway
      GATEWAY_NAMESPACE: default
      DOMAIN: movie-scripts2.sthings-vsphere.labul.sva.de
      PDNS_ENABLED: "true"
      PDNS_URL: https://pdns.sthings-vsphere.labul.sva.de
      PDNS_ZONE: sthings.io
      DDWRT_ENABLED: "true"
      DDWRT_HOST: 192.168.1.1
      DDWRT_USER: root
      DDWRT_ZONE: sthings.lab
    substituteFrom:
      - kind: Secret
        name: clusterbook-pdns-vars
      - kind: Secret
        name: clusterbook-ddwrt-vars
EOF
```

## Substitution Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTERBOOK_NAMESPACE` | `clusterbook` | Target namespace |
| `CLUSTERBOOK_VERSION` | `v1.25.7` | Image + kustomize OCI tag |
| `CLUSTERBOOK_HOSTNAME` | `clusterbook` | HTTPRoute hostname prefix |
| `GATEWAY_NAME` | *(required)* | Gateway API gateway name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `DOMAIN` | *(required)* | Domain suffix for HTTPRoute hostname |
| `PDNS_ENABLED` | `false` | Enable PowerDNS integration |
| `PDNS_URL` | *(empty)* | PowerDNS API base URL |
| `PDNS_ZONE` | *(empty)* | PowerDNS DNS zone |
| `PDNS_TOKEN` | *(required if PDNS enabled)* | PowerDNS API key (via `substituteFrom` Secret) |
| `DDWRT_ENABLED` | `false` | Enable DD-WRT integration |
| `DDWRT_HOST` | *(empty)* | DD-WRT router host/IP |
| `DDWRT_USER` | *(empty)* | DD-WRT login user |
| `DDWRT_ZONE` | *(empty)* | DD-WRT DNS zone |
| `DDWRT_PASSWORD` | *(required if DD-WRT enabled)* | DD-WRT login password (via `substituteFrom` Secret) |
| `CLUSTERBOOK_ROUTE` | `all` | bundle component only: what the own hostname serves, `all` or `api` (see below) |
| `CLUSTERBOOK_BASE_PATH` | *(empty; the bundle component passes `/`)*: UI at the root | URL prefix of the web UI behind [sthings-portal](../sthings-portal/README.md), e.g. `/clusterbook` (clusterbook v1.29.0+, stuttgart-things/clusterbook#220) |

## Behind sthings-portal

The portal forwards `/<key>/...` unchanged to the service, so clusterbook has
to answer under the same prefix: the portal entry
`clusterbook=http://clusterbook-http.clusterbook.svc.cluster.local:8080` needs
`CLUSTERBOOK_BASE_PATH: /clusterbook`. Use the Service `clusterbook-http`
(port 8080, HTTP); `clusterbook` (port 80) is gRPC.

With a prefix set:

- the UI is under the prefix **on the own hostname too**:
  `https://clusterbook.<domain>/clusterbook/` (the root `/` answers 404);
- `/health` and the REST API `/api/v1/...` stay at the root -- the Crossplane
  provider, `dagger -m clusterbook` and other clients need no change;
- `BASE_PATH` is a container env entry, so changing it rolls the pod.

### The own hostname: `CLUSTERBOOK_ROUTE`

The bundle component picks one of `./components/route-*` for the HTTPRoute
on `clusterbook.<domain>`:

| `CLUSTERBOOK_ROUTE` | the own hostname serves |
|---|---|
| `all` (default) | everything: UI, REST API, `/health` |
| `api` | `/api/...` and `/health` only -- the UI is then reachable only through sthings-portal (behind its login); everything else answers 404 |

Every client (Crossplane provider-clusterbook, terraform-provider-clusterbook,
clusterbook-operator, clusterscope, `dagger -m clusterbook`, the Backstage VM
template) calls `/api/v1/...` only. With `api`, set `CLUSTERBOOK_BASE_PATH`
and the portal entry too, or the UI is nowhere.

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
