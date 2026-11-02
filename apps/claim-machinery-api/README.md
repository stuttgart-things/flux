# stuttgart-things/flux/claim-machinery-api

OCI kustomize-based app using `OCIRepository` + Flux `Kustomization` with Gateway API `HTTPRoute`.

## SUBSTITUTION VARIABLES

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `CLAIM_MACHINERY_API_NAMESPACE` | `claim-machinery` | no | Target namespace |
| `CLAIM_MACHINERY_API_VERSION` | `v0.10.0` | no | OCI tag + container image tag |
| `GATEWAY_NAME` | - | yes | Gateway parentRef name |
| `GATEWAY_NAMESPACE` | `default` | no | Gateway parentRef namespace |
| `HOSTNAME` | - | yes | HTTPRoute hostname prefix |
| `DOMAIN` | - | yes | HTTPRoute domain suffix |
| `CLAIM_MACHINERY_PROFILE_PATH` | composed remote URL (see below) | no | Full override for the profile source: any HTTP URL, or `/app/config/profile.yaml` for the version-pinned baked-in profile |
| `CLAIM_MACHINERY_PROFILE_REF` | `main` | no | Git ref/tag/sha used when composing the default remote profile URL (ignored if `CLAIM_MACHINERY_PROFILE_PATH` is set) |
| `CLAIM_MACHINERY_PROFILE_NAME` | `labul-vsphere` | no | Profile file name used when composing the default remote profile URL (ignored if `CLAIM_MACHINERY_PROFILE_PATH` is set) |
| `CLAIM_MACHINERY_ENABLE_HOMERUN` | `false` | no | Enable homerun2 notifications (`true`/`1`/`yes`) |
| `CLAIM_MACHINERY_HOMERUN_URL` | - | no | Omni-pitcher base URL (required when homerun enabled) |
| `CLAIM_MACHINERY_HOMERUN_AUTH_TOKEN` | - | no | Bearer token for pitcher `/pitch` endpoint (stored in Secret via pre-release) |
| `CLAIM_MACHINERY_AUTH_SECRET_NAME` | `claim-machinery-auth` | no | Secret name for the auth token |
| `CLAIM_MACHINERY_AUTH_SECRET_KEY` | `HOMERUN_AUTH_TOKEN` | no | Key within the auth secret |
| `CLAIM_MACHINERY_TRUST_BUNDLE_CONFIGMAP` | `cluster-trust-bundle` | no | ConfigMap name created by trust-manager containing CA bundle |
| `CLAIM_MACHINERY_TRUST_BUNDLE_KEY` | `trust-bundle.pem` | no | Key within the trust bundle ConfigMap |
| `CLAIM_MACHINERY_SSL_CERT_DIR` | `/etc/ssl/custom` | no | Directory to mount the CA bundle into (sets `SSL_CERT_DIR`) |
| `CLAIM_MACHINERY_API_BASE_PATH` | `/` (no prefix) | no | Prefix of UI, docs and API behind sthings-portal, e.g. `/claims` (v0.23.0+). `/` is no prefix; the env entry is always set |
| `CLAIM_MACHINERY_API_ROUTE` | `all` | no | Bundle component only: what the own hostname serves, `all` or `api` (`components/route-*`) |

### Behind sthings-portal

claim-machinery-api has no login of its own. Behind
[sthings-portal](../sthings-portal/README.md) (machinery-portal,
stuttgart-things/stuttgart-things#4262) the portal forwards `/<key>/...`
unchanged, so the service answers under that prefix:
`CLAIM_MACHINERY_API_BASE_PATH: /claims` with the portal entry
`claims|Claims=http://claim-machinery-api.claim-machinery.svc.cluster.local:8080`.
The htmx UI is then at `/claims/ui/` (template list, a form per template,
preview/render). claim-machinery-api v0.23.0+
(stuttgart-things/claim-machinery-api#117); older releases ignore it.

- `BASE_PATH` is a container env entry, so changing it rolls the pod even
  where Reloader does not run.
- **The env entry is always there**, `BASE_PATH=/` by default.
  claim-machinery-api trims the trailing slash and reads `/` as no prefix, so
  an unset cluster behaves as before -- but its Deployment gained the entry
  and rolled once when this came in (stuttgart-things/flux#945). The value
  must start with `/` (claim-machinery-api refuses to start otherwise).
- `/health`, `/version`, `/openapi`, `/openapi.yaml` and
  `/api/v1/claim-templates*` stay at the root under any prefix
  (`internal/api/server.go`, `registerRoutes`), and answer under the prefix as
  well: the claims CLI, Backstage and the kubelet probes are unchanged.

#### The own hostname: `CLAIM_MACHINERY_API_ROUTE`

The bundle component (`cicd/platform/components/claim-machinery-api`) picks
one of [`./components/route-*`](components) for the HTTPRoute on
`claim-machinery-api.<domain>`:

| `CLAIM_MACHINERY_API_ROUTE` | the own hostname serves |
|---|---|
| `all` (default) | everything: API, `/docs`, OpenAPI, `/ui/`, health |
| `api` | `/api/...`, `/health`, `/version`, `/openapi`, `/openapi.yaml` -- UI and `/docs` only through sthings-portal |

Anything else answers 404 from the Gateway (also `/`, the JSON service
summary). With `api`, set `CLAIM_MACHINERY_API_BASE_PATH` and the portal entry
too, or the UI is nowhere. The API stays on this host on purpose: the claims
CLI and Backstage call it from outside the cluster.

```yaml
# cluster's cicd/platform.yaml, postBuild.substitute
CLAIM_MACHINERY_API_BASE_PATH: /claims   # = the portal key
CLAIM_MACHINERY_API_ROUTE: api           # own host: API, health, version, OpenAPI only
```

### Profile source

`TEMPLATE_PROFILE_PATH` (the file listing the claim templates to serve) resolves as:

1. If `CLAIM_MACHINERY_PROFILE_PATH` is set, it wins verbatim — point it at any HTTP
   URL, or at `/app/config/profile.yaml` to use the version-pinned profile baked into
   the OCI artifact.
2. Otherwise it is composed as:
   `https://raw.githubusercontent.com/stuttgart-things/claim-machinery-api/${CLAIM_MACHINERY_PROFILE_REF:-main}/profiles/${CLAIM_MACHINERY_PROFILE_NAME:-labul-vsphere}.yaml`

So a new environment usually only sets `CLAIM_MACHINERY_PROFILE_NAME` (and optionally
pins `CLAIM_MACHINERY_PROFILE_REF` to a tag/sha for reproducibility).

## GIT-REPOSITORY MANIFEST

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: stuttgart-things-flux
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    tag: v1.1.0
EOF
```

## KUSTOMIZATION EXAMPLE

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: claim-machinery-api
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: stuttgart-things-flux
  path: ./apps/claim-machinery-api
  prune: true
  wait: true
  postBuild:
    substitute:
      CLAIM_MACHINERY_API_NAMESPACE: claim-machinery
      CLAIM_MACHINERY_API_VERSION: v0.10.0
      GATEWAY_NAME: whatever-gateway
      GATEWAY_NAMESPACE: default
      HOSTNAME: claim-api
      DOMAIN: whatever.sthings-vsphere.labul.sva.de
      CLAIM_MACHINERY_PROFILE_PATH: https://raw.githubusercontent.com/stuttgart-things/claim-machinery-api/refs/heads/main/profiles/labul-vsphere.yaml
      # Optional: homerun2 notifications
      CLAIM_MACHINERY_ENABLE_HOMERUN: "true"
      CLAIM_MACHINERY_HOMERUN_URL: https://pitcher.example.sthings-vsphere.labul.sva.de
      # CLAIM_MACHINERY_HOMERUN_AUTH_TOKEN: "<from substituteFrom secret>"
      # Optional: TLS trust via trust-manager CA bundle
      CLAIM_MACHINERY_TRUST_BUNDLE_CONFIGMAP: cluster-trust-bundle
      CLAIM_MACHINERY_TRUST_BUNDLE_KEY: trust-bundle.pem
      CLAIM_MACHINERY_SSL_CERT_DIR: /etc/ssl/custom
EOF
```

> **Note:** When the homerun pitcher is reachable via a cluster-internal service URL
> (e.g. `http://homerun2-omni-pitcher.homerun2.svc.cluster.local`), no CA bundle
> is needed and the `CLAIM_MACHINERY_TRUST_BUNDLE_*` variables can be omitted. The ConfigMap
> volume mount is configured with `optional: true` so the pod starts fine without the bundle.

## HOW IT WORKS

Two-layer Flux reconciliation:

1. **Outer Kustomization** (above) reads `./apps/claim-machinery-api` from the GitRepository, substitutes variables, and creates the Namespace + HelmRepository + OCIRepository + pre-release HelmRelease + inner Kustomization + HTTPRoute on the cluster
2. **Pre-release HelmRelease** (`pre-release.yaml`) uses `sthings-cluster` to create a Secret containing the homerun auth token in the target namespace
3. **Inner Kustomization** (`release.yaml`) reconciles the OCI kustomize base from `ghcr.io/stuttgart-things/claim-machinery-api-kustomize`, patches out the Ingress (replaced by HTTPRoute), overrides the container image tag, injects the auth token from the Secret, mounts the trust-manager CA bundle, and applies the resulting manifests
