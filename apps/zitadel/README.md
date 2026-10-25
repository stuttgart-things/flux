# apps/zitadel

[ZITADEL](https://zitadel.com) as the lab IdP (OIDC provider), from the upstream
chart at `https://charts.zitadel.com`, with the Login UI v2 and a PostgreSQL of
its own. Selected through the bundle component
[`apps/platform/components/zitadel`](../platform/components/zitadel); first
consumer is sthings-portal (stuttgart-things/stuttgart-things#4118).

Ported from the ArgoCD catalog entry `stuttgart-things/argocd: apps/zitadel`
that ran on homerun2-dev, keeping what that deployment learned (env at chart
top level, the Login UI route) and dropping what was only an ArgoCD workaround
(stripped hook annotations, sync-waves).

```
apps/zitadel/
├── kustomization.yaml       requirements + secret + postgresql + release
├── requirements.yaml        Namespace, HelmRepositories zitadel + bitnami (OCI)
├── secret.yaml              zitadel-credentials, from substitution variables
├── postgresql.yaml          HelmRelease zitadel-postgresql (bitnami chart)
├── release.yaml             HelmRelease zitadel, dependsOn zitadel-postgresql
└── components/httproute/    HTTPRoute -- applied by a SECOND Kustomization
```

## PostgreSQL: a release of its own

The zitadel chart can deploy PostgreSQL as a subchart, but that cannot work
under Helm: the init and setup jobs are pre-install hooks, which run before the
release's regular objects -- the init job waits for a StatefulSet Helm has not
created yet and fails the install. The chart's own acceptance tests install the
database as a separate release first; so does this base.

It is the bitnami chart with `bitnamilegacy/postgresql`, like apps/keycloak and
apps/harbor. Those images are frozen at `17.6.0-debian-12-r4`, and the chart is
held at `16.7.27` (renovate.json) because newer ones default to
`bitnami/postgresql:latest`. When the cluster runs cnpg-operator, CNPG is the
replacement -- with a dump/restore, not in place.

## Terraform bootstrap

`FirstInstance.Org.Machine` in `release.yaml` makes the first setup create a
machine user `terraform` with a JSON key. ZITADEL grants it **ORG_OWNER and
IAM_OWNER** (`internal/command/instance.go`, `setupAdminMembers`), and the chart's
machinekey writer stores the key as the Secret **`terraform`**, key
**`terraform.json`**, in this namespace. That is the file the zitadel Terraform
provider's `jwt_profile_file` reads:

```bash
mkdir -p ~/.config/zitadel && (umask 077;
  kubectl -n zitadel get secret terraform -o jsonpath='{.data.terraform\.json}' \
    | base64 -d > ~/.config/zitadel/terraform-key-<lab>.json)
jq -r .userId ~/.config/zitadel/terraform-key-<lab>.json   # sanity check
```

- Written **once**, on the first setup of an empty database. Later upgrades run
  the setup job again, but FirstInstance is done and nothing is rewritten.
- The Secret is created by a `kubectl` inside the setup job, so it is in neither
  the Helm nor the Flux inventory: not pruned, not overwritten.
- The key expires on `2029-01-01T00:00:00Z` (`release.yaml`). A new key
  afterwards: console → Users → Service Users → terraform → Keys, or the API
  with the old one.
- Lost the Secret before saving the key? Same place: make a new key in the
  console with the human admin below.

Self-registration is off from the start (`DefaultInstance.LoginPolicy.AllowRegister: false`,
read when the instance is created).

The human IAM_OWNER `zitadel-admin` exists too, login name
`zitadel-admin@zitadel.<ZITADEL_DOMAIN>`, with the initial password from the
Secret and a forced change at the first login.

## The Secret

`secret.yaml` renders `zitadel-credentials` from four variables the component
reads from a SOPS Secret (`zitadel-secrets` in `flux-system`):

| Variable | Key | Make it with |
|---|---|---|
| `ZITADEL_MASTERKEY` | `masterkey` | `openssl rand -base64 24` (exactly 32 characters) |
| `ZITADEL_DB_PASSWORD` | `db-password` | `openssl rand -hex 16` |
| `ZITADEL_DB_ADMIN_PASSWORD` | `db-admin-password` | `openssl rand -hex 16` |
| `ZITADEL_ADMIN_PASSWORD` | `admin-password` | `openssl rand -base64 32` (the trailing `=` is the symbol the password policy wants) |

- **The masterkey must never change.** It encrypts secrets inside the database;
  a new one leaves the data unreadable. Keep it with the database backup.
- Values land as **plain YAML scalars** (kustomize drops the quotes before Flux
  substitutes): no leading `#`, `!`, `&`, `*`, no `: ` or ` #`. The generators
  above are safe.
- The PostgreSQL passwords and the admin password are read only when the
  database is initialised. Changing them in the Secret later changes nothing
  but the Secret.

## TLS and the HTTPRoute

TLS terminates at the Gateway. ZITADEL serves h2c and is told the public origin
(`ExternalDomain`, `ExternalSecure: true`, `ExternalPort: 443`). There is no
per-host Certificate: the route attaches to the cilium-gateway's
`*.${INFRA_DOMAIN}` listener, whose wildcard certificate is the one clients
see. Clients of ZITADEL (Terraform, the portal) therefore need that wildcard's
CA -- the cluster's Vault PKI.

One HTTPRoute, two rules: `/ui/v2/login` → `zitadel-login:3000` (the Login UI v2,
where the console sends every sign-in), everything else → `zitadel:8080`. It is
applied by `zitadel-httproute`, which dependsOn `zitadel`, because Cilium
resolves a route's backends once.

## Backups

All state is in PostgreSQL, and the masterkey is needed to read it. A backup is
the PVC (or a `pg_dump`) **plus** the masterkey from SOPS. This base ships no
backup.

## Variables

| Variable | Default | |
|---|---|---|
| `ZITADEL_NAMESPACE` | `zitadel` | |
| `ZITADEL_VERSION` | `10.4.0` | chart; server and Login UI follow its appVersion |
| `ZITADEL_POSTGRESQL_VERSION` | `16.7.27` | bitnami chart, held (see above) |
| `ZITADEL_DOMAIN` | -- (component: `${ZITADEL_HOSTNAME:-zitadel}.${INFRA_DOMAIN}`) | baked into every token |
| `ZITADEL_STORAGE_CLASS` | -- (component: placeholder) | REQUIRED |
| `ZITADEL_STORAGE_SIZE` | `8Gi` | |
| `GATEWAY_NAME` / `GATEWAY_NAMESPACE` | `cilium-gateway` / `default` | httproute only |
