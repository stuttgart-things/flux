# stuttgart-things/flux/infra/platform

A **bundle**: one Flux `Kustomization` stands up a cluster's whole infra layer.

Nothing here is a raw manifest — every `ks-*.yaml` is a Flux `Kustomization` CR
pointing back at an existing base in this repo. The consumer's
`postBuild.substitute` fills their `${VAR:-default}` values one hop, and each
child then renders its own base.

## Layout

```
infra/platform/
├── base/                      the core (each child individually toggleable)
│   ├── ks-cilium-lb.yaml               → ./infra/cilium/components/lb
│   ├── ks-cilium-gateway.yaml          → ./infra/cilium/components/gateway   (dependsOn cilium-lb)
│   ├── ks-cert-manager-install.yaml    → ./infra/cert-manager/components/install
│   └── ks-cert-manager-selfsigned.yaml → ./infra/cert-manager/components/selfsigned (dependsOn cert-manager-install)
├── components/                opt-in, one kustomize Component each
│   ├── trust-manager/    → ./infra/trust-manager   (dependsOn cert-manager-install — needs base)
│   │   └── switch/{true,false}/   path target of <APP>_ENABLED
│   ├── nfs-csi/          → ./infra/nfs-csi         (standalone)
│   ├── reloader/         → ./infra/reloader        (standalone)
│   ├── openebs/          → ./infra/openebs         (standalone)
│   └── prometheus/       → ./infra/prometheus      (dependsOn cilium-gateway — needs base)
└── overlays/
    ├── infra-sthings/    base + trust-manager, nfs-csi, openebs, prometheus
    └── test-infra1/      base + every component (selection made by <APP>_ENABLED)
```

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

## Consumer usage

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
  path: ./infra/platform/overlays/infra-sthings
  prune: true
  wait: true
  postBuild:
    substitute:
      FLUX_SOURCE: flux-infra
      # --- shared, set once, fanned out to every child -------------------
      INFRA_DOMAIN: infra.sthings-vsphere.labul.sva.de
      INFRA_GATEWAY_NAME: sthings-infra-gateway
      INFRA_GATEWAY_NAMESPACE: default
      INFRA_TLS_SECRET: wildcard-sthings-infra-tls
      CERT_MANAGER_NAMESPACE: cert-manager
      CERT_MANAGER_CA_SECRET: cluster-ca-secret
      CERT_MANAGER_SELFSIGNED_ISSUER: vault-pki-k8s
      # --- per component --------------------------------------------------
      CILIUM_LB_IP_START: '10.31.101.6'
      CILIUM_LB_IP_STOP: '10.31.101.6'
      NFS_SERVER_FQDN: '10.31.101.26'
      NFS_SHARE_PATH: /data/col1/sthings
      CLUSTER_NAME: sthings-infra
      OPENEBS_VERSION: '4.2.0'
      TRUST_MANAGER_VERSION: '0.22.0'
      PROMETHEUS_STORAGE_CLASS: openebs-hostpath
```

That single block replaces the eight hand-written CRs previously kept in
`clusters/labul/vsphere/infra-sthings/infra/`, and collapses their duplication:
the cluster domain was spelled three times under three names
(`CERT_MANAGER_SELFSIGNED_DOMAIN`, `CILIUM_GATEWAY_DOMAIN`, `DOMAIN`), the
gateway name and TLS secret twice each.

Verified equivalent: rendering both hops of `overlays/infra-sthings` with the
values above produces **byte-for-byte the same manifests** as the eight CRs it
replaces.

## Turning components off

Three switches. They differ in what happens to objects that are **already
deployed**, which is the only question that matters when choosing.

| | `<APP>_ENABLED: "false"` | `<APP>_SUSPEND: "true"` | remove the line from the overlay |
|---|---|---|---|
| Where | consumer's `substitute` (cluster repo) | consumer's `substitute` (cluster repo) | `overlays/<cluster>/` (this repo) |
| Deployed objects | **pruned** | **stay**, frozen | **pruned** |
| Child Kustomization CR | stays, Ready, owns nothing | stays, suspended | deleted |
| Blocks dependents | no | **yes** | no |
| Scope | **all nine children** | all nine children | the opt-in components |

### `<APP>_ENABLED` — the on/off boolean

```yaml
postBuild:
  substitute:
    PROMETHEUS_ENABLED: "false"    # note the quotes: substitute is map[string]string
    OPENEBS_ENABLED: "false"
```

One per child, all default `true`:

| base | components |
|---|---|
| `CILIUM_LB_ENABLED` | `TRUST_MANAGER_ENABLED` |
| `CILIUM_GATEWAY_ENABLED` | `NFS_CSI_ENABLED` |
| `CERT_MANAGER_INSTALL_ENABLED` | `OPENEBS_ENABLED` |
| `CERT_MANAGER_SELFSIGNED_ENABLED` | `PROMETHEUS_ENABLED` |
| | `RELOADER_ENABLED` |

Base children are toggleable too: the first cluster pointed at this bundle
wanted `cilium-lb` + `cert-manager-install` and *not* the Gateway or the PKI
chain, so an always-on base would not have fit. A cluster's whole shape now
lives in its substitute block, and the overlay just lists what is available.

A substituted variable cannot remove a resource from a build — kustomize builds
the resource set first, substitution runs afterwards on its output. So the
toggle moves the child's **path** instead:

```
components/prometheus/switch/
├── true/    resources: [ ../../../../../prometheus ]   → the real base, unchanged
└── false/   resources: []                              → nothing
```

Base children switch the same way under `base/switch/<name>/`, except their
`true/` uses `components:` rather than `resources:` — those targets are
`kind: Component`, which kustomize refuses to accumulate as a resource.

```yaml
path: ./infra/platform/components/prometheus/switch/${PROMETHEUS_ENABLED:-true}
```

Disabled, the child Kustomization still exists and still reconciles — it just
applies nothing, and its own `prune: true` removes every object it previously
owned. That is a real uninstall.

It also still reports **Ready**, which is why `_ENABLED` and `_SUSPEND` differ
for dependents: disabling `cilium-gateway` leaves `prometheus` free to
reconcile (against nothing), whereas suspending it strands `prometheus` on
"dependency not ready" forever.

Verified locally: `switch/true` builds byte-identical output to building
`./infra/<app>` directly, `switch/false` builds zero objects, and
`flux build kustomization --dry-run` (the controller's own build path) exits 0
on the disabled directory. The pruning half is Flux's ordinary garbage
collection for an emptied Kustomization; it could not be exercised here without
a cluster, so watch the first flip.

### `<APP>_SUSPEND` — the freeze boolean

One per child, all eight, default `false`: `CILIUM_LB_SUSPEND`,
`CILIUM_GATEWAY_SUSPEND`, `CERT_MANAGER_INSTALL_SUSPEND`,
`CERT_MANAGER_SELFSIGNED_SUSPEND`, `TRUST_MANAGER_SUSPEND`, `NFS_CSI_SUSPEND`,
`OPENEBS_SUSPEND`, `PROMETHEUS_SUSPEND`.

This is the one place a bool works *directly*, and it is worth understanding
why: `spec.suspend` is a **boolean field**, so the bare `false` that
`${VAR:-false}` renders is exactly the right type. `postBuild.substitute` is
`map[string]string`, so the same bare `false` is rejected there. The field's
type decides, not the syntax.

Suspend **stops reconciliation and leaves deployed objects running**,
unmanaged. Use it for maintenance, not for "this cluster doesn't need X" —
`_ENABLED` is that switch. And **do not suspend a child that has dependents**
(`cilium-lb`, `cilium-gateway`, `cert-manager-install`): a suspended
Kustomization never reports Ready, so on a fresh cluster everything behind it
stalls on "dependency not ready" indefinitely. Those three carry the warning
inline.

### The component list — removes the child CR too

Delete a line from `overlays/<cluster>/kustomization.yaml` and the child leaves
the build; the bundle's own prune deletes the child CR, which in turn prunes
what it deployed. Same end state as `_ENABLED: "false"`, but it also removes
the Kustomization object, and it is an edit to *this* repo rather than the
cluster's. Prefer `_ENABLED` for per-cluster choices; prefer the list when a
component should not exist for any cluster using that overlay.

> A fourth option needs nothing from this bundle: point the consumer at
> `./infra/platform/base` and list `spec.components` on the consumer's own
> Kustomization. Flux supports it, and it puts the selection in the cluster
> repo as a list rather than a set of booleans.

## Variables

```bash
task get-variables    # every ${VAR:-default} in this folder
```

Bundle-level names (map onto differently-named base variables):

| Variable | Default | Feeds |
|---|---|---|
| `FLUX_SOURCE` | `flux-infra` | `sourceRef.name` of every child |
| `INFRA_DOMAIN` | *(required)* | `CILIUM_GATEWAY_DOMAIN`, `CERT_MANAGER_SELFSIGNED_DOMAIN`, prometheus `DOMAIN` |
| `INFRA_GATEWAY_NAME` | `cilium-gateway` | `CILIUM_GATEWAY_NAME`, prometheus `GATEWAY_NAME` |
| `INFRA_GATEWAY_NAMESPACE` | `default` | both of the above + `CERT_MANAGER_SELFSIGNED_CERT_NAMESPACE` |
| `INFRA_TLS_SECRET` | `wildcard-tls` | `CILIUM_GATEWAY_TLS_SECRET`, `CERT_MANAGER_SELFSIGNED_{CERT,SECRET}_NAME` |
| `PROMETHEUS_HOSTNAME` | `prometheus` | prometheus `HOSTNAME` (the base's name is too generic to expose) |
| `<APP>_ENABLED` | `true` | that component's path switch — `false` uninstalls it |
| `<COMPONENT>_SUSPEND` | `false` | that child's `spec.suspend` — freezes, does not uninstall |

Required variables have no upstream default, so they fall back to an
unmistakable sentinel (`set-INFRA_DOMAIN.invalid`, `0.0.0.0`,
`set-NFS_SERVER_FQDN.invalid`) rather than a null — see below.

Every other variable keeps its base name and its base default.

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
from the overlay with a **literal** value — a literal keeps its quotes:

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

## Migrating a cluster off the eight CRs

The bundle's children are named exactly like the CRs they replace
(`cilium-lb`, `cert-manager-install`, …), so they adopt the existing objects
instead of duplicating them. Apply the bundle **first**, confirm the children
are `Ready`, then remove the old files from the cluster repo.

Do not simply `kubectl delete kustomization <name>` — those CRs have
`prune: true` and deletion takes their workloads with them. Either let the
bundle adopt them by name as above, or set `prune: false` on a CR before
deleting it.
