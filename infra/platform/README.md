# stuttgart-things/flux/infra/platform

A **bundle**: one Flux `Kustomization` stands up a cluster's whole infra layer.

Nothing here is a raw manifest — every `ks-*.yaml` is a Flux `Kustomization` CR
pointing back at an existing base in this repo. The consumer's
`postBuild.substitute` fills their `${VAR:-default}` values one hop, and each
child then renders its own base.

## Layout

```
infra/platform/
├── root/          empty kustomization — the consumer's spec.path
└── components/    one kustomize Component per app, all opt-in
    ├── cilium-lb/                → ./infra/cilium/components/lb
    ├── cilium-gateway/           → ./infra/cilium/components/gateway        (requires cilium-lb)
    ├── cert-manager-install/     → ./infra/cert-manager/components/install
    ├── cert-manager-selfsigned/  → ./infra/cert-manager/components/selfsigned (requires cert-manager-install)
    ├── trust-manager/            → ./infra/trust-manager                    (requires cert-manager-install)
    ├── nfs-csi/                  → ./infra/nfs-csi
    ├── openebs/                  → ./infra/openebs
    ├── prometheus/               → ./infra/prometheus                       (requires cilium-gateway)
    ├── flux-web/                 → ./apps/flux-web                          (requires cilium-gateway)
    ├── headlamp/                 → ./apps/headlamp                          (requires cilium-gateway)
    └── reloader/                 → ./infra/reloader
```

There is no always-on base. The first cluster pointed at this bundle wanted
`cilium-lb` + `cert-manager-install` and neither the Gateway nor the PKI chain,
so everything is opt-in.

## Consumer usage

The cluster picks its components on its **own** Kustomization. `spec.components`
is a Flux field; the paths are relative to `spec.path`.

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-platform
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-infra
  path: ./infra/platform/root
  components:
    - ../components/cilium-lb
    - ../components/cert-manager-install
    - ../components/openebs
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_SOURCE: flux-infra
      CILIUM_LB_IP_START: '10.100.136.210'
      CILIUM_LB_IP_STOP: '10.100.136.210'
      CERT_MANAGER_NAMESPACE: cert-manager
      OPENEBS_VERSION: '4.5.1'
```

**Adding a line deploys that component. Removing one prunes everything it
deployed, and deletes its child Kustomization too.** That is the entire on/off
mechanism — there is no `<APP>_ENABLED` variable and no switch directory.

A substituted variable could never have done this job: `kustomize build`
produces the resource set first and substitution runs afterwards on its output,
so a variable can change what a resource *says*, never whether it *exists*.
Selection has to happen at build time, and `spec.components` is the build-time
mechanism Flux gives you.

Verified: an eight-component selection renders **byte-for-byte** the same
manifests as the eight hand-written CRs it replaces.

## Prerequisites between components

Six components carry a `dependsOn` and therefore need their prerequisite in
the same list:

| Component | Requires |
|---|---|
| `cilium-gateway` | `cilium-lb` |
| `cert-manager-selfsigned` | `cert-manager-install` |
| `trust-manager` | `cert-manager-install` |
| `prometheus` | `cilium-gateway` |
| `flux-web` | `cilium-gateway` |
| `headlamp` | `cilium-gateway` |

The three behind `cilium-gateway` render an `HTTPRoute` unconditionally, and an
`HTTPRoute` whose `parentRef` does not resolve sits at `Accepted=False` without
explaining itself. The dependency turns that into a loud stall instead.

Flux has no optional dependency, so selecting one without its prerequisite
parks it on "dependency not ready" instead of deploying something half-wired.
That is a loud, correct failure — but it is a failure, so check the table when
trimming a list.

## Why child Kustomizations and not one merged build

`apps/homerun2` composes components whose manifests all land in **one** Flux
Kustomization. That works there because those components are independent.

Infra is not: `cert-manager-selfsigned` applies `ClusterIssuer`/`Certificate`,
`cilium-gateway` applies a `Gateway`, `trust-manager` applies a `Bundle`,
`cilium-lb` applies `CiliumLoadBalancerIPPool` — CRs whose CRDs are installed by
the very same bundle. Merged into one build, every reconcile races those CRDs
and only converges by retry, with `wait: true` reporting failure in between.
Child CRs keep `dependsOn`, plus per-component health, retry and blast radius.

Same shape as [`cicd/argocd-platform`](../../cicd/argocd-platform).

## Freezing a component without removing it

Each child also has `<COMPONENT>_SUSPEND`, default `false`:

```yaml
postBuild:
  substitute:
    PROMETHEUS_SUSPEND: "true"     # note the quotes: substitute is map[string]string
```

`CILIUM_LB_SUSPEND`, `CILIUM_GATEWAY_SUSPEND`, `CERT_MANAGER_INSTALL_SUSPEND`,
`CERT_MANAGER_SELFSIGNED_SUSPEND`, `TRUST_MANAGER_SUSPEND`, `NFS_CSI_SUSPEND`,
`OPENEBS_SUSPEND`, `PROMETHEUS_SUSPEND`, `FLUX_WEB_SUSPEND`,
`HEADLAMP_SUSPEND`, `RELOADER_SUSPEND`.

This **stops reconciliation and leaves deployed objects running**, unmanaged —
it is for maintenance, not for "this cluster doesn't need X" (that is a line in
`spec.components`). A suspended Kustomization never reports Ready, so do not
suspend one that others depend on: everything behind it stalls.

Note it is also the one place a bool works *directly*, and the reason is worth
knowing: `spec.suspend` is a **boolean field**, so the bare `false` that
`${VAR:-false}` renders is exactly the right type. `postBuild.substitute` is
`map[string]string`, so the same bare `false` is rejected there. The field's
type decides, not the syntax — which is also the subject of the next section.

## Two constraints that shape every file here

**1. A child's substitute values must be non-empty strings.**
`kustomize build` normalises away *every* quoting style — `"${VAR}"`,
`'${VAR}'`, `!!str`, `|-` all emit plain `${VAR}` — so an unset variable
reaches Flux as `KEY:`, a YAML null, and the CRD declares
`postBuild.substitute` as `map[string]string` with no `nullable`: the API
server rejects the entire CR. A child therefore **cannot inherit** a base's
default by passing an empty value, and every threaded variable carries its own
default here.

That means chart versions exist twice — in the base (where the `# renovate:`
annotation lives) and here. `renovate.json`'s fourth `customManager` matches
these lines so both copies move in the same PR. **When adding a version
default to a `ks-*.yaml`, copy the base's `# renovate:` comment with it** —
without it the bundle silently pins the old version after the next bump.

**2. Booleans and numbers cannot be threaded at all.**
Same quote-stripping: `KEY: "${FOO:-false}"` renders as `KEY: false`, a YAML
bool, which the string-typed map rejects. Those knobs are listed as
`# NOT threaded` in the file that would carry them and are left to the base's
default (all of which already match this fleet). To change one, patch the child
from the consumer with a **literal** value — a literal keeps its quotes:

```yaml
patches:
  - target: {kind: Kustomization, name: openebs}
    patch: |
      - op: add
        path: /spec/postBuild/substitute/REPLICATED_MAYASTOR_ENABLED
        value: "true"
```

The same limit applies to two-part versions: `OPENEBS_VERSION: '4.5'` renders
as a float and is rejected — use `4.5.0`, or the literal-patch form.

## Variables

```bash
task get-variables    # every ${VAR:-default} in this folder
```

Bundle-level names (they map onto differently-named base variables):

| Variable | Default | Feeds |
|---|---|---|
| `FLUX_SOURCE` | `flux-infra` | `sourceRef.name` of every child |
| `INFRA_DOMAIN` | *(required)* | `CILIUM_GATEWAY_DOMAIN`, `CERT_MANAGER_SELFSIGNED_DOMAIN`, prometheus/flux-web/headlamp `DOMAIN` |
| `INFRA_GATEWAY_NAME` | `cilium-gateway` | `CILIUM_GATEWAY_NAME`, prometheus/flux-web/headlamp `GATEWAY_NAME` |
| `INFRA_GATEWAY_NAMESPACE` | `default` | both of the above + `CERT_MANAGER_SELFSIGNED_CERT_NAMESPACE` |
| `INFRA_TLS_SECRET` | `wildcard-tls` | `CILIUM_GATEWAY_TLS_SECRET`, `CERT_MANAGER_SELFSIGNED_{CERT,SECRET}_NAME` |
| `PROMETHEUS_HOSTNAME` | `prometheus` | prometheus `HOSTNAME` (the base's name is too generic to expose) |
| `FLUX_WEB_HOSTNAME` | `flux` | flux-web `HOSTNAME` (same reason) |
| `HEADLAMP_HOSTNAME` | `headlamp` | headlamp `HOSTNAME` (same reason) |
| `<COMPONENT>_SUSPEND` | `false` | that child's `spec.suspend` |

Required variables have no upstream default, so they fall back to an
unmistakable sentinel (`set-INFRA_DOMAIN.invalid`, `0.0.0.0`,
`set-NFS_SERVER_FQDN.invalid`) rather than a null.

Every other variable keeps its base name and its base default.

## Migrating a cluster off per-component CRs

The bundle's children are named exactly like the CRs they replace
(`cilium-lb`, `cert-manager-install`, …), so they adopt the existing objects
instead of duplicating them. Apply the bundle **first**, confirm the children
are `Ready`, then remove the old files from the cluster repo.

Do not simply `kubectl delete kustomization <name>` — those CRs have
`prune: true` and deletion takes their workloads with them. Either let the
bundle adopt them by name as above, or set `prune: false` on a CR before
deleting it.

If you are rebuilding rather than adopting, delete the old files in their own
commit and let the prune finish **before** the bundle lands, so the teardown
does not race the bundle's create — the two use the same child names.
