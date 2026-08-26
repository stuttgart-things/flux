# apps/platform

The app layer, selected exactly like [`infra/platform`](../../infra/platform):
one kustomize Component per app, all opt-in, chosen with `spec.components` on
the consumer's own Flux Kustomization.

```
apps/platform/
├── root/          empty kustomization — the consumer's spec.path
└── components/
    ├── argo-cd/    → ./cicd/argo-cd    (requires cilium-gateway + a Secret)
    ├── openbao/    → ./apps/openbao    (requires cilium-gateway, a seal)
    ├── vault/      → ./apps/vault      (existing instances only — see below)
    ├── rancher/    → ./apps/rancher    (requires cilium-gateway, cert-manager-install)
    └── minio/      → ./apps/minio      (requires cilium-gateway + a Secret)
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

## Every app here needs a Secret you must supply

`argo-cd`, `rancher` and `minio` use `substituteFrom` with `optional: false`.
That is on purpose: left optional, Flux proceeds with the variables unset and
installs an ArgoCD nobody can log into, or a MinIO with an empty admin
password, and reports success either way.

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
