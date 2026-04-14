# stuttgart-things/flux/apps/dapr

Collection of Flux components for running [Dapr](https://dapr.io) and the
workflows built on top of it. Follows the same *collection pattern* as
`apps/homerun2` — one top-level folder, one sub-folder per component under
`components/`. Each component is self-contained and can be targeted
individually by a Flux `Kustomization` via its own `path:`.

## Layout

```
apps/dapr/
├── kustomization.yaml         # aggregate — lists all components
├── README.md                  # this file
└── components/
    ├── control-plane/         # Dapr runtime (Helm chart, dapr-system ns)
    │   ├── kustomization.yaml
    │   ├── requirements.yaml
    │   ├── release.yaml
    │   └── README.md
    └── template-execution/    # dapr-backstage-template-execution workflow app
        ├── kustomization.yaml
        ├── requirements.yaml
        ├── release.yaml
        ├── secrets.yaml
        └── README.md
```

Each `components/<name>/kustomization.yaml` is a `kind: Component` so it
composes cleanly into the aggregate while still being buildable on its
own — the same convention used by `infra/cert-manager/components/*`.

## Components

| Component | Purpose | Details |
|-----------|---------|---------|
| [`control-plane`](./components/control-plane/README.md) | Dapr runtime (operator, placement, scheduler, sentry, sidecar injector) via the official Helm chart | Namespace: `dapr-system` |
| [`template-execution`](./components/template-execution/README.md) | `dapr-backstage-template-execution` workflow worker — drives Backstage scaffolder templates and watches the resulting GitHub Actions run | Namespace: `backstage-workflows` |

The control-plane must reconcile before `template-execution` — the cluster-side
Flux `Kustomization` for template-execution therefore uses `dependsOn` on the
control-plane Kustomization.

## Wiring into a cluster

Target each component independently from the consuming cluster. Example
(`stuttgart-things/clusters/labul/vsphere/cd-mgmt-1/apps/dapr.yaml`):

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: dapr-control-plane
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./apps/dapr/components/control-plane
  prune: true
  wait: true
  postBuild:
    substitute:
      DAPR_NAMESPACE: dapr-system
      DAPR_VERSION: 1.17.4
      DAPR_HA_ENABLED: "false"
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: dapr-backstage-template-execution
  namespace: flux-system
spec:
  dependsOn:
    - name: dapr-control-plane
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./apps/dapr/components/template-execution
  prune: true
  wait: true
  postBuild:
    substitute:
      DAPR_BACKSTAGE_TPL_NAMESPACE: backstage-workflows
      DAPR_BACKSTAGE_TPL_VERSION: 60b81b0cbb6b
      DAPR_BACKSTAGE_TPL_IMAGE_TAG: 60b81b0cbb6b
      FLUX_SOURCE_API_VERSION: v1
```

## Variables

See each component's README for the full list of `postBuild.substitute`
variables and their defaults:

- [`components/control-plane`](./components/control-plane/README.md#variables)
  — `DAPR_VERSION`, `DAPR_NAMESPACE`, `DAPR_HA_ENABLED`
- [`components/template-execution`](./components/template-execution/README.md)
  — `DAPR_BACKSTAGE_TPL_NAMESPACE`, `DAPR_BACKSTAGE_TPL_VERSION`,
  `DAPR_BACKSTAGE_TPL_IMAGE_TAG`, plus `GITHUB_TOKEN` /
  `BACKSTAGE_AUTH_TOKEN` / `REDIS_PASSWORD` via a SOPS-encrypted Secret or
  `substituteFrom`.

## Backstage CA trust

The `template-execution` workflow talks to Backstage over HTTPS. When the
Backstage endpoint is served with a cert signed by an internal CA (e.g.
`CN=infra.sthings-vsphere.labul.sva.de`), the pod will fail TLS
verification with `unable to get local issuer certificate` unless that
CA is mounted into the `workflow` container.

Download the internal CA straight from the Vault PKI endpoint (same
pattern as `stuttgart-things/images/sthings-alpine/Dockerfile`):

```bash
# CN=infra.sthings-vsphere.labul.sva.de — signs *.platform.sthings-vsphere.labul.sva.de
wget -O /tmp/infra-vsphere-ca.crt \
  https://vault.infra.sthings-vsphere.labul.sva.de/v1/pki/ca/pem \
  --no-check-certificate

# verify
openssl x509 -in /tmp/infra-vsphere-ca.crt -noout -subject -issuer -dates
```

Ship the PEM as a `Secret` named `backstage-ca` in the
`${DAPR_BACKSTAGE_TPL_NAMESPACE}` namespace (key: `ca.crt`). The
`template-execution` component re-adds the volume, mount and
`SSL_CERT_FILE` env on the `workflow` container so the CA is trusted at
runtime — see
[`components/template-execution/release.yaml`](./components/template-execution/release.yaml).
An example cluster-side Secret lives at
`stuttgart-things/clusters/labul/vsphere/cd-mgmt-1/apps/dapr-backstage-ca.yaml`.

## Adding a new dapr-based workflow app

1. Create `components/<new-app>/` with its own `requirements.yaml`,
   `release.yaml`, optional `secrets.yaml`, and a `kind: Component`
   `kustomization.yaml`.
2. Add it to the top-level `kustomization.yaml` under `components:`.
3. Wire a cluster-side Flux `Kustomization` pointing at
   `./apps/dapr/components/<new-app>` with `dependsOn: dapr-control-plane`.
