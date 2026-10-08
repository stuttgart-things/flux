# stuttgart-things/flux/apps/openbao

Deploys [OpenBao](https://openbao.org) — the MPL-2.0 fork of Vault — as a
**standalone raft** instance, published through the shared Gateway API
`HTTPRoute` (the chart's own Ingress stays off). The route is a component of its
own, applied **after** the release — see
[The HTTPRoute](#the-httproute-is-applied-after-the-release).

This is a **new instance, not a migration**. The documented in-place Vault →
OpenBao migration only covers Vault 1.14.1 with raft + shamir and is explicitly
unsupported from Vault 1.15.0 up, so an existing `apps/vault` 1.20.x cannot take
that path — stand a fresh one up and move workloads over.

## The seal is a component, and one must be chosen

The base deploys a **shamir** OpenBao: it starts **sealed** and stays that way
until a human unseals it. Which seal you get is decided by the component named
in the consumer `Kustomization`:

| Component | What unseals it | Use when |
|---|---|---|
| `./components/seal-transit` | another Vault/OpenBao unwraps the master key on start | **preferred** — a peer already exists |
| `./components/seal-static` | a 32-byte key read from a Secret | the **first** instance in an environment, with no peer to chain to |
| `./components/seal-none` | a human, after every pod restart | short-lived or hand-held instances |

The seal lives in a component rather than a substitution variable because it is
a **block in an HCL document** — no `${VAR:-default}` can conditionally omit a
stanza, and a half-written seal stanza does not fail: it starts an instance that
cannot be unsealed by the mechanism anyone expects.

`seal-none` is a deliberately **empty** component rather than "just leave the
line off", so that a cluster's seal choice is always visible where its apps are
listed. A cluster whose seal choice is invisible is a cluster where nobody
remembers what unseals it.

> **`spec.components` paths are relative to `spec.path`** — `./components/seal-transit`,
> not `./apps/openbao/components/seal-transit`.

> **Changing the seal of an already-initialized instance is not a component
> swap.** Repointing `components:` rewrites the config, but the data is still
> sealed by the old mechanism; OpenBao requires the documented seal-migration
> procedure (old seal stanza kept with `disabled = "true"`, unseal with
> `-migrate`) which these components do not model. Decide the seal before
> `bao operator init`.

## The HTTPRoute is applied after the release

The base renders namespace, HelmRepository and HelmRelease — **no route**. The
HTTPRoute is `./components/httproute`, and the intended use is as the `path:` of
a **second** Kustomization with `dependsOn` on the first:

```
openbao            ./apps/openbao                       + seal (+ single-node)
openbao-httproute  ./apps/openbao/components/httproute  dependsOn: openbao
```

Cilium resolves a route's `backendRefs` once. A route applied before its Service
exists serves **HTTP 500 for good** while every Kustomization reports Ready
(the reason [`apps/homerun2`](../homerun2/README.md) has its `*-routes`
profiles). In one Kustomization with the HelmRelease, the route is applied at
once and the Service only when helm-controller installs the chart. Same split as
[`apps/minio`](../minio/README.md)'s `components/httproute`.

Selecting `./components/httproute` as a **component** beside the seal instead
renders exactly what the base rendered before the route moved out — with the
race above.

> **Upgrading from a revision where the base carried the route.** A consumer of
> `./apps/openbao` that relied on it loses the route on the next reconcile
> (pruned) until it either adds the `openbao-httproute` Kustomization below or
> selects `./components/httproute`. A consumer that deleted the base's route
> with a `$patch: delete` patch needs no change there — a patch whose target
> matches nothing is a no-op — but a Kustomization that reduced the base to the
> route by deleting everything else now renders **nothing**: repoint it at
> `./apps/openbao/components/httproute`. `apps/platform/components/openbao`
> already does this (`openbao-httproute`).

## Single node: `components/single-node`

For a cluster with one node. Combine it with a seal; it changes no seal
setting:

```yaml
  components:
    - ./components/seal-static
    - ./components/single-node
```

| What | Why |
|---|---|
| `install.disableWait` + `upgrade.disableWait` | A fresh pod is **never Ready before `bao operator init`** (the readiness probe is `bao status`). A Helm install that waits for it times out, remediation uninstalls it, and the pod you need to `exec` into for the init is gone again. Without the wait the HelmRelease is Ready once the objects exist — the Service included, so the route Kustomization can follow. **Cost:** a broken upgrade no longer fails the HelmRelease; check `bao status`, not only the HelmRelease. |
| `injector.enabled: false` | Nothing on a single node is expected to use sidecar injection. `OPENBAO_INJECTOR_ENABLED: "true"` keeps it. |
| `injector.affinity: ""` | The chart's injector has a **hard** anti-affinity against itself plus a RollingUpdate: on one node the new pod never schedules beside the old one, and every chart upgrade stalls on `Deployment/openbao-agent-injector`. Matters only if the injector is enabled. Not `strategy: Recreate` — server-side apply then fails on the live, defaulted `rollingUpdate`. |
| small `server.resources` | The chart sets none; on a small box the request is what reserves the room. |

Why not in the base: on a multi-node cluster with a transit seal and a healthy
peer, Helm's wait is a real check, and the injector's anti-affinity is what
spreads it.

`./components/multi-node` is its empty counterpart, so a topology can be a
slot: the `apps/platform` components select
`./components/${OPENBAO_TOPOLOGY:-multi-node}`.

## Self-initialisation: `components/self-init-userpass`

Instead of `bao operator init` by hand, OpenBao initialises **itself** on its
first start ([`initialize`](https://openbao.org/docs/configuration/self-init/),
tested with OpenBao 2.7.0 and 2.7.1): it runs a fixed list of requests once,
on empty storage, with a root token it revokes right after. **No root token**
is handed to anyone and **no recovery keys** are created. What is left is two
userpass logins:

| Created | What |
|---|---|
| `auth/userpass` | the auth method |
| policy `terraform` | PKI at `pki/` and nothing else (below) |
| user `terraform` | `token_policies = ["terraform"]`, token TTL 1h (max 4h), password from env `OPENBAO_TERRAFORM_PASSWORD` |
| policy `admin` | `path "*"`: create, read, update, delete, list, sudo, patch |
| user `admin` | **break-glass**: `token_policies = ["admin"]`, token TTL 30m (max 1h), password from env `OPENBAO_ADMIN_PASSWORD` |

```yaml
  components:
    - ./components/seal-static          # an auto-unseal is REQUIRED
    - ./components/single-node          # optional
    - ./components/self-init-userpass   # after the seal
```

The `terraform` policy (`components/self-init-userpass/self-init.hcl`, each
path commented there):

| Path | Capabilities | For |
|---|---|---|
| `sys/mounts/pki` | create, read, update, delete | `vault_mount` -- mount, read back, unmount `pki/` |
| `sys/mounts/pki/tune` | read, update | the mount's TTLs and ACME headers |
| `sys/mounts` | read | the mount table (`bao secrets list`); hashicorp/vault 5.12 does not need it |
| `pki/*` | create, read, update, delete, list | config/cluster, config/urls, config/acme, roles, issuers, intermediate/generate/internal, intermediate/set-signed, issue/sign, acme/new-eab |
| `auth/token/lookup-self` | read | the provider's token lookup (the default policy has it too) |

Everything else is denied to `terraform`: `sys/auth`, policies, other mounts,
audit, `sys/seal`, `sys/rotate`, the userpass users, token creation. Terraform
logs in with `auth_login_userpass { username = "terraform" }` and
`skip_child_token = true`.

**The break-glass `admin`** replaces the root token for the exceptional
operation -- enabling Kubernetes auth later, a rotation, extending a policy --
without a reinstall. Its policy can do anything a root token can, but its
tokens expire (30m, at most 1h). Keep its password **only in SOPS** and use it
**by hand** (`bao login -method=userpass username=admin`), never in
automation, a pipeline or a Terraform run; Terraform has its own, narrow user.

**How it is wired.** The requests are a **second** server config file: the
ConfigMap `openbao-self-init` (mounted through `server.extraVolumes` at
`/openbao/userconfig/openbao-self-init/`) and `server.extraArgs:
-config=…/self-init.hcl`; `bao server` merges the `initialize` stanzas of all
its `-config` files. The chart's own config is not touched -- the seal
components replace that string wholesale, and a JSON patch cannot append to a
string -- so this works with either seal and either topology. The two
password envs are appended to the seal's `extraSecretEnvironmentVars`: from
keys `terraform-password` and `admin-password` of the seal Secret
`OPENBAO_SEAL_SECRET`, which `./seal-static-secret` renders from
`OPENBAO_TERRAFORM_PASSWORD` and `OPENBAO_ADMIN_PASSWORD` -- the one
SOPS-delivered Secret the instance already depends on.

**Rules:**

* **An auto-unseal is required** (`seal-static`, `seal-transit`): OpenBao
  refuses self-init with shamir. Listed after `seal-none`, or before the seal,
  the build fails -- there is no env list to append to.
* **Empty storage only.** On an instance that is already initialised it only
  changes the pod spec; OpenBao never re-runs self-init. Reinstall (delete the
  PVC), or create the users by hand there.
* **Failure is loud, at runtime.** A Secret without one of the keys keeps the
  pod in `CreateContainerConfigError` before anything is initialised -- add the
  key. An **empty** password (unset `OPENBAO_TERRAFORM_PASSWORD` or
  `OPENBAO_ADMIN_PASSWORD`: the Secret then holds `""`) fails the self-init: the server exits, and from then on refuses
  to unseal (`self-initialization failed: refusing to unseal`). Set the
  password, then delete PVC `data-openbao-0` and the pod. A render-time check
  is not possible: substitution cannot fail on an empty value.
* **The passwords are read once.** Changing them in the Secret later changes
  nothing in OpenBao; change a password as `admin` (`bao write
  auth/userpass/users/<user>/password`) and then in SOPS.
* With `self-init-userpass` the pod becomes Ready on its own, so Helm's wait
  (multi-node) passes on a fresh install; `single-node`'s no-wait is no
  longer needed for the init, and harmless.

`./components/init-none` is its empty counterpart:
`apps/platform/components/openbao-sops` selects
`./components/${OPENBAO_INIT:-init-none}`.

## The static seal key from substitution: `seal-static-secret`

`./seal-static-secret` is a **path**, not a component: the Namespace (with
`ssa: merge`, as the base renders it too) and the Secret
`OPENBAO_SEAL_SECRET` (default `openbao-static-seal`) with `key:
OPENBAO_SEAL_STATIC_KEY`, `terraform-password: OPENBAO_TERRAFORM_PASSWORD`
and `admin-password: OPENBAO_ADMIN_PASSWORD` (both optional, empty when unset;
only `components/self-init-userpass` reads them).
Apply it from a Kustomization that reads the key
from a SOPS `substituteFrom` Secret, and make `openbao` `dependsOn` it, so the
Secret exists before the HelmRelease starts the pod.
`apps/platform/components/openbao-sops` does exactly that (`openbao-prereqs`).

## Structure

```
openbao/
├── kustomization.yaml      # Base: namespace + HelmRepository + release (no route)
├── requirements.yaml       # Namespace + openbao.github.io HelmRepository
├── release.yaml            # OpenBao HelmRelease (standalone raft, shamir)
├── seal-static-secret/     # Namespace + seal-static key Secret from substitution
│                           #   (the path of a Kustomization openbao dependsOn)
└── components/
    ├── seal-transit/       # seal "transit" — a peer unwraps the key
    ├── seal-static/        # seal "static" — 32-byte key from a Secret
    ├── seal-none/          # no seal stanza: shamir, unsealed by hand
    ├── single-node/        # no Helm wait, no injector, small requests
    ├── multi-node/         # empty: the base as it is (the topology slot's default)
    ├── self-init-userpass/ # self-init on first start: userpass `terraform` (PKI-only) + break-glass `admin`
    ├── init-none/          # empty: init by hand (the init slot's default)
    └── httproute/          # Gateway API HTTPRoute → svc/openbao:8200
                            #   (the path of a second Kustomization)
```

## Requirements

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

<details><summary>SECRET — seal-transit (a token for the peer)</summary>

Make the token **periodic and renewable**: OpenBao renews it itself
(`disable_renewal` defaults to false), and that is the whole reason this does not
become a static token that dies a month later with everything reporting green.
Encrypt it with SOPS rather than applying it in the clear.

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openbao-transit-seal
  namespace: openbao
type: Opaque
stringData:
  token: "<periodic-renewable-token>" # pragma: allowlist secret
EOF
```

The peer-side half — transit mount, key, policy and that token — is **not**
created here and cannot be: it needs credentials for the other Vault/OpenBao.
Same split as `cert-manager-vault-issuer`.

The CA that signed the peer's certificate must be in the trust-bundle ConfigMap
(`OPENBAO_TRUST_BUNDLE_CONFIGMAP`), or the seal fails on x509 and the pod never
becomes ready **while the HelmRelease reports installed**.

</details>

<details><summary>SECRET — seal-static (a 32-byte key)</summary>

```bash
openssl rand -base64 32   # the key

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openbao-static-seal
  namespace: openbao
type: Opaque
stringData:
  key: "<openssl rand -base64 32 output>" # pragma: allowlist secret
EOF
```

`OPENBAO_SEAL_KEY_ID` is an **opaque label**, not a version to be clever with —
but it **must** change whenever the key does, or OpenBao cannot tell the two
apart and whatever was sealed with the old key becomes unreadable.

This stores a key that can unseal the instance in the same cluster as the
instance. That is the trade-off; prefer `seal-transit` wherever a peer exists.

</details>

## Deployment — seal `transit` (preferred)

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: openbao
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/openbao
  components:
    - ./components/seal-transit
  prune: true
  wait: true
  postBuild:
    substitute:
      OPENBAO_NAMESPACE: openbao
      OPENBAO_CHART_VERSION: "0.30.0"
      OPENBAO_STORAGE_CLASS: openebs-hostpath
      OPENBAO_STORAGE_SIZE: 8Gi
      # ---- seal: transit ----
      OPENBAO_SEAL_ADDRESS: https://vault.example.sthings-vsphere.labul.sva.de
      OPENBAO_SEAL_KEY_NAME: openbao-unseal
      OPENBAO_SEAL_MOUNT_PATH: transit/
      OPENBAO_SEAL_SECRET: openbao-transit-seal
      OPENBAO_SEAL_SECRET_KEY: token
      OPENBAO_TRUST_BUNDLE_CONFIGMAP: cluster-trust-bundle
      OPENBAO_TRUST_BUNDLE_KEY: trust-bundle.pem
EOF
```

## Deployment — seal `static` (first instance in an environment)

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: openbao
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/openbao
  components:
    - ./components/seal-static
  prune: true
  wait: true
  postBuild:
    substitute:
      OPENBAO_NAMESPACE: openbao
      OPENBAO_CHART_VERSION: "0.30.0"
      OPENBAO_STORAGE_CLASS: openebs-hostpath
      OPENBAO_STORAGE_SIZE: 8Gi
      # ---- seal: static ----
      # Opaque label — but it MUST change whenever the key changes.
      OPENBAO_SEAL_KEY_ID: openbao-2026-01
      OPENBAO_SEAL_SECRET: openbao-static-seal
      OPENBAO_SEAL_SECRET_KEY: key
EOF
```

## Deployment — seal `none` (shamir, unsealed by hand)

The pod is **not ready** until somebody unseals it, so `wait: true` would keep
the Kustomization failing until then. Either accept that or set `wait: false`.

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: openbao
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 10m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/openbao
  components:
    - ./components/seal-none
  prune: true
  wait: false
  postBuild:
    substitute:
      OPENBAO_NAMESPACE: openbao
      OPENBAO_CHART_VERSION: "0.30.0"
      OPENBAO_STORAGE_CLASS: openebs-hostpath
      OPENBAO_STORAGE_SIZE: 8Gi
EOF
```

## Deployment — the HTTPRoute (with any of the above)

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: openbao-httproute
  namespace: flux-system
spec:
  dependsOn:
    - name: openbao
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./apps/openbao/components/httproute
  prune: true
  wait: true
  postBuild:
    substitute:
      OPENBAO_NAMESPACE: openbao
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: openbao
      DOMAIN: example.sthings-vsphere.labul.sva.de
EOF
```

On a **fresh** instance `openbao` is not Ready until `bao operator init` has
run — unless it uses `components/single-node` — so the route follows only after
the init.

## Parameters

### Base

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_NAMESPACE` | `openbao` | Target namespace |
| `OPENBAO_CHART_VERSION` | `0.30.0` | openbao-helm chart version |
| `OPENBAO_STORAGE_CLASS` | *(required)* | StorageClass for the raft PVC — a PVC that never binds leaves the pod `Pending` while the HelmRelease reports installed |
| `OPENBAO_STORAGE_SIZE` | `8Gi` | Raft data volume size |
| `OPENBAO_CPU_REQUEST` | `50m` | CPU request (no CPU limit) |
| `OPENBAO_MEMORY_REQUEST` | `512Mi` | Memory request -- makes the pod Burstable, not the kernel's first OOM victim |
| `OPENBAO_MEMORY_LIMIT` | `3Gi` | Memory limit (above the ~2.1 GB seen after weeks of growth; reaching it = a restart that a transit seal unseals) |

There is **no** `OPENBAO_VERSION`: the image tag is not parameterised at all.
The chart renders `.Values.server.image.tag | default (trimPrefix "v" .Chart.AppVersion)`,
so an unset tag follows the chart *and* gets the leading `v` stripped, while an
explicit one does not. The image tags are `2.6.2`; the chart's appVersion is
`v2.6.2` — setting the obvious value yields `quay.io/openbao/openbao:v2.6.2`,
which does not exist. `OPENBAO_CHART_VERSION` is the single thing to keep
current.

### `seal-transit`

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_SEAL_ADDRESS` | *(required)* | Address of the Vault/OpenBao holding the transit key |
| `OPENBAO_SEAL_KEY_NAME` | `openbao-unseal` | Transit key name on the peer |
| `OPENBAO_SEAL_MOUNT_PATH` | `transit/` | Transit mount path on the peer |
| `OPENBAO_SEAL_SECRET` | `openbao-transit-seal` | Secret holding the peer token |
| `OPENBAO_SEAL_SECRET_KEY` | `token` | Key inside that Secret |
| `OPENBAO_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | ConfigMap with the CA that signed the peer's certificate |
| `OPENBAO_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | Key inside that ConfigMap |

The token is passed as `BAO_TOKEN` via `extraSecretEnvironmentVars`, never in
the config — the chart renders that config into a **ConfigMap**, where a token
would be plaintext to anyone with `get`.

### `seal-static`

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_SEAL_KEY_ID` | *(required)* | Opaque key label — must change whenever the key does |
| `OPENBAO_SEAL_SECRET` | `openbao-static-seal` | Secret holding the 32-byte key |
| `OPENBAO_SEAL_SECRET_KEY` | `key` | Key inside that Secret |

### `seal-none`

No variables. Base parameters only.

### `single-node`

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_INJECTOR_ENABLED` | `false` | Agent injector on/off (`"true"`/`"false"`, quoted in `postBuild.substitute`) |
| `OPENBAO_CPU_REQUEST` | `50m` | Server CPU request |
| `OPENBAO_MEMORY_REQUEST` | `128Mi` | Server memory request |
| `OPENBAO_MEMORY_LIMIT` | `512Mi` | Server memory limit |

### `self-init-userpass`

No variables of its own. It reads `OPENBAO_SEAL_SECRET` (default
`openbao-static-seal`, the Secret holding keys `terraform-password` and
`admin-password`) and `OPENBAO_NAMESPACE`. The passwords themselves go into
that Secret: `OPENBAO_TERRAFORM_PASSWORD` and `OPENBAO_ADMIN_PASSWORD` for <!-- pragma: allowlist secret -->
`./seal-static-secret`.

### `httproute`

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_NAMESPACE` | `openbao` | Namespace of the route — the release's |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway |
| `HOSTNAME` | *(required)* | Hostname prefix for the HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for the HTTPRoute |

## Initialize

Whichever seal is chosen, the instance still has to be **initialized once** --
unless it uses `components/self-init-userpass`, which does that itself:

```bash
kubectl exec -n openbao openbao-0 -- bao operator init
```

With `transit` or `static` this returns **recovery keys** (the seal does the
unsealing from then on). With `seal-none` it returns **unseal keys**, and every
pod restart needs:

```bash
kubectl exec -n openbao openbao-0 -- bao operator unseal <key>   # repeat to threshold
```

Store the output immediately — it is printed once and cannot be recovered.

## Consuming as an OCI artifact

On every merge to `main` this base is published as a Flux OCI artifact to
`oci://ghcr.io/stuttgart-things/flux/apps/openbao`, tagged with the release
version and `latest`. Point an `OCIRepository` at it instead of the Git source
(the `components:` paths in the Kustomization stay the same):

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: openbao
  namespace: flux-system
spec:
  interval: 1h
  url: oci://ghcr.io/stuttgart-things/flux/apps/openbao
  ref:
    tag: ${OPENBAO_KUSTOMIZE_VERSION:-latest}
```

## As part of the apps-platform bundle

`apps/platform/components/openbao` wires this base into the platform bundle and
picks the seal from a single variable:

```yaml
components:
  - ./components/seal-${OPENBAO_SEAL_MODE:-transit}
```

Set `OPENBAO_SEAL_MODE` to `transit`, `static` or `none` there instead of
writing a standalone Kustomization. The component renders **two** child
Kustomizations, `openbao` and `openbao-httproute` (`dependsOn: openbao`), the
split described [above](#the-httproute-is-applied-after-the-release). It does
not select `single-node`; a single-node cluster patches the `openbao` child (or
writes its own Kustomization).

## Verify deployment

```bash
# Kustomization / HelmRelease
kubectl get kustomization -n flux-system openbao
kubectl get helmrelease -n openbao openbao

# Pod, PVC (a Pending pod is usually the StorageClass)
kubectl get pods,pvc -n openbao

# Seal state — sealed=false is the thing to look for
kubectl exec -n openbao openbao-0 -- bao status

# Seal errors (bad transit address, token or CA) show up here while
# everything above still reports installed
kubectl logs -n openbao openbao-0 | grep -i seal

# HTTPRoute + UI
kubectl get httproute -n openbao
curl -sk https://<HOSTNAME>.<DOMAIN>/v1/sys/health
```
