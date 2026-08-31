# cicd/crossplane/profiles

A **profile** is a cluster shape: the set of Crossplane Configurations one kind
of cluster installs. `components/install` and `components/functions` are shared
by every profile; only the Configuration set differs.

| Profile | Path | Cluster |
|---|---|---|
| cicd-platform | `../configs` (wraps `../components/configs`) | CI/CD cluster — pipeline-integration, storage-platform |
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

## Blocker — a machinery cluster needs its own crossplane core

These profiles ship **Configurations only**, and they cannot yet be paired with
`components/install` + `components/functions`. CI proved why on the first run:

`crossplane-configurations` declares its Providers and Functions against
**`xpkg.crossplane.io`** — `provider-kubernetes` (>=v1.2.0), `provider-helm`
(>=v1.0.0), `function-kcl` (>=v0.12.0), `function-patch-and-transform`
(>=v0.10.6). `components/install` and `components/functions` install those same
packages from **`xpkg.upbound.io`**, because that is what the `crossplane/*`
family declares. Crossplane keys its lock on the source string, so on a cluster
carrying both, every machinery Configuration reports the package it wants as a
missing dependency while the other spelling sits there installed. Eight of the
nine packages here hit it.

The fix is not to install them at the other spelling — it is to **not install
them explicitly at all**. Every Provider and Function a machinery Configuration
needs arrives through its own `dependsOn`, at the registry it names.
`stuttgart-things/argocd` takes exactly this position for `provider-kubernetes`
in `cicd/crossplane/providers/values.yaml`.

So a machinery cluster needs crossplane core **without** the `provider.packages`
list, and no functions component. `components/install` hardcodes that list and
is shared with cicd-platform, so it cannot simply be reused. Until a machinery
install variant exists, these profiles are **not deployable as they stand** —
the Configuration set and its pins are correct and verified, the core underneath
it is not yet there.

(An earlier version of this file guessed the gap was a missing
`function-environment-configs`. That was wrong: a Function a Configuration
declares is pulled automatically, so absence is never the problem — only a
second, differently-spelled copy is.)

## Consuming a profile

No bundle wires these: `cicd/platform` is the CI/CD bundle and must not install
machinery packages. Create the Kustomizations directly.

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-machinery
  namespace: flux-system
spec:
  dependsOn:
    - name: crossplane          # its wait: true is what guarantees the CRDs exist
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
