# stuttgart-things/flux/cicd/crossplane

Crossplane, plus **one profile's** worth of Configurations.

A profile is a cluster shape: which Configuration family this cluster installs
*and* which crossplane core goes underneath it. Those two are not separable —
the core decides which registry a Provider or Function is locked to, and the
families disagree about that — so each profile brings both.

| `CROSSPLANE_PROFILE` | Cluster | Packages |
|---|---|---|
| `cicd-platform` (default) | CI/CD cluster — pipeline-integration, storage-platform | `ghcr.io/stuttgart-things/crossplane/*`, listed here |
| `machinery` | a **management** cluster: VM + image builder and fleet manager | `ghcr.io/stuttgart-things/crossplane-configurations/*`, **generated from the KCL catalog** |

```
cicd/crossplane/
├── components/            reusable pieces, composed BY the profiles
│   ├── install/           the chart + namespace + HelmRepositories
│   ├── functions/         composition functions (cicd-platform only)
│   ├── configs/           the crossplane/* Configuration packages
│   └── provider-configs/  one `in-cluster` ClusterProviderConfig per provider
└── profiles/
    ├── cicd-platform/     install/  configs/  provider-configs/
    └── machinery/         install/  configs/  provider-configs/   (generated)
```

Every profile directory has the same three roots, and the bundle's
Kustomizations point at them by name:

| Kustomization | `spec.path` | `dependsOn` |
|---|---|---|
| `crossplane` | `…/profiles/${CROSSPLANE_PROFILE}/install` | — |
| `crossplane-configs` | `…/profiles/${CROSSPLANE_PROFILE}/configs` | `crossplane` |
| `crossplane-provider-configs` | `…/profiles/${CROSSPLANE_PROFILE}/provider-configs` | `crossplane-configs` |

Three, on every profile. See [`profiles/README.md`](profiles/README.md).

## The machinery profile is generated

Its package list is **not written here**. `ManagementPlane` builds a management
cluster from `stuttgart-things/kcl`,
[`crossplane/xplane-crossplane-catalog`](https://github.com/stuttgart-things/kcl/tree/main/crossplane/xplane-crossplane-catalog),
and that catalog's own header names this directory as one of the three stale
copies it replaced. So the list is rendered from it, at a pinned version:

```bash
python3 hack/gen-crossplane-profile.py           # write
python3 hack/gen-crossplane-profile.py --check   # CI: verify, fail on drift
```

A cluster built by Flux and one built by Crossplane then install the same set.
To move a version, move the catalog — an edit to a generated file is reverted by
the next run and fails CI in between.

## Consuming it

Through the bundle — this is the normal path:

```yaml
spec:
  path: ./cicd/platform/root
  components:
    - ../components/crossplane
  postBuild:
    substitute:
      CROSSPLANE_PROFILE: machinery         # omit for cicd-platform
```

Standalone, without the bundle, is still one Kustomization per row of the table
above. The split is not optional:

```bash
kubectl apply -f - <<EOF
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  url: https://github.com/stuttgart-things/flux.git
  ref:
    branch: main
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 20m
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/profiles/cicd-platform/install
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: crossplane-system
      CROSSPLANE_VERSION: "2.4.0"
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-configs
  namespace: flux-system
spec:
  dependsOn:
    - name: crossplane
  interval: 1h
  retryInterval: 1m
  timeout: 20m
  prune: true
  wait: true
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/profiles/cicd-platform/configs
EOF
```

## Why the Configurations need a Kustomization of their own

`Configuration` is a CRD the chart installs, so applying the CRs in the same
pass dry-runs them against an API that does not know the kind yet:

```
Configuration/cloud-config dry-run failed: no matches for kind
"Configuration" in version "pkg.crossplane.io/v1"
```

Flux aborts the whole apply on that — the HelmRelease included — so crossplane
is never installed, the CRD never appears, and every retry fails identically.
The deadlock is silent: the namespace exists and nothing else does.
`dependsOn` plus the install root's `wait: true` is what breaks it.

The **ClusterProviderConfigs** need a third one for the same reason, one step
later: each is an instance of a CRD that a *provider* registers, and a provider
is Healthy only once its package has been pulled and its controller has started.
On the machinery profile no provider but opentofu is installed explicitly at
all, so that moment is after the Configurations resolve — which is why it
depends on `crossplane-configs` rather than on `crossplane`.

The Functions do **not** need this: `components/functions` ships them as
`customresources` inside a HelmRelease, so nothing types them at apply time.

## Adding a profile

Create `profiles/<name>/` with `install/`, `configs/` and `provider-configs/`
roots, thread any pins it needs in
`cicd/platform/components/crossplane/ks-crossplane.yaml`, and add the file list
to `PROFILES` in `hack/check-crossplane-deps.py` plus its CR-naming convention
to `NAMING` beside it — a profile in neither map is silently unchecked, and one
checked under the wrong convention is worse than unchecked.

Nothing else changes. `hack/check-passthrough-defaults.py` globs the substituted
path segment, so a new profile's pins are compared against the bundle's copies
from the first commit.
