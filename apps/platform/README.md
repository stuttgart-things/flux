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
    ├── backstage/   → ./apps/backstage   (requires cilium-gateway + a Secret)
    ├── clusterbook/ → ./apps/clusterbook  (requires cilium-gateway + a Secret; lab-bound)
    ├── redis-stack/ → ./apps/redis-stack (requires a StorageClass + a Secret)
    ├── harbor/      → ./apps/harbor      (requires cilium-gateway, cert-manager-install, a StorageClass + a Secret)
    ├── keycloak/    → ./apps/keycloak    (requires cilium-gateway, cert-manager-install, a StorageClass + a Secret)
    ├── openldap/    → ./apps/openldap    (requires a StorageClass + a Secret)
    ├── backstage-rag-postgres/ → ./apps/backstage-rag-postgres
    │                  (requires backstage, cnpg-operator, cnpg-barman-cloud, velero, the ESO vault store)
    ├── homepage/    → ./apps/homepage    (requires cilium-gateway + a homepage-config ConfigMap)
    ├── uptime-kuma/ → ./apps/uptime-kuma (requires cilium-gateway, trust-manager, a StorageClass)
    ├── run-things/  → ./apps/run-things  (requires cilium-gateway)
    ├── clusterscope/ → ./apps/clusterscope (requires cilium-gateway, a git repo + git-sync-auth)
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

## The apps that need a Secret you must supply

`rancher`, `minio`, `backstage`, `redis-stack`, `harbor`, `keycloak` and
`openldap` use
`substituteFrom` with `optional: false`. That is on purpose: left optional, Flux proceeds with the
variables unset and installs a MinIO with an empty admin password, and reports
success.

### AppProfiles: generating that Secret instead of writing it

`keycloak`, `harbor` and `minio` carry a `profile.yaml` next to their `ks-*.yaml`.
It lists the vars a cluster may set for the app, which of them are required, and
the Secret with its keys and how each value is made (generated, referenced from
SOPS or Vault, or literal). blueprints' `render-cluster-apps` reads it and renders
both the bundle's `spec.components` and `postBuild.substitute`, and the
SOPS-encrypted Secret in `flux-system`
([stuttgart-things/blueprints#206](https://github.com/stuttgart-things/blueprints/issues/206)).

`hack/check-app-profiles.py` keeps each profile true to its component in both
directions: the vars the component reads, `required: true` for every `set-...`
placeholder, and exactly the keys of `# substituteFrom-keys:`. Generated passwords are
`alnum`, because the releases substitute them unquoted.
`hack/vet-app-profiles.sh` checks the values themselves (generate types, ref
syntax, unknown fields) with `kcl vet` against the
[`app-profile`](https://github.com/stuttgart-things/kcl/tree/main/models/app-profile)
KCL schema.

## redis-stack needs a StorageClass

`REDIS_STACK_STORAGE_CLASS` defaults to a `set-REDIS_STACK_STORAGE_CLASS`
placeholder rather than the base's `standard`, which no cluster in this fleet
has: a missing StorageClass leaves the PVCs Pending while the HelmRelease
reports installed. The password comes from `REDIS_STACK_PASSWORD` in
`${REDIS_STACK_SECRET:-redis-stack-secrets}`.

This is a general-purpose Redis. `homerun2` and `dapr-workflows` each deploy
their own from a copy of the same base and do not use it.

## keycloak and openldap are selected together, but not wired together

Both are standalone: selecting `openldap` beside `keycloak` gives you a
directory at `ldap://openldap.openldap:389` and a Keycloak that does not know
about it. The user federation is realm configuration, done in Keycloak.

Their Secrets carry the same key names (`ADMIN_USER`, `ADMIN_PASSWORD`) — the
bases share them — so they are two Secrets, `keycloak-secrets` and
`openldap-secrets`, not one. Keycloak needs both keys; openldap only
`ADMIN_PASSWORD` (the user defaults to `admin`).

Keycloak runs behind the Gateway through `apps/keycloak/components/httproute`,
which also turns the chart's Ingress off. That is more than a route: with no
Ingress the chart stops setting `KC_HOSTNAME`, and Keycloak 26 then refuses to
start, so the component sets it — plus `proxyHeaders: xforwarded`, without
which every redirect is `http://` behind a TLS-terminating Gateway.

## Things the cluster supplies that no component ships

None of these is substituted, so no check sees them missing. Each one leaves a
pod stuck while the objects around it apply cleanly:

- **homepage** mounts a `homepage-config` ConfigMap (services, settings,
  bookmarks, widgets, kubernetes) in `HOMEPAGE_NAMESPACE`. Dashboard content is
  cluster data. Without it: ContainerCreating.
- **clusterscope** reads `username`/`password` from a `git-sync-auth` Secret in
  `CLUSTERSCOPE_NAMESPACE`, with no `optional` — dummy values for a public
  repo. Without it: CreateContainerConfigError. `CLUSTERSCOPE_GIT_REPO` is
  required as well.
- **backstage-rag-postgres** reads two entries from the ESO store's KV mount —
  `backstage-rag-postgres` (`username`, `password`) and
  `backstage-rag-postgres-s3` (`access_key`, `secret_key`) — and needs
  `RAG_PG_STORAGE_CLASS`, `RAG_S3_ENDPOINT` and a pre-created bucket. Its paths
  are relative to the store's mount, not the base's `kv/data/...` form.

## backstage needs an image tag and a GitHub OAuth app

Two things are worth knowing before selecting it:

- **`BACKSTAGE_IMAGE_TAG` is the image, not the chart.** The component leaves
  the chart version to the base, where the renovate annotation lives, and
  threads only the tag of `ghcr.io/stuttgart-things/sthings-backstage`. Its
  default is the base's `latest`, which is a placeholder rather than a choice —
  set a released tag per cluster.
- **Sign-in needs a GitHub OAuth app per cluster.** The resolver is
  `usernameMatchingUserEntityName`, so the callback URL
  `https://backstage.<domain>/api/auth/github/handler/frame` and a `User` entity
  matching the GitHub username both have to exist. `BACKSTAGE_CATALOG_ORG`
  decides which org file those entities come from.

The catalog ConfigMap the Deployment mounts is shipped by the app itself. It
used to be a cluster prerequisite, and a missing one does not degrade the
catalog — the pod never starts, while everything reports Ready.

## minio is on chart 17, and the console caveat is still open

The base sat on chart 16 deliberately — it predates MinIO's licence change, and
a higher number was not an improvement. Renovate has since carried it to
17.0.21, which the caveat below was written about and which nothing has
addressed:

Chart 17 splits the console into its own deployment with its own image. The
base parameterises the registry globally but not that repository, so it
resolves to `ghcr.io/bitnami/minio-object-browser` and cannot be pulled — while
the server keeps serving and the HelmRelease reports installed. The mirror does
carry `ghcr.io/stuttgart-things/minio-object-browser:2.0.2-debian-12-r3`, so 17
is reachable once that repository is set too. That is a licence decision first
and a config change second.

Until it is made, a cluster that needs the console pins `MINIO_VERSION` to
`16.0.10`. The component threads that variable — the image values it still
leaves entirely to the base.

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
