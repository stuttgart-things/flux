# stuttgart-things/flux/rancher

Deploys [Rancher](https://artifacthub.io/packages/helm/rancher-stable/rancher) via the
`rancher-stable` Helm repo.

- TLS is terminated at the Gateway API `Gateway`; the chart runs with `ingress.enabled: false`
  and `tls: external`, and traffic is routed via a `HTTPRoute` (port `80`).
- A private/internal CA is trusted via `privateCA: true` and the `tls-ca` secret
  (`cacerts.pem`). That secret is distributed into the namespace by **trust-manager**
  (see `infra/trust-manager`), so no CA material needs to be supplied to this app.

> **Requires** `infra/trust-manager` with `secretTargets.enabled: true` and a Bundle
> writing the `tls-ca` secret (`cacerts.pem`) into `${RANCHER_NAMESPACE}`.

## SECRET

```bash
kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: rancher
  namespace: flux-system
type: Opaque
stringData:
  BOOTSTRAP_PASSWORD: "ChangeMe123" #pragma: allowlist secret
EOF
```

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux-rancher-dev
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: feature/add-rancher
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: rancher
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux-rancher-dev
  path: ./apps/rancher
  prune: true
  wait: true
  postBuild:
    substitute:
      RANCHER_NAMESPACE: cattle-system
      RANCHER_VERSION: 2.14.2
      RANCHER_REPLICAS: "3"
      INGRESS_HOSTNAME: rancher
      INGRESS_DOMAIN: fluxdev-3.sthings-vsphere.example.com
      CLUSTER_ISSUER: cluster-issuer-approle
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
    substituteFrom:
      - kind: Secret
        name: rancher
EOF
```

## VARIABLES

Run `task get-variables` against this folder to list all `\${VAR:-default}` substitutions.

| Variable | Default | Purpose |
|---|---|---|
| `RANCHER_NAMESPACE` | `cattle-system` | Target namespace |
| `RANCHER_VERSION` | `2.14.2` | Rancher chart version |
| `RANCHER_REPLICAS` | `3` | Rancher replica count |
| `STHINGS_CLUSTER_VERSION` | `0.3.20` | `sthings-cluster` helper chart version |
| `INGRESS_HOSTNAME` | `rancher` | Hostname prefix |
| `INGRESS_DOMAIN` | _(required)_ | Base domain |
| `CLUSTER_ISSUER` | _(required)_ | cert-manager `ClusterIssuer` for the gateway cert |
| `GATEWAY_NAME` | _(required)_ | Gateway API `Gateway` name |
| `GATEWAY_NAMESPACE` | `default` | Gateway namespace |
| `BOOTSTRAP_PASSWORD` | _(secret)_ | Initial admin bootstrap password |
