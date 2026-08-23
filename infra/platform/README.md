# stuttgart-things/flux/infra/platform

A **bundle**: one Flux `Kustomization` stands up a cluster's whole infra layer.

Nothing here is a raw manifest — every `ks-*.yaml` is a Flux `Kustomization` CR
pointing back at an existing base in this repo. The consumer's
`postBuild.substitute` fills their `${VAR:-default}` values one hop, and each
child then renders its own base.

## Layout

```
infra/platform/
├── base/                      always-on core
│   ├── ks-cilium-lb.yaml               → ./infra/cilium/components/lb
│   ├── ks-cilium-gateway.yaml          → ./infra/cilium/components/gateway   (dependsOn cilium-lb)
│   ├── ks-cert-manager-install.yaml    → ./infra/cert-manager/components/install
│   └── ks-cert-manager-selfsigned.yaml → ./infra/cert-manager/components/selfsigned (dependsOn cert-manager-install)
├── components/                opt-in, one kustomize Component each
│   ├── trust-manager/    → ./infra/trust-manager   (dependsOn cert-manager-install — needs base)
│   ├── nfs-csi/          → ./infra/nfs-csi         (standalone)
│   ├── openebs/          → ./infra/openebs         (standalone)
│   └── prometheus/       → ./infra/prometheus      (dependsOn cilium-gateway — needs base)
└── overlays/
    └── infra-sthings/    base + all four components
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

Two switches, with different semantics. Pick by whether you want the objects
**gone** or merely **frozen**.

| | `*_SUSPEND: "true"` | remove the component line from the overlay |
|---|---|---|
| Where | consumer's `substitute` block (cluster repo) | `overlays/<cluster>/kustomization.yaml` (this repo) |
| Already-deployed objects | **stay**, frozen — drift no longer corrected | **deleted** (pruned) |
| Never-deployed (fresh cluster) | never installed | never installed |
| Reversible by | flipping the value back | re-adding the line |
| Blocks dependents | yes — a suspended child never reports Ready | no |

### `*_SUSPEND` — the boolean

```yaml
postBuild:
  substitute:
    PROMETHEUS_SUSPEND: "true"     # note the quotes: substitute is map[string]string
    OPENEBS_SUSPEND: "true"
```

One per child: `CILIUM_LB_SUSPEND`, `CILIUM_GATEWAY_SUSPEND`,
`CERT_MANAGER_INSTALL_SUSPEND`, `CERT_MANAGER_SELFSIGNED_SUSPEND`,
`TRUST_MANAGER_SUSPEND`, `NFS_CSI_SUSPEND`, `OPENEBS_SUSPEND`,
`PROMETHEUS_SUSPEND`. All default `false`.

This is the one place a bool *does* work, and it is worth understanding why,
because it is the exact inverse of the rule in the section below: `spec.suspend`
is a **boolean field**, so the bare `false` that `${VAR:-false}` renders is
precisely the right type. `postBuild.substitute` is `map[string]string`, so the
same bare `false` is rejected there. The field's type decides, not the syntax.

**It suspends, it does not uninstall.** On a cluster that never ran the
component that is indistinguishable from "off" — which is the common fleet case
("this cluster has no NFS server"). On a cluster where it already reconciled,
the workloads keep running, unmanaged.

**Do not suspend a child that has dependents** — `cilium-lb`,
`cilium-gateway`, `cert-manager-install`. A suspended Kustomization never
reports Ready, so on a fresh cluster everything behind it stalls on "dependency
not ready" indefinitely. Each of those files carries the warning inline.

### The component list — the switch that prunes

Delete a line from `overlays/<cluster>/kustomization.yaml` and the child
Kustomization leaves the build; the bundle's own `prune` deletes the child CR,
which in turn prunes everything it deployed. Add it back with one line.

### Why a substituted boolean cannot do the pruning one

`kustomize build` runs first and produces the full resource set; Flux's
variable substitution runs **after**, on that output. A variable can therefore
change what a resource *says*, never whether it *exists*. Conditional inclusion
has to happen at build time — which is what the component list is.

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
| `<COMPONENT>_SUSPEND` | `false` | that child's `spec.suspend` — see [Turning components off](#turning-components-off) |

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
