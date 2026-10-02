# cicd/crossplane/runtime-defaults

Fallback `DeploymentRuntimeConfig`s for a cluster on the **machinery profile
that has no machinery fleet state**. Opt-in through the bundle component
[`crossplane-runtime-defaults`](../../platform/components/crossplane-runtime-defaults).

## Why it exists

The [machinery profile](../profiles/machinery/configs/configs.yaml) is generated
from the KCL catalog. Two of its providers carry a `runtimeConfigRef` to a
config the profile does **not** create:

| Provider | `runtimeConfigRef` | what the config does |
|---|---|---|
| `stuttgart-things-provider-kubeconfig-xpkg` | `provider-kubeconfig` | lab CA for the Vault client (`VAULT_CACERT`), stable SA name |
| `vshn-provider-minio` | `provider-minio` | lab CA via `SSL_CERT_FILE` -- its ProviderConfig has no CA field |

That is deliberate (`hack/gen-crossplane-profile.py`, the `external` branch):
the CA belongs to the cluster, not to the fleet. On the `machinery` cluster the
fleet state in `stuttgart-things` supplies both
(`clusters/labda/vsphere/machinery-fleet-state/provider-minio-runtime.yaml`, and
the `provider-kubeconfig-vault` Helm release from `provider-kubeconfig.yaml`).

A cluster with `CROSSPLANE_PROFILE: machinery` and no fleet state has neither,
and both providers stay `Healthy=False: DeploymentRuntimeConfig "provider-…" not
found` for good (stuttgart-things#3374: cicd-machinery-test5, cicd-test4).
Nothing else turns red, because `crossplane-configs` health-checks
Configurations only.

## What it ships

The same two objects, in the same shape (container `package-runtime`,
`selector: {}`, CA at `/etc/ssl/lab/ca.crt`). Only the CA **source** differs:

| | fleet state (`machinery`) | this directory |
|---|---|---|
| CA volume | Secret `vault-pki-ca` (rendered by the chart) | ConfigMap `cluster-trust-bundle`, key `trust-bundle.pem`, mapped to `ca.crt` |
| contents | the three lab roots | trust-manager's bundle: the public roots plus **this cluster's** CAs |

**The contents differ, and that is the limit of this fallback.** On the LabDA
cicd clusters (cicd-machinery-test5, cicd-test4; checked 2026-10-02) the bundle
holds `tiab.labda.sva.de` but neither `labul.sva.de` nor
`infra.sthings-vsphere.labul.sva.de`. The providers become Healthy and can reach
LabDA endpoints; a ProviderConfig pointing at a LabUL Vault or MinIO would still
fail with `x509: certificate signed by unknown authority`. Neither cluster has
such a ProviderConfig today (no `provider-kubeconfig-vault` release, no MinIO
ProviderConfig). A cluster that needs them wants the fleet-state path, or the
missing roots added to its trust-manager Bundle.

| Variable | Default | |
|---|---|---|
| `CROSSPLANE_RUNTIME_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | trust-manager's `TRUST_BUNDLE_NAME` |
| `CROSSPLANE_RUNTIME_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | trust-manager's `TRUST_BUNDLE_TARGET_KEY` |

The ConfigMap has to exist in the crossplane namespace -- trust-manager's
`cluster-trust-bundle` Bundle syncs it into every namespace. The mount is **not**
optional: a provider without the lab CA starts and fails every TLS handshake
with `x509: certificate signed by unknown authority`, which reads like a
credentials problem; a missing ConfigMap keeps the pod in `ContainerCreating`
with an event that names it.

## Ownership: this OR the fleet state, never both

| cluster | owner of `provider-kubeconfig` / `provider-minio` |
|---|---|
| `machinery` (fleet state) | Helm release `provider-kubeconfig-vault` / Kustomization `machinery-fleet-state` |
| machinery profile, no fleet state | **this component** |
| play-built kind machinery cluster | the play's `provider-kubeconfig-vault` chart -- do not select |
| `cicd-platform` profile | nobody; no Provider references them -- selecting is harmless and pointless |

Two owners on one object rewrite each other every reconcile, and whichever
wins decides which CA the provider pod mounts. To move a cluster onto a fleet
state, **remove this component first** (prune deletes the two DRCs; the
providers are `Healthy=False` until the new owner applies its own), then add
the fleet state.
