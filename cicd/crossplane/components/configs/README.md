# crossplane/components/configs

Deploys Crossplane `Configuration` packages from the stuttgart-things registry.

## How this is wired (do NOT add it to the root kustomization)

This component is deliberately absent from `cicd/crossplane/kustomization.yaml`,
and that is not an oversight to be fixed. `Configuration` is a CRD that the
crossplane chart in `components/install` installs. Applied in the same pass as
the chart, the CRs dry-run against an API that does not know them yet:

```
Configuration/cloud-config dry-run failed: no matches for kind
"Configuration" in version "pkg.crossplane.io/v1"
```

Flux aborts the **entire** apply on that — so the HelmRelease is never created
either, the CRD never appears, and every retry fails identically. Witnessed on
cicd-test1, 2026-08-28: `crossplane-system` existed and nothing else did.

So this component is composed by a build root of its own, `cicd/crossplane/configs/`,
which a second Flux Kustomization applies with `dependsOn` on the first. Both
Kustomizations live in `cicd/platform/components/crossplane/ks-crossplane.yaml`:

| Kustomization | `spec.path` | Installs |
|---|---|---|
| `crossplane` | `./cicd/crossplane` | controller + functions (`components/install`, `components/functions`) |
| `crossplane-configs` | `./cicd/crossplane/configs` | this component |

Point the Kustomization at **`./cicd/crossplane/configs`**, not at this directory.
`kustomize build` does render `components/configs` directly (v5.5.0 emits all six
Configurations from it), so this is a convention, not a hard error — but the
wrapper is the declared entry point, it is what `hack/check-passthrough-defaults.py`
resolves `spec.path` against, and pointing elsewhere silently opts out of that check.

## Consuming it

The bundle already wires this. Point a Kustomization here directly only when
running this component outside the `cicd-platform` bundle:

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: crossplane-configs
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  # NOT 5m. A Configuration is not installed when its resource exists -- the
  # package manager pulls each image, resolves its dependencies and only then
  # marks it Healthy. Six of them on a cold cluster take minutes, and a shorter
  # timeout marks the Kustomization failed while the packages are still
  # arriving correctly.
  timeout: 20m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/crossplane/configs
  prune: true
  wait: true
  dependsOn:
    - name: crossplane
  postBuild:
    substitute:
      CROSSPLANE_CONFIG_CLOUD_CONFIG_VERSION: v0.5.1
      CROSSPLANE_CONFIG_VOLUME_CLAIM_VERSION: v0.1.1
      CROSSPLANE_CONFIG_STORAGE_PLATFORM_VERSION: v0.6.0
      CROSSPLANE_CONFIG_ANSIBLE_RUN_VERSION: v12.0.0
      CROSSPLANE_CONFIG_PIPELINE_INTEGRATION_VERSION: v0.1.2
      CROSSPLANE_CONFIG_HARVESTER_VM_VERSION: v0.3.3
```

Those defaults are a **second copy** of the ones in `configs.yaml`, and the copy
wins — a child Kustomization cannot inherit a default, because an empty
substitute value renders as YAML null and the API server rejects the CR. Bump
both in the same PR; `hack/check-passthrough-defaults.py` enforces it.

## Resources

| Resource | Package | Purpose |
|---|---|---|
| `cloud-config` | `crossplane/cloud-config` | cloud-init Secret rendering |
| `volume-claim` | `crossplane/volume-claim` | root-disk PVC composition |
| `storage-platform` | `crossplane/storage-platform` | storage platform provisioning |
| `ansible-run` | `crossplane/ansible-run` | Ansible playbook execution |
| `pipeline-integration` | `crossplane/pipeline-integration` | CI/CD pipeline integration |
| `harvester-vm` | `crossplane/harvester-vm` | Harvester / KubeVirt VM provisioning |

All six are on `ghcr.io/stuttgart-things/crossplane/*`. That is a **different
package family** from the `ghcr.io/stuttgart-things/crossplane-configurations/*`
one used elsewhere in the org — see the note at the top of `configs.yaml` before
changing any of them.

## Dependencies

- **`crossplane`** — the controller must be running, and its CRDs must exist,
  before any CR here can even be dry-run (see above). Its `wait: true` is what
  makes `dependsOn` sufficient.
- The composition **Functions** come from the same `crossplane` Kustomization,
  so they are in the lock before any Configuration resolves — which is why only
  the Configurations race each other, and why `skipDependencyResolution` in
  `configs.yaml` is scoped to Configuration → Configuration edges only.
