# stuttgart-things/flux/apps/openbao

Deploys [OpenBao](https://openbao.org) — the MPL-2.0 fork of Vault — as a
**standalone raft** instance, published through the shared Gateway API
`HTTPRoute` (the chart's own Ingress stays off).

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

## Structure

```
openbao/
├── kustomization.yaml      # Base: namespace + HelmRepository + release + HTTPRoute
├── requirements.yaml       # Namespace + openbao.github.io HelmRepository
├── release.yaml            # OpenBao HelmRelease (standalone raft, shamir)
├── httproute.yaml          # Gateway API HTTPRoute → svc/openbao:8200
└── components/
    ├── seal-transit/       # seal "transit" — a peer unwraps the key
    ├── seal-static/        # seal "static" — 32-byte key from a Secret
    └── seal-none/          # no seal stanza: shamir, unsealed by hand
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
      OPENBAO_CHART_VERSION: "0.29.2"
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
      # ---- HTTPRoute ----
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: openbao
      DOMAIN: example.sthings-vsphere.labul.sva.de
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
      OPENBAO_CHART_VERSION: "0.29.2"
      OPENBAO_STORAGE_CLASS: openebs-hostpath
      OPENBAO_STORAGE_SIZE: 8Gi
      # ---- seal: static ----
      # Opaque label — but it MUST change whenever the key changes.
      OPENBAO_SEAL_KEY_ID: openbao-2026-01
      OPENBAO_SEAL_SECRET: openbao-static-seal
      OPENBAO_SEAL_SECRET_KEY: key
      # ---- HTTPRoute ----
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: openbao
      DOMAIN: example.sthings-vsphere.labul.sva.de
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
      OPENBAO_CHART_VERSION: "0.29.2"
      OPENBAO_STORAGE_CLASS: openebs-hostpath
      OPENBAO_STORAGE_SIZE: 8Gi
      # ---- HTTPRoute ----
      GATEWAY_NAME: cilium-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: openbao
      DOMAIN: example.sthings-vsphere.labul.sva.de
EOF
```

## Parameters

### Base

| Variable | Default | Description |
|---|---|---|
| `OPENBAO_NAMESPACE` | `openbao` | Target namespace |
| `OPENBAO_CHART_VERSION` | `0.29.2` | openbao-helm chart version |
| `OPENBAO_STORAGE_CLASS` | *(required)* | StorageClass for the raft PVC — a PVC that never binds leaves the pod `Pending` while the HelmRelease reports installed |
| `OPENBAO_STORAGE_SIZE` | `8Gi` | Raft data volume size |
| `GATEWAY_NAME` | `cilium-gateway` | Gateway resource name |
| `GATEWAY_NAMESPACE` | `default` | Namespace of the Gateway |
| `HOSTNAME` | *(required)* | Hostname prefix for the HTTPRoute |
| `DOMAIN` | *(required)* | Domain suffix for the HTTPRoute |

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

## Initialize

Whichever seal is chosen, the instance still has to be **initialized once**:

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
writing a standalone Kustomization.

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
