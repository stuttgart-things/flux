# apps/sthings-portal

[sthings-portal](https://github.com/stuttgart-things/sthings-portal), the
successor of homerun2-portal: one page for the services behind it (a card per
service with its status, each service's UI under `/<key>/` through the
portal's reverse proxy), with **login through an OIDC provider (ZITADEL)** and
the local users file as **emergency access**. Selected through the bundle
component [`apps/platform/components/sthings-portal`](../platform/components/sthings-portal);
first consumer is platform-sthings (stuttgart-things/stuttgart-things#4141),
second the per-cluster **machinery-portal** for the lab services
(stuttgart-things/stuttgart-things#4221, see [Instances](#instances)).

```
apps/platform/components/sthings-portal/   everything Flux-specific
├── ks-sthings-portal.yaml          OCIRepository sthings-portal-kustomize
│                                   + Kustomization sthings-portal (patches)
├── ks-sthings-portal-routes.yaml   Kustomization sthings-portal-routes → ./route
└── profile.yaml                    AppProfile
apps/sthings-portal/
├── README.md                       this file
└── route/                          the HTTPRoute (plain manifest)
```

## Design

**The base is the release's artifact.** Each sthings-portal release pushes
`ghcr.io/stuttgart-things/sthings-portal-kustomize:<tag>`: a kustomize
directory (ServiceAccount, ConfigMap, Deployment, Service, HTTPRoute) rendered
by the portal's KCL module (`kcl/`) with `tests/kcl-deploy-profile.yaml`, the
image pinned to the same tag. Those are plain Kubernetes manifests -- no Flux
CRs, no substitution variables -- so they are the base here, consumed
unchanged.

**Flux lives in the component, only.** `ks-sthings-portal.yaml` holds the
OCIRepository and the Kustomization that applies the artifact with
`targetNamespace` and three patches. Unlike homerun2-portal, run-things or
clusterscope there is no second, inner Kustomization under `./apps/<app>`:
this directory carries no Flux object. `route/` is a plain HTTPRoute; its
`${...}` are filled in by the routes Kustomization's `postBuild`.

**The patches are what KCL renders for `authMode: oidc`.** The artifact is
rendered with `authMode: none`; the patches add the `AUTH_*` settings to the
ConfigMap, the Secret's keys as env, and the users file and the CA as
volumes, with the same names and paths as `kcl/deploy.k` and
`kcl/configmap.k` -- but with every Secret key and both volumes `optional`
(KCL: session-key, the users and the CA volume are not), so the same patches
serve `STHINGS_PORTAL_AUTH_MODE` `oidc`, `local` and `none`; the portal checks
at start what its mode needs ([Login](#login-oidc-local-or-none)). Checked when this was added (v0.13.0): the artifact plus the
patches and a `kcl run` with the same values in `config.authMode: oidc`
render the same ServiceAccount, ConfigMap, Deployment and Service, the only
difference being the Reloader annotation. A portal release that changes how
KCL wires auth has to be mirrored here -- read the KCL diff when renovate
bumps `STHINGS_PORTAL_VERSION`.

**The artifact's own HTTPRoute is removed** and replaced by `route/`, applied
by `sthings-portal-routes` after `sthings-portal` is Ready: Cilium resolves a
route's backendRefs once, and a route applied before its Service serves HTTP
500 for good (`apps/homerun2/README.md`, "Routes come last").

### ArgoCD later (not built)

Nothing here is needed to run the same portal from ArgoCD:

- Source: the same OCI artifact. ArgoCD (3.1+) reads OCI artifacts directly
  (`repoURL: oci://ghcr.io/stuttgart-things/sthings-portal-kustomize`,
  `targetRevision: v0.13.0`, `path: .`) and builds it with kustomize; the
  layer is a plain `application/vnd.oci.image.layer.v1.tar+gzip`, one of the
  media types ArgoCD accepts by default.
- Settings: the three patches of `ks-sthings-portal.yaml`, copied into the
  Application's `spec.source.kustomize.patches` with the values written out
  (ArgoCD does not substitute `${...}`), and `spec.destination.namespace`
  instead of `targetNamespace`.
- Route: patch the artifact's own HTTPRoute (parentRefs, hostname) instead of
  deleting it. ArgoCD orders by sync wave, so the route gets a later wave than
  the Service rather than a Kustomization of its own.
- Secret and CA ConfigMap: the same, created by hand or by the SOPS CMP.

The cleaner long-term step is upstream: a second artifact rendered with an
auth profile (or ArgoCD rendering `kcl/` with its own profile), so neither
tool has to patch.

## Variables

| Variable | Default | |
|---|---|---|
| `INFRA_DOMAIN` | -- | REQUIRED: host is `${STHINGS_PORTAL_HOSTNAME}.${INFRA_DOMAIN}` |
| `STHINGS_PORTAL_HOSTNAME` | `portal` | the same default host as homerun2-portal -- select one of the two |
| `STHINGS_PORTAL_NAMESPACE` | `homerun2` | must exist; not created here (see [Instances](#instances)) |
| `STHINGS_PORTAL_VERSION` | `v0.14.0` | artifact tag = image tag (renovate) |
| `STHINGS_PORTAL_SERVICES` | `led=http://homerun2-led-catcher` | `key=url` or `key\|Title=url`, comma-separated, in navigation order |
| `STHINGS_PORTAL_THEME` | `homerun2` | `homerun2` or `machinery` |
| `STHINGS_PORTAL_AUTH_MODE` | `oidc` | `oidc`, `local` or `none` -- [Login](#login-oidc-local-or-none) |
| `STHINGS_PORTAL_OIDC_ISSUER` | *(empty)* | REQUIRED with `oidc`, e.g. `https://zitadel.<infra domain>`; ignored otherwise |
| `STHINGS_PORTAL_OIDC_CLIENT_ID` | *(empty)* | REQUIRED with `oidc` (not secret); ignored otherwise |
| `STHINGS_PORTAL_OIDC_ALLOWED_GROUPS` | *(empty: every user the provider lets through)* | comma-separated, e.g. `portal-admin,portal-user` |
| `STHINGS_PORTAL_OIDC_NAME` | `Zitadel` | label of the login button |
| `STHINGS_PORTAL_OIDC_CA_CONFIGMAP` | `cluster-trust-bundle` | ConfigMap with the CA that signed the provider's certificate |
| `STHINGS_PORTAL_OIDC_CA_KEY` | `trust-bundle.pem` | its key |
| `STHINGS_PORTAL_FAVICON` | *(empty: the theme's built-in icon)* | a file in the favicon ConfigMap, e.g. `/etc/portal/favicon/favicon.svg` (`.svg`, `.png`, `.ico`, at most 1 MiB; v0.14.0+) |
| `STHINGS_PORTAL_FAVICON_CONFIGMAP` | `sthings-portal-favicon` | ConfigMap mounted (optional) at `/etc/portal/favicon` |
| `STHINGS_PORTAL_AUTH_SECRET` | `sthings-portal-auth` | the Secret below |
| `STHINGS_PORTAL_SESSION_TTL` | `12h` | |
| `STHINGS_PORTAL_SUSPEND` | `false` | |
| `INFRA_GATEWAY_NAME` / `INFRA_GATEWAY_NAMESPACE` | `cilium-gateway` / `default` | route only |

All values land as plain YAML scalars after substitution: no leading `#`,
`!`, `&`, `*`, no `: ` or ` #`.

The redirect URI is `https://${STHINGS_PORTAL_HOSTNAME}.${INFRA_DOMAIN}/auth/callback`,
the post-logout URI `.../auth/login`. Register exactly those at the provider.

## Instances

One component, two kinds of instance -- the difference is variables only, the
patches are the same. One instance per cluster: the object names
(`sthings-portal`, `sthings-portal-routes`, Deployment `sthings-portal`, ...)
are fixed.

| | homerun2 portal (platform-sthings) | machinery-portal (infra clusters) |
|---|---|---|
| Services | the homerun2 services, short names in `homerun2` | the lab services on that cluster (clusterbook, clusterscope, machinery, claim-machinery-api), full in-cluster names |
| `STHINGS_PORTAL_NAMESPACE` | `homerun2` (default; owned by homerun2-sops) | `machinery-portal` -- shipped by the cluster repo |
| `STHINGS_PORTAL_HOSTNAME` | `portal` (default) | `machinery-portal` |
| `STHINGS_PORTAL_THEME` | `homerun2` (default) | `machinery` |
| `STHINGS_PORTAL_OIDC_*` | ZITADEL on infra-sthings, client `lab-portal` | the ZITADEL on the same cluster, client `machinery-portal` |

**machinery-portal, the settings of one cluster** (LabUL infra-sthings):

```yaml
components:
  - ../components/clusterbook
  - ../components/sthings-portal
postBuild:
  substitute:
    INFRA_DOMAIN: infra.sthings-vsphere.labul.sva.de
    CLUSTERBOOK_BASE_PATH: /clusterbook          # = the portal key below
    STHINGS_PORTAL_NAMESPACE: machinery-portal
    STHINGS_PORTAL_HOSTNAME: machinery-portal
    STHINGS_PORTAL_THEME: machinery
    STHINGS_PORTAL_SERVICES: clusterbook|Clusterbook=http://clusterbook-http.clusterbook.svc.cluster.local:8080
    STHINGS_PORTAL_OIDC_ISSUER: https://zitadel.infra.sthings-vsphere.labul.sva.de
    STHINGS_PORTAL_OIDC_CLIENT_ID: "<terraform output client_ids machinery-portal>"
    STHINGS_PORTAL_OIDC_ALLOWED_GROUPS: portal-admin,portal-user
    STHINGS_PORTAL_AUTH_SECRET: machinery-portal-auth
```

- **Each service runs with `BASE_PATH=/<key>`**, the key of its
  `STHINGS_PORTAL_SERVICES` entry: the portal forwards `/<key>/...`
  unchanged. clusterbook: `CLUSTERBOOK_BASE_PATH: /clusterbook`, and the
  Service `clusterbook-http` (8080, HTTP) -- `clusterbook` (80) is gRPC.
- **The namespace comes from the cluster repo**, in the same directory as the
  SOPS Secret (`machinery-portal-namespace.yaml` beside
  `machinery-portal-auth.enc.yaml`): the cluster's Kustomization applies both
  in one go, the Namespace first. Created by this component instead, the
  Secret's apply in the cluster's Kustomization would fail on the missing
  namespace before the bundle that creates it is even updated.
- **Title and subtitle are the theme's**: `machinery` / `LAB PORTAL` (page
  title `machinery portal`). The portal reads `PORTAL_TITLE` and
  `PORTAL_SUBTITLE`, but the component does not pass them: two more keys in
  the ConfigMap patch would change every existing instance's rendering (and
  roll its pod) for no difference in what it shows.

## Login: oidc, local or none

`STHINGS_PORTAL_AUTH_MODE` picks the login. ZITADEL is needed for `oidc`
only; the patches are the same in every mode, and the portal checks at start
what its mode needs (sthings-portal `internal/auth`, `internal/config`) and
exits with the variable's name in its log if something is missing.

| Mode | Login | Needs | Ignored |
|---|---|---|---|
| `oidc` (default) | the provider's button, plus the users file as emergency access | Secret with `session-key`, `users` (at least one user: `AUTH_USERS_FILE` is set), `oidc-client-secret` (unless a public client); `STHINGS_PORTAL_OIDC_ISSUER`, `STHINGS_PORTAL_OIDC_CLIENT_ID`; the CA ConfigMap; the client registered at the provider | -- |
| `local` | user / password from the users file | Secret with `session-key` and `users` | `AUTH_OIDC_*`, the CA ConfigMap, `oidc-client-secret` |
| `none` | none -- **everyone who reaches the host sees every service** | nothing | the Secret, the CA ConfigMap, every `AUTH_*` |

`oidc` and `local` keep the Secret below; `local` simply leaves out
`oidc-client-secret`:

```yaml
STHINGS_PORTAL_AUTH_MODE: local
STHINGS_PORTAL_AUTH_SECRET: my-portal-auth     # users + session-key
```

```bash
htpasswd -nB admin > users                     # one line per user
kubectl create secret generic my-portal-auth -n <namespace> \
  --from-file=users=./users \
  --from-literal=session-key="$(openssl rand -base64 48)" \
  --dry-run=client -o yaml > my-portal-auth.yaml   # SOPS-encrypt, then commit
```

`none` needs no Secret and no CA (the volumes are optional) -- only for a
portal on a network where every visitor may use every service behind it:

```yaml
STHINGS_PORTAL_AUTH_MODE: none
```

The rendered `AUTH_OIDC_*` keys stay in the ConfigMap in every mode (empty
where not set); the portal reads them with `oidc` only.

## The Secret

The pod reads one Secret in its namespace, `STHINGS_PORTAL_AUTH_SECRET`
(modes `oidc` and `local`; `none` reads none). It is
**not** rendered by the component: `oidc-client-secret` exists only in the
Terraform state that registered the client, and nothing here should hold a
copy. Create it by hand, SOPS-encrypted, next to the cluster's other secrets.

| Key | |
|---|---|
| `users` | REQUIRED (`oidc`, `local`). The emergency access (with `oidc`) or the only login (`local`), one `name:bcrypt-hash[:group,group]` per line (`htpasswd -nB <name>`). Mounted optional: without it, or with no line in it, the portal refuses to start (`AUTH_USERS_FILE` in its log). |
| `session-key` | REQUIRED (`oidc`, `local`), at least 32 bytes: `openssl rand -base64 48`. A new one ends every session. Optional in the pod spec; the portal refuses to start without it. |
| `oidc-client-secret` | `oidc`: the client's secret (leave it out only for a public PKCE client). |
| `kiosk-token` | Optional, at least 32 bytes: read-only access for a kiosk display (`openssl rand -hex 32`). |

Reloader restarts the pod when the Secret changes; the portal reads it at
start only.

## The CA

ZITADEL is served under its Gateway's wildcard certificate from the lab's
Vault PKI, so the portal has to trust that CA (`AUTH_OIDC_CA_FILE`), or the
login ends in "not reachable" with an `x509` error in the log. The CA file is
read at start (`oidc` only): the volume is optional, so a missing ConfigMap
leaves the file out and the portal exits with `AUTH_OIDC_CA_FILE` in its log;
`local` and `none` do not read it.

- **Default: trust-manager's `cluster-trust-bundle`** (key `trust-bundle.pem`),
  which trust-manager copies into every namespace. Enough when the bundle
  carries the CA that signed the provider's certificate -- the case where both
  clusters chain to the same Vault PKI. Check from a machine that has the
  bundle:

  ```bash
  kubectl -n homerun2 get cm cluster-trust-bundle -o jsonpath='{.data.trust-bundle\.pem}' > /tmp/bundle.pem
  openssl s_client -connect zitadel.<infra domain>:443 -servername zitadel.<infra domain> \
    -CAfile /tmp/bundle.pem </dev/null 2>/dev/null | grep 'Verify return code'   # 0 (ok)
  ```

- **Otherwise a ConfigMap of its own** with the provider's CA, and
  `STHINGS_PORTAL_OIDC_CA_CONFIGMAP: sthings-portal-oidc-ca`,
  `STHINGS_PORTAL_OIDC_CA_KEY: ca.crt`. The wildcard Secret on the
  provider's cluster carries the CA:

  ```bash
  KUBECONFIG=~/.kube/<provider cluster> kubectl -n default get secret <wildcard tls secret> \
    -o jsonpath='{.data.ca\.crt}' | base64 -d > ca.crt
  kubectl create configmap sthings-portal-oidc-ca -n homerun2 --from-file=ca.crt \
    --dry-run=client -o yaml > sthings-portal-oidc-ca.yaml   # commit it with the cluster
  ```

## Favicon

Without anything set the portal serves its theme's built-in icon at
`/favicon.ico` (no login needed). An own icon: a ConfigMap in the portal's
namespace plus the path to the file in it --

```bash
kubectl create configmap sthings-portal-favicon -n homerun2 --from-file=favicon.svg \
  --dry-run=client -o yaml > sthings-portal-favicon.yaml   # commit it with the cluster
```

```yaml
STHINGS_PORTAL_FAVICON: /etc/portal/favicon/favicon.svg
```

The volume is optional, so a missing ConfigMap only leaves the directory
empty -- but a `STHINGS_PORTAL_FAVICON` pointing at a file that is not there
stops the portal at start. Set the variable together with the ConfigMap.

## Replacing homerun2-portal

Both components default to the host `portal.<INFRA_DOMAIN>`, in different
objects (`homerun2-portal*` vs `sthings-portal*`), so nothing collides but the
host. Swap them **in one change** of the cluster's component list: remove
`../components/homerun2-portal`, add `../components/sthings-portal`, rename
`HOMERUN2_PORTAL_SERVICES` to `STHINGS_PORTAL_SERVICES`. The bundle then
prunes `homerun2-portal` and `homerun2-portal-routes` (and with them the old
route, Deployment, Service, ConfigMap and OCIRepository) and creates
`sthings-portal`; `sthings-portal-routes` follows once the new pod is Ready.
The host is down from the old route's removal until the new route is applied,
typically a minute or two. Selecting both components instead would leave two
routes for one host and path, which the Gateway settles by age -- the old one
would keep winning.
