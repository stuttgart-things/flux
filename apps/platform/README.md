# apps/platform

The app layer, selected exactly like [`infra/platform`](../../infra/platform):
one kustomize Component per app, all opt-in, chosen with `spec.components` on
the consumer's own Flux Kustomization.

```
apps/platform/
├── root/          empty kustomization — the consumer's spec.path
└── components/
    ├── openbao/     → ./apps/openbao     (requires cilium-gateway, a seal)
    ├── vault/       → ./apps/vault       (existing instances only — see below)
    ├── rancher/     → ./apps/rancher     (requires cilium-gateway, cert-manager-install)
    ├── minio/       → ./apps/minio       (requires cilium-gateway + a Secret)
    ├── clusterbook/ → ./apps/clusterbook  (requires cilium-gateway + a Secret; lab-bound)
    └── vcluster/    → ./apps/vcluster
```

## Two bundles, one cluster

`infra-platform` and `apps-platform` are two Kustomizations side by side. The
apps bundle deliberately reads the **same** variable names as the infra one —
`INFRA_DOMAIN`, `INFRA_GATEWAY_NAME`, `INFRA_GATEWAY_NAMESPACE` — so a cluster
can define them once in a ConfigMap and `substituteFrom` it in both, rather
than writing its own domain twice in two files that will eventually disagree.

`dependsOn` crosses bundles freely: several apps depend on `cilium-gateway`,
which the infra bundle provides. Flux does not care which Kustomization owns a
name, only that it exists and is ready. Selecting an app whose dependency is
not selected anywhere gives no error — it waits on "dependency not ready"
forever, which reads like slowness.

## argo-cd moved

It lives in [`cicd/platform`](../../cicd/platform) now, with tekton, dapr and
crossplane. Its child Kustomization always pointed at `./cicd/argo-cd`; only
the wrapper was here, and ArgoCD is not an app a platform happens to run, it is
how a platform delivers things. A consumer that selected
`../components/argo-cd` has to repoint that line.

## Every app here needs a Secret you must supply

`rancher` and `minio` use `substituteFrom` with `optional: false`. That is on
purpose: left optional, Flux proceeds with the variables unset and installs a
MinIO with an empty admin password, and reports success.

## minio stays on chart 16

Not lag — it predates MinIO's licence change, and the pin is the point. A
higher number is not an improvement here, so the component sets no chart or
image values at all and lets the base decide.

Chart 17 does work if it is ever wanted: it splits the console into its own
deployment, and the mirror carries
`ghcr.io/stuttgart-things/minio-object-browser:2.0.2-debian-12-r3` for it. The
base parameterises the registry globally but not that repository, so it must be
set as well. That is a licence decision first and a config change second.

## `vault` never becomes Ready on its own

Its component is the only one here with `wait: false`, and that is not a
workaround. A fresh Vault starts `Initialized=false, Sealed=true`; its
readiness probe fails while sealed; so a waiting Kustomization can never
succeed on first install. It times out and retries forever against a Vault
behaving exactly as designed, until a human runs `vault operator init` and
unseals it.

Measured on cluster-test4, deploying all five components at once:

```
vault    False  timeout waiting for: [StatefulSet/vault/vault-server InProgress]
         pod Running 0/1, Sealed=true
openbao  True   unsealed by its transit seal, no human involved
```

## vault vs openbao

`vault` is here for the instances that already exist. **Prefer `openbao` for
anything new:**

- Vault is BUSL-licensed from 1.15.0 up; OpenBao is MPL-2.0.
- Auto-unseal. Vault CE has no HSM seal, so our instances use an external
  operator that stores the shamir keys *and the root token* in a Secret beside
  the server they unseal. OpenBao carries a real `seal` stanza — `transit`,
  `static` or `pkcs11` — and the `openbao` component makes that a choice.
- They are **not migratable** in either direction beyond Vault 1.14.1: the
  documented in-place path covers 1.14.1 only, needs raft + shamir, and is
  explicitly unsupported from 1.15.0 up. Moving means a new instance and moving
  workloads, not an upgrade.

The `hashicorp/vault` Terraform provider works against OpenBao unchanged —
every resource type `stuttgart-things/vault-base-setup` uses was applied
against OpenBao 2.6.2 with provider v5.11.0, PKI issuance and AppRole login
included.
