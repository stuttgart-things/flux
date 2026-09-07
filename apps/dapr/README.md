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
      DAPR_VERSION: 1.18.3
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

**You do not need to ship it.** `template-execution` mounts the cluster's own
trust bundle — the ConfigMap `cluster-trust-bundle` that trust-manager
distributes into every namespace — and points `SSL_CERT_FILE` at it. That
bundle already holds the lab CA next to the public roots, so it is right by
construction on the cluster it runs on and cannot go stale. See
[`components/template-execution/release.yaml`](./components/template-execution/release.yaml).

The command above is still how you look at the CA; fetching it by hand is for
inspection, not for deployment.

**Why not a per-cluster Secret, which is what this used to be.** The value
belongs to ONE Backstage instance, but it was seeded per cluster from a *shared*
Vault path. A LabDA cluster seeded from a path holding the LabUL CA fails every
call with `x509: certificate signed by unknown authority` while the worker, the
Deployment and every Kustomization stay green — the failure is only visible in a
workflow run's error. Witnessed on `cicd-machinery-test5`, 2026-09-07.

**On a cluster without trust-manager**, override both variables to point at a
ConfigMap that does exist:

| variable | default |
|---|---|
| `DAPR_BACKSTAGE_CA_CONFIGMAP` | `cluster-trust-bundle` |
| `DAPR_BACKSTAGE_CA_KEY` | `trust-bundle.pem` |

Getting this wrong is loud: the pod cannot mount the volume and never starts.
That is deliberate — a missing CA should stop the workflow up front rather than
surface as an obscure TLS error on the first call.

## Adding a new dapr-based workflow app

1. Create `components/<new-app>/` with its own `requirements.yaml`,
   `release.yaml`, optional `secrets.yaml`, and a `kind: Component`
   `kustomization.yaml`.
2. Add it to the top-level `kustomization.yaml` under `components:`.
3. Wire a cluster-side Flux `Kustomization` pointing at
   `./apps/dapr/components/<new-app>` with `dependsOn: dapr-control-plane`.
