# cicd/crossplane/profiles

A **profile** is a cluster shape: the set of Crossplane Configurations one kind
of cluster installs AND the crossplane core underneath them. Those two are not
separable here — the core decides which registry a Provider or Function is
locked to, and the two Configuration families disagree about that — so each
profile brings its own core.

One variable selects it, on the cluster's own Kustomization:

```yaml
postBuild:
  substitute:
    CROSSPLANE_PROFILE: machinery      # omit for cicd-platform
```

| Profile | Cluster |
|---|---|
| `cicd-platform` (default) | CI/CD cluster — pipeline-integration, storage-platform |
| `machinery` | vSphere / Proxmox / Harvester VM + image builder, plus an optional fleet-manager half |

Every profile has the same three roots:

```
<profile>/
├── install/           crossplane core, at the version and provider list this profile wants
├── configs/           the package CRs (+ preconditions, on machinery)
└── provider-configs/  the `in-cluster` ClusterProviderConfigs
```

On `machinery` all three are **generated** from the KCL catalog; only
`configs/preconditions.yaml` beside them is handwritten.

`spec.path` carries the variable, so the whole selection is one string:
`./cicd/crossplane/profiles/${CROSSPLANE_PROFILE:-cicd-platform}/configs`.

## Two package families — one per cluster, enforced by construction

| | Registry | Root |
|---|---|---|
| cicd-platform | `ghcr.io/stuttgart-things/crossplane/*` | `cicd-platform/configs` |
| machinery | `ghcr.io/stuttgart-things/crossplane-configurations/*` | `machinery/configs` |

They share package **names** (`harvester-vm`, `volume-claim`, `ansible-run`,
`cloud-config`) but are different lineages with unrelated version lines.
`stuttgart-things/argocd` records the `crossplane/*` one as the "old repo,
decommissioned", with entries re-added under `crossplane-configurations/*` as
their v2 replacements are pushed — so the cicd-platform profile is the one on
borrowed time, not this.

Both families on one cluster means two Configurations named `harvester-vm` from
different sources. Crossplane keys its lock on the source string, so that is a
duplicate node, and a duplicate node takes **every** package on the cluster to
`Healthy=False` at once — while `Installed` stays True and the pods keep
running, so nothing crashes and nothing restarts. Crossplane simply reconciles
no claim at all.

A cluster cannot express that: there is one `CROSSPLANE_PROFILE` and one set of
Kustomizations following it. That is the reason the profile is a variable rather
than a second component.

## The CR naming convention

**Providers and Configurations carry the name Crossplane itself derives from the
package path. Functions stay short.** That is the rule, it is a *fleet* rule
rather than a rule of this directory, and #506 is what happens when only one
repository follows it.

```
ghcr.io/stuttgart-things/crossplane-configurations/platform
  -> stuttgart-things-crossplane-configurations-platform
xpkg.upbound.io/upbound/provider-opentofu
  -> upbound-provider-opentofu
```

The derived name is the one the package manager would create for a package it
installs as somebody's `dependsOn`. Use it, and an explicit CR and a pulled one
are the **same** Lock node. Use a short name, and they are two nodes for one
source — which takes every package on the cluster to `Healthy=False` at once
while `Installed` stays True and the pods keep running
(crossplane-configurations#247).

Functions are the exception and it is not a free one: Compositions name a
function in `functionRef`, so renaming one breaks every Composition that uses
it. A function therefore keeps a short name and lives with a dependsOn-derived
twin beside it — which is safe only as long as the two differ in **source**.
Since catalog **0.8.0** that applies to all five: every short Function sits on
`xpkg.upbound.io` and every twin on `xpkg.crossplane.io`, the registry the
`dependsOn` entries name, under exactly the derived name — so a twin is the
dependsOn node rather than a third one, and all five twins are pinned instead
of floating.

The versions may match. machinery-kind5 runs `function-kcl` v0.12.2 on both
mirrors, same digest, both Healthy, because the names *and* the sources differ.
What must never match is the **source**, and 0.8.0 exists because it did:
`function-auto-ready`, `-go-templating` and `-environment-configs` were on
`xpkg.crossplane.io` next to their twins. On a kind cluster that never showed —
the play installs the functions **before** the Configurations, so the resolver
finds the short CR by source and creates no twin at all. This profile applies
the whole list in one pass, the twin appears first, and the short name then
lands on a source that already has one: on `machinery` (2026-09-22) the Lock
held `…/function-go-templating` twice and **all 51 packages** went
`Healthy=False`. Same list, different install order.

`function-kcl` additionally stays at v0.12.2 until the cicd-test4 incident
(catalog 0.5.0) is understood; "same digest = one node" is not what explains
it.

### Who still owes it

The catalog and this directory are consistent. The other two places that install
packages onto a machinery cluster have moved part of the way (2026-09-22):

| Where | CR names | since |
|---|---|---|
| `helm` `cicd/crossplane-providers.yaml.gotmpl`, `cicd/crossplane-config.yaml.gotmpl` | derived **with `derivedNames=true`**, short without it (the default) | helm#165 |
| `ansible` `kind_machinery` (both plays) | derived for the helmfile packages above and for `provider_packages`, on **fresh** clusters | ansible#1258 |
| ″ `machinery_packages` / `platform_packages` | still **short**: `cluster`, `platform`, `proxmoxvm`, `vspherevm`, `minio`, `harvester-vm`, `packer-build`, `packer-release`, `cluster-backup`, `scheduled-run`, `tofu-run`, `capability`, `argocd-cluster` | open |

Opt-in in helm because four consumers apply those helmfiles from `main`, with
no check in front of them (`ansible` `plays/kind-machinery-test.yaml`,
platform-engineering-showcase, `stuttgart-things` dev3-kind). A rename on a
live cluster is destructive either way: helm deletes the old CR, and a
Provider/Configuration takes its CRDs/XRDs and everything on them with it, or
both names coexist as a duplicate Lock node.

So the play sets `derivedNames=true` only after a preflight. Any
Provider/Configuration whose **source** is one of the renamed packages under
another name stops the run before anything is touched: "cluster predates the
rename — rebuild, or migrate by hand". machinery-kind4 and -kind5 predate it.
They get no package updates through the play until they are rebuilt (one
Backstage run). That stop is intended.

Verified by a Backstage `machinery-smoke` build with the new collection
(stuttgart-things#3141): 48/48 packages Healthy, identical to kind5 apart from
the five renamed CRs and the p&t twin at v0.10.9.

`crossplane-contrib-provider-helm`, `crossplane-contrib-provider-kubernetes`,
`valkiriaaquaticamendi-provider-proxmox-bpg`, `vshn-provider-minio` and
`upbound-provider-vault` are derived names on both sides. The play's *Install
Configuration packages* task resolves an existing CR **by source** before
applying, so its short-named entries adopt a long-named CR that is already
there.

That adoption only works in one direction: the play run over a Flux-built
cluster. It does not help the reverse, and because of the open row above even a
**freshly** play-built cluster is not one this profile can be layered over.

### Never layer this profile over an existing kind machinery cluster

A kind machinery cluster built by the play carries its root Configurations and
three providers under **short** names. machinery-kind5 (2026-09-22) has
`cluster`, `platform`, `proxmoxvm`, `vspherevm`, `minio`, `namespace`,
`volume-claim`, … next to `provider-opentofu`, `provider-kubeconfig` and
`provider-clusterbook`. This profile applies the same sources under their
derived names. Nothing on the Flux side resolves by source, so every one of
those becomes a second CR for a source that already has one — a duplicate Lock
node, and every package on the cluster goes `Healthy=False`.

This holds for a freshly play-built cluster too, as long as
`machinery_packages` / `platform_packages` use short names (see the table above).

Moving a kind cluster to this profile therefore means **rebuilding** it: a fresh
cluster, then this profile, then the play (if at all) on top. Renaming CRs in
place is not a migration path; see the next paragraph for why even a single
rename has to delete the old CR in the same step.

A rename in the helm repo is not a pure rename. The chart derives the
DeploymentRuntimeConfig name, the `serviceAccountTemplate` and the
ClusterRoleBinding subject from the provider's name, so renaming a provider that
has `rbac`, `env` or `resources` moves its pod identity — and the old Provider CR
has to go in the same step, or the rename *is* the duplicate it was meant to
remove.

`hack/check-crossplane-deps.py` holds the convention per profile in its `NAMING`
map (`machinery: "derived"`, `cicd-platform: "short"`) and applies a different
rule set to each. A new profile that is not in that map is silently unchecked.

## Why the package lists are so short

Everything reachable through another package's `dependsOn` is deliberately
absent. `ansible-run` (pulled by vspherevm and proxmoxvm), `volume-claim` and
`cloud-config` (pulled by harvester-vm), `flux-apps`, `remote-cluster`,
`rancher-cluster`, `vault-secrets`, `app-secret-profile`,
`management-plane`, `cni`, `flux-init`, `ip-reservation`, `vault-auth` and
`vault-pki-secrets` all arrive transitively. They appear in
`kubectl get configuration` under package-manager-derived names like
`stuttgart-things-crossplane-configurations-ansible-run` and are **expected** to
look extra.

Listing one explicitly as well puts the same OCI path under both a short CR name
and a `dependsOn`, which is the lock collision above
(crossplane-configurations#247 — all 20 packages on u26-kind3, 2026-08-12).

This is the opposite convention from `../components/configs`, which lists every
dependency and sets `skipDependencyResolution` on the one package that needs it.
Both are valid; do not mix them inside one file.
`hack/check-crossplane-deps.py` reads the published packages and enforces
whichever shape a file uses — it groups files by profile, so add any new profile
to its `PROFILES` map or it is silently unchecked.

`packer-build` (reached by `packer-release`) and `platform` (reached by
`cluster`) are the exception the derived names buy: both are listed **and**
pulled, and that is not a duplicate, because the CR the resolver would create
carries the name the CR here already has — one lock node, not two. The rule
that stays is the naming one, not "never name a reachable package".

The inverse case is `capability` and `argocd-cluster`. **Nothing** pulls them,
so they exist only where somebody installs them. On u26-kind3 somebody did, by
hand, each with a live XR — which is why the gap here stayed invisible until a
machinery cluster rebuilt from Git came up with neither XRD (u26-kindtest,
2026-09-19). A package that only exists because of a past `kubectl apply` is not
a fleet fact; being in the catalog is what makes it one.

## Source of truth for the pins

`stuttgart-things/kcl`,
[`crossplane/xplane-crossplane-catalog`](https://github.com/stuttgart-things/kcl/tree/main/crossplane/xplane-crossplane-catalog)
— the same catalog `ManagementPlane` reads through `spec.profile`. The list here
is rendered from it by `hack/gen-crossplane-profile.py` at a pinned module
version, and CI re-renders and compares.

It was not always. The catalog's own header names the three places it replaced,
and one of them is this directory: an older generation of the same list,
pointing at `ghcr.io/stuttgart-things/crossplane/*`. Maintaining a fourth copy
by hand is what let this bundle drift to cluster-backup v0.2.0 against the
fleet's v0.1.0, opentofu v1.1.7 against v1.1.6 and crossplane 2.4.0 against
2.3.3, while missing two providers, all five functions and three configurations.

To move a version, move the catalog. Read its comments first: several pins are
dependency floors or deliberate reverts, and at least one (`cluster`) must never
be lowered, because `kubectl apply` walks a Configuration backwards without
complaint.

Package identity and version are not all the catalog may own. A provider it
gives `env` or `resources` is rendered here as a `DeploymentRuntimeConfig` plus
a `runtimeConfigRef` on the Provider — the same two fields, and the same emitted
shape, as the play's chart, because a cluster built either way has to be the
same cluster. The generator names every field it renders and every field it
deliberately does not (`RENDERED` / `IGNORED`), and **aborts** on one it has
never heard of rather than dropping it: a catalog that grows past the generator
is the same drift as a hand-maintained copy, only harder to see. `clusterRole`
is the interesting "deliberately not" — the play binds it per provider, this
profile binds cluster-admin to the whole `system:serviceaccounts:` group in
`configs/preconditions.yaml`, and doing both would be one real grant and a
handful of decorative ones.

There is no `platform_enabled` split here, and that follows the catalog rather
than the play: `platform` and `cluster` are both in the one `machinery` list,
because being a management cluster is what that profile IS. A pure VM builder
would be a profile of its own — the catalog's `main.k` says as much ("a seed and
a full machinery cluster will not want the same package set").

## Why machinery has its own crossplane core

`crossplane-configurations` declares its Providers and Functions against
**`xpkg.crossplane.io`** — `provider-kubernetes` (>=v1.2.0), `provider-helm`
(>=v1.0.0), `function-kcl` (>=v0.12.0), `function-patch-and-transform`
(>=v0.10.6). `../components/install` and `../components/functions` install those
same packages from **`xpkg.upbound.io`**, which is what the `crossplane/*`
family declares. Crossplane keys its lock on the source string, so on a cluster
carrying both, every machinery Configuration reports the package it wants as a
missing dependency while the other spelling sits there installed and no claim
reconciles. CI caught it on eight of the nine packages the first time these
profiles ran.

The fix is not to install them at the other spelling — it is to **not install
them explicitly at all**. Every Provider and Function a machinery Configuration
needs is already in its `dependsOn`, so Crossplane installs it at the registry
the package itself names. `stuttgart-things/argocd` takes the same position for
`provider-kubernetes` in `cicd/crossplane/providers/values.yaml`.

`machinery/install/` is therefore a build root that composes
`../../../components/install` — same chart, version, namespace and
HelmRepositories — and replaces only the provider list, keeping the single entry
that never conflicted:

| Provider | cicd-platform | machinery |
|---|---|---|
| `provider-helm` | `xpkg.upbound.io` | via `dependsOn` (platform declares `xpkg.crossplane.io`) |
| `provider-kubernetes` | `xpkg.upbound.io` | via `dependsOn` (`xpkg.crossplane.io`) |
| `provider-opentofu` | `xpkg.upbound.io` | `xpkg.upbound.io` — kept |

`provider-opentofu` stays because it is the one entry CI never flagged: tofu-run
either declares this exact upbound string or does not declare it at all, and
installing it here is right either way — in the first case the node is identical,
in the second nothing else would install it.

It composes `../../../components/install` rather than the cicd-platform install
root because that one pulls `components/functions` in alongside, and a machinery
cluster wants no functions component for the same registry reason.

(An earlier version of this file guessed the gap was a missing
`function-environment-configs`. That was wrong: a Function a Configuration
declares is pulled automatically, so absence is never the problem — only a
second, differently-spelled copy is.)

## What a profile is NOT allowed to say

A profile says what a cluster **is**. Where a VM gets placed, and what it
authenticates to a hypervisor with, is not a fleet fact — it is a cluster fact,
and it arrives through a `Capability` XR instead. The rule is stated at its
source in `stuttgart-things`,
`crossplane/xrs/capability/labda/seed-labda-1.yaml`:

> das machinery-Profil enthält genau DREI ProviderConfigs, und alle drei sind
> `in-cluster` (helm, kubernetes, opentofu) … es enthält keine
> Hypervisor-Credentials und keine Platzierung.

So `configs/` here holds packages and nothing else. An earlier version of it
shipped `vsphere-vm-defaults` and `tofu-run-defaults`, vendored from the ansible
play's raw examples, and that was wrong in the most expensive direction: the
vsphere one carries **LabUL** placement, while LabDA is where new vSphere work
goes. The reference machinery cluster in LabDA (`seed-labda-1`) carries no such
object at all, so today an XR asking for `spec.environmentConfig: default`
matches nothing and fails loudly. Adding a `default`-labelled config turns that
into a match — against another lab's datacenter. "Fails visibly" would have
become "runs and builds in the wrong place".

What that cluster does carry is three EnvironmentConfigs, all emitted by the
capability charts and all suffixed for their lab: `vspherevm-labda`,
`proxmoxvm-labda`, `ansible-run-labda`. Nothing here competes with those.

Two EnvironmentConfigs do stay, in `machinery/configs/preconditions.yaml`
beside the generated list: `flux-defaults` and `flux-apps-defaults` carry
reconcile intervals, a chart version and a `sourceRef`, and name no place and no
secret. Both are REQUIRED by their Compositions and composed by nothing, which
is the same category as the provider RBAC next to them.

The capability charts themselves, the per-lab credentials, the sops-git wiring
and the provider-kubeconfig-vault releases all still live in
`stuttgart-things/crossplane/platform/*` and are applied by the ansible play.
Installing a package here provisions nothing on its own.

## Related

- Package pins: [`stuttgart-things/ansible` — `collections/container/kind_machinery.yaml`](https://github.com/stuttgart-things/ansible/blob/main/collections/container/kind_machinery.yaml)
- Capability charts: [`stuttgart-things/stuttgart-things` — `crossplane/platform`](https://github.com/stuttgart-things/stuttgart-things/tree/main/crossplane/platform)
- ArgoCD equivalent: [`stuttgart-things/argocd` — `cicd/crossplane`](https://github.com/stuttgart-things/argocd/tree/main/cicd/crossplane)
