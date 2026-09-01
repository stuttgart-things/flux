# stuttgart-things/flux/cicd/crossplane

Crossplane, plus **one profile's** worth of Configurations.

A profile is a cluster shape: which Configuration family this cluster installs
*and* which crossplane core goes underneath it. Those two are not separable —
the core decides which registry a Provider or Function is locked to, and the
families disagree about that — so each profile brings both.

| `CROSSPLANE_PROFILE` | Cluster | Packages |
|---|---|---|
| `cicd-platform` (default) | CI/CD cluster — pipeline-integration, storage-platform | `ghcr.io/stuttgart-things/crossplane/*` |
| `machinery` | vSphere / Proxmox / Harvester VM + image builder | `ghcr.io/stuttgart-things/crossplane-configurations/*` |

```
cicd/crossplane/
├── components/            reusable pieces, composed BY the profiles
│   ├── install/           the chart + namespace + HelmRepositories
│   ├── functions/         composition functions (cicd-platform only)
│   ├── configs/           the crossplane/* Configuration packages
│   └── provider-configs/  one `in-cluster` ClusterProviderConfig per provider
└── profiles/
    ├── cicd-platform/     install/  configs/  provider-configs/
    └── machinery/         install/  configs/  provider-configs/
                           platform/  platform-provider-configs/
```

Every profile directory has the same three roots, and the bundle's
Kustomizations point at them by name:

| Kustomization | `spec.path` | `dependsOn` |
|---|---|---|
| `crossplane` | `…/profiles/${CROSSPLANE_PROFILE}/install` | — |
| `crossplane-configs` | `…/profiles/${CROSSPLANE_PROFILE}/configs` | `crossplane` |
| `crossplane-provider-configs` | `…/profiles/${CROSSPLANE_PROFILE}/provider-configs` | `crossplane-configs` |
| `crossplane-platform-configs` | `…/profiles/${CROSSPLANE_PROFILE}/platform` | `crossplane-configs` |
| `crossplane-platform-provider-configs` | `…/profiles/${CROSSPLANE_PROFILE}/platform-provider-configs` | `crossplane-platform-configs` |

The last two come from a separate, opt-in component
(`cicd/platform/components/crossplane-platform`) and exist only on the
`machinery` profile. See [`profiles/README.md`](profiles/README.md).

## Consuming it

Through the bundle — this is the normal path:

```yaml
spec:
  path: ./cicd/platform/root
  components:
    - ../components/crossplane
    # - ../components/crossplane-platform   # machinery profile only
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
roots, thread its pins in `cicd/platform/components/crossplane/ks-crossplane.yaml`
(both families already live in one substitute block; a third adds no names that
collide), and add the file list to `PROFILES` in `hack/check-crossplane-deps.py`
— a profile not in that map is silently unchecked for lock collisions.

Nothing else changes. `hack/check-passthrough-defaults.py` globs the substituted
path segment, so a new profile's pins are compared against the bundle's copies
from the first commit.
