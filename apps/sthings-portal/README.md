# apps/sthings-portal

[sthings-portal](https://github.com/stuttgart-things/sthings-portal), the
successor of homerun2-portal: one page for the services behind it (a card per
service with its status, each service's UI under `/<key>/` through the
portal's reverse proxy), with **login through an OIDC provider (ZITADEL)** and
the local users file as **emergency access**. Selected through the bundle
component [`apps/platform/components/sthings-portal`](../platform/components/sthings-portal);
first consumer is platform-sthings (stuttgart-things/stuttgart-things#4141).

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
volumes, with the same names, paths and `optional` flags as `kcl/deploy.k` and
`kcl/configmap.k`. Checked when this was added (v0.13.0): the artifact plus the
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
| `STHINGS_PORTAL_NAMESPACE` | `homerun2` | must exist; not created here |
| `STHINGS_PORTAL_VERSION` | `v0.13.0` | artifact tag = image tag (renovate) |
| `STHINGS_PORTAL_SERVICES` | `led=http://homerun2-led-catcher` | `key=url` or `key\|Title=url`, comma-separated, in navigation order |
| `STHINGS_PORTAL_THEME` | `homerun2` | `homerun2` or `machinery` |
| `STHINGS_PORTAL_OIDC_ISSUER` | -- | REQUIRED, e.g. `https://zitadel.<infra domain>` |
| `STHINGS_PORTAL_OIDC_CLIENT_ID` | -- | REQUIRED (not secret) |
| `STHINGS_PORTAL_OIDC_ALLOWED_GROUPS` | *(empty: every user the provider lets through)* | comma-separated, e.g. `portal-admin,portal-user` |
| `STHINGS_PORTAL_OIDC_NAME` | `Zitadel` | label of the login button |
| `STHINGS_PORTAL_OIDC_CA_CONFIGMAP` | `cluster-trust-bundle` | ConfigMap with the CA that signed the provider's certificate |
| `STHINGS_PORTAL_OIDC_CA_KEY` | `trust-bundle.pem` | its key |
| `STHINGS_PORTAL_AUTH_SECRET` | `sthings-portal-auth` | the Secret below |
| `STHINGS_PORTAL_SESSION_TTL` | `12h` | |
| `STHINGS_PORTAL_SUSPEND` | `false` | |
| `INFRA_GATEWAY_NAME` / `INFRA_GATEWAY_NAMESPACE` | `cilium-gateway` / `default` | route only |

All values land as plain YAML scalars after substitution: no leading `#`,
`!`, `&`, `*`, no `: ` or ` #`.

The redirect URI is `https://${STHINGS_PORTAL_HOSTNAME}.${INFRA_DOMAIN}/auth/callback`,
the post-logout URI `.../auth/login`. Register exactly those at the provider.

## The Secret

The pod reads one Secret in its namespace, `STHINGS_PORTAL_AUTH_SECRET`. It is
**not** rendered by the component: `oidc-client-secret` exists only in the
Terraform state that registered the client, and nothing here should hold a
copy. Create it by hand, SOPS-encrypted, next to the cluster's other secrets.

| Key | |
|---|---|
| `users` | REQUIRED. The emergency access, one `name:bcrypt-hash[:group,group]` per line (`htpasswd -nB <name>`). The volume mounts this key, so without it the pod does not start; with no line in it the portal refuses to start. |
| `session-key` | REQUIRED, at least 32 bytes: `openssl rand -base64 48`. A new one ends every session. |
| `oidc-client-secret` | The client's secret (leave it out only for a public PKCE client). |
| `kiosk-token` | Optional, at least 32 bytes: read-only access for a kiosk display (`openssl rand -hex 32`). |

Reloader restarts the pod when the Secret changes; the portal reads it at
start only.

## The CA

ZITADEL is served under its Gateway's wildcard certificate from the lab's
Vault PKI, so the portal has to trust that CA (`AUTH_OIDC_CA_FILE`), or the
login ends in "not reachable" with an `x509` error in the log. The CA file is
read at start: a missing ConfigMap keeps the pod in ContainerCreating.

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
