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

Every profile has the same three roots, and `machinery` adds two more:

```
<profile>/
├── install/                    crossplane core + the providers THIS profile installs
├── configs/                    the Configuration packages (+ their EnvironmentConfigs)
├── provider-configs/           the `in-cluster` ClusterProviderConfigs
├── platform/                   optional: the fleet-manager half
└── platform-provider-configs/  optional: the helm ClusterProviderConfig
```

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

## Why the package lists are so short

Everything reachable through another package's `dependsOn` is deliberately
absent. `ansible-run` (pulled by vspherevm and proxmoxvm), `volume-claim` and
`cloud-config` (pulled by harvester-vm), `flux-apps`, `remote-cluster`,
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

Two packages the ansible play pins are deliberately **not** listed here for the
same reason: `packer-build` (reached by `packer-release`) and `platform`
(reached by `cluster`). The play can pin both because it applies packages in a
waited sequence, where the dependency is already in the lock; a Kustomization
applies in one pass and has no such ordering, so listing them makes each a
sibling of its own dependent. They resolve to the newest tag satisfying their
floor.

## Source of truth for the pins

`stuttgart-things/ansible`, `collections/container/kind_machinery.yaml` —
`machinery_packages` and `platform_packages`, reconciled against the reference
machinery cluster kind1. Read its comments before changing a version: several
pins are dependency floors or deliberate reverts, and at least one (`cluster`)
must never be lowered, because `kubectl apply` walks a Configuration backwards
without complaint.

`machinery/platform/` corresponds to that play's `platform_enabled` flag
(default true). Kustomize has no conditional, so the toggle is the **component**:
select `crossplane` alone for a pure VM builder, or `crossplane` plus
`crossplane-platform`.

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

The fleet-manager half keeps two, and they pass the same test:
`machinery/platform/environmentconfigs.yaml` holds `flux-defaults` and
`flux-apps-defaults`, which carry reconcile intervals, a chart version and a
`sourceRef`, and name no place and no secret.

The capability charts themselves, the per-lab credentials, the sops-git wiring
and the provider-kubeconfig-vault releases all still live in
`stuttgart-things/crossplane/platform/*` and are applied by the ansible play.
Installing a package here provisions nothing on its own.

## Related

- Package pins: [`stuttgart-things/ansible` — `collections/container/kind_machinery.yaml`](https://github.com/stuttgart-things/ansible/blob/main/collections/container/kind_machinery.yaml)
- Capability charts: [`stuttgart-things/stuttgart-things` — `crossplane/platform`](https://github.com/stuttgart-things/stuttgart-things/tree/main/crossplane/platform)
- ArgoCD equivalent: [`stuttgart-things/argocd` — `cicd/crossplane`](https://github.com/stuttgart-things/argocd/tree/main/cicd/crossplane)
