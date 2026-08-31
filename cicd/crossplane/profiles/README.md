# cicd/crossplane/profiles

A **profile** is a cluster shape: the set of Crossplane Configurations one kind
of cluster installs — the Configurations it runs AND the crossplane core
underneath them. Those two are not separable here: the core decides which
registry a Provider or Function is locked to, and the two Configuration families
disagree about that (see below), so each profile brings its own core.

| Profile | Path | Cluster |
|---|---|---|
| cicd-platform | `../configs` (wraps `../components/configs`) | CI/CD cluster — pipeline-integration, storage-platform |
| machinery-install | `./machinery-install` | crossplane core for a machinery cluster |
| machinery | `./machinery` | vSphere / Proxmox / Harvester VM + image builder |
| machinery-platform | `./machinery-platform` | the fleet-manager half, opt-in on top of `machinery` |

This mirrors the split `stuttgart-things/argocd` describes in
`cicd/crossplane/configs/values.yaml` ("when there's a real second profile …
split into `cicd/crossplane/profiles/<name>/`").

## Two package families — do not mix them on one cluster

| | Registry | Installed by |
|---|---|---|
| cicd-platform | `ghcr.io/stuttgart-things/crossplane/*` | `components/configs` |
| machinery | `ghcr.io/stuttgart-things/crossplane-configurations/*` | these profiles |

They share package **names** (`harvester-vm`, `volume-claim`, `ansible-run`,
`cloud-config`) but are different lineages with unrelated version lines.
`stuttgart-things/argocd` records the `crossplane/*` one as the "old repo,
decommissioned", with entries re-added under `crossplane-configurations/*` as
their v2 replacements are pushed — so the cicd-platform profile is the one on
borrowed time, not this.

Applying `../configs` **and** a machinery profile to the same cluster creates two
Configurations named `harvester-vm` from different sources. Crossplane keys its
lock on the source string, so that is a duplicate node, and a duplicate node
takes every package on the cluster to `Healthy=False` at once. Pick one profile
per cluster.

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

This is the opposite convention from `components/configs`, which lists every
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
pins are dependency floors or deliberate reverts, and at least one
(`cluster`) must never be lowered, because `kubectl apply` walks a Configuration
backwards without complaint.

`machinery-platform` corresponds to that play's `platform_enabled` flag
(default true). Kustomize has no conditional, so the toggle is the directory:
apply `machinery` alone for a pure VM builder, or both.

## Why machinery has its own crossplane core

`crossplane-configurations` declares its Providers and Functions against
**`xpkg.crossplane.io`** — `provider-kubernetes` (>=v1.2.0), `provider-helm`
(>=v1.0.0), `function-kcl` (>=v0.12.0), `function-patch-and-transform`
(>=v0.10.6). `components/install` and `components/functions` install those same
packages from **`xpkg.upbound.io`**, which is what the `crossplane/*` family
declares. Crossplane keys its lock on the source string, so on a cluster
carrying both, every machinery Configuration reports the package it wants as a
missing dependency while the other spelling sits there installed and no claim
reconciles. CI caught it on eight of the nine packages the first time these
profiles ran.

The fix is not to install them at the other spelling — it is to **not install
them explicitly at all**. Every Provider and Function a machinery Configuration
needs is already in its `dependsOn`, so Crossplane installs it at the registry
the package itself names. `stuttgart-things/argocd` takes the same position for
`provider-kubernetes` in `cicd/crossplane/providers/values.yaml`.

`machinery-install/` is therefore a build root that composes
`../components/install` — same chart, version, namespace and HelmRepositories —
and replaces only the provider list, keeping the single entry that never
conflicted:

| Provider | cicd-platform | machinery |
|---|---|---|
| `provider-helm` | `xpkg.upbound.io` | via `dependsOn` (platform declares `xpkg.crossplane.io`) |
| `provider-kubernetes` | `xpkg.upbound.io` | via `dependsOn` (`xpkg.crossplane.io`) |
| `provider-opentofu` | `xpkg.upbound.io` | `xpkg.upbound.io` — kept |

`provider-opentofu` stays because it is the one entry CI never flagged: tofu-run
either declares this exact upbound string or does not declare it at all, and
installing it here is right either way — in the first case the node is identical,
in the second nothing else would install it.

It composes `../components/install` rather than `../../crossplane` because that
root pulls `components/functions` in alongside, and a machinery cluster wants no
functions component for the same registry reason.

(An earlier version of this file guessed the gap was a missing
`function-environment-configs`. That was wrong: a Function a Configuration
declares is pulled automatically, so absence is never the problem — only a
second, differently-spelled copy is.)

## Consuming a profile

No bundle wires these: `cicd/platform` is the CI/CD bundle and must not install
machinery packages. Create the Kustomizations directly.

```yaml
---
# Crossplane core. Replaces the `crossplane` Kustomization on this cluster --
# do not run both, they manage the same HelmRelease.
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-machinery-install
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 20m
  prune: true
  # wait: true is what lets the Configuration Kustomizations below rely on
  # dependsOn: a Configuration CR dry-runs against an API that has to know the
  # kind already, and this one is Ready only once the chart is installed.
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/profiles/machinery-install
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_VERSION: "2.4.0"
      CROSSPLANE_OPENTOFU_PROVIDER_VERSION: v1.1.7
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-machinery
  namespace: flux-system
spec:
  dependsOn:
    - name: crossplane-machinery-install
  interval: 1h
  retryInterval: 1m
  # A Configuration is not installed when its resource exists -- the package
  # manager pulls each image, resolves its dependencies and only then marks it
  # Healthy. Eight of them plus their transitive deps take minutes on a cold
  # cluster, and a shorter timeout fails the Kustomization while the packages
  # are still arriving correctly.
  timeout: 20m
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/profiles/machinery
  postBuild:
    substitute:
      CROSSPLANE_MACHINERY_VSPHEREVM_VERSION: v0.9.2
      CROSSPLANE_MACHINERY_PROXMOXVM_VERSION: v0.13.0
      CROSSPLANE_MACHINERY_PACKER_RELEASE_VERSION: v0.4.2
      CROSSPLANE_MACHINERY_CLUSTER_BACKUP_VERSION: v0.2.0
      CROSSPLANE_MACHINERY_SCHEDULED_RUN_VERSION: v0.1.1
      CROSSPLANE_MACHINERY_TOFU_RUN_VERSION: v0.1.0
      CROSSPLANE_MACHINERY_HARVESTER_VM_VERSION: v0.1.9
---
# Fleet-manager half. Omit for a pure VM builder.
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-machinery-platform
  namespace: flux-system
spec:
  dependsOn:
    - name: crossplane-machinery
  interval: 1h
  retryInterval: 1m
  timeout: 20m
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/profiles/machinery-platform
  postBuild:
    substitute:
      CROSSPLANE_MACHINERY_CLUSTER_VERSION: v0.6.1
      CROSSPLANE_MACHINERY_PROVIDER_CLUSTERBOOK_VERSION: v0.4.2
```

Substituted defaults written here are a **second copy** of the ones in
`configs.yaml` and they win — a child Kustomization cannot inherit a default,
because an empty substitute value renders as YAML null and the API server
rejects the CR. Bump both together.

The capability charts, EnvironmentConfigs and RBAC that make these
Configurations *usable* (as opposed to installed) still live in
`stuttgart-things/crossplane/platform/*` and are applied by the ansible play.
Installing a package here does not provision anything on its own.

## Related

- Package pins: [`stuttgart-things/ansible` — `collections/container/kind_machinery.yaml`](https://github.com/stuttgart-things/ansible/blob/main/collections/container/kind_machinery.yaml)
- Capability charts: [`stuttgart-things/stuttgart-things` — `crossplane/platform`](https://github.com/stuttgart-things/stuttgart-things/tree/main/crossplane/platform)
- ArgoCD equivalent: [`stuttgart-things/argocd` — `cicd/crossplane`](https://github.com/stuttgart-things/argocd/tree/main/cicd/crossplane)
