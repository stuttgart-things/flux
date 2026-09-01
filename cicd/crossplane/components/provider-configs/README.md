# cicd/crossplane/components/provider-configs

One `ClusterProviderConfig` named `in-cluster` per provider, all targeting the
cluster Crossplane runs in. No secrets: `InjectedIdentity` for helm and
kubernetes, an in-cluster tofu state backend for opentofu.

`in-cluster` is the name every stuttgart-things Composition and
EnvironmentConfig references. A missing one is not a startup error -- the
package installs, the XRD appears, and the first XR then loops in observe with

```
cannot get provider config: ClusterProviderConfig "in-cluster" not found
```

## One component per provider, on purpose

A `ClusterProviderConfig` is an instance of a CRD its provider registers, so it
can only be applied where that provider is installed. The profiles do not agree
about that:

| Provider | cicd-platform | machinery | machinery + platform |
|---|---|---|---|
| kubernetes | installed by the chart | via every Configuration's `dependsOn` | ✓ |
| opentofu | installed by the chart | installed by `profiles/machinery-install` | ✓ |
| helm | installed by the chart | **nowhere** | via `cni` / `flux-init` / `platform` |

Not one package in the `machinery` profile declares `provider-helm`; only the
fleet-manager half does. Shipping all three to a pure VM builder would leave a
Kustomization retrying against a kind that never registers, which reads like a
slow reconcile rather than a mistake.

## Wiring

Nothing points at this directory. Each PROFILE composes the ones it can carry,
in a build root of its own, and the bundle's Kustomization names that root:

```yaml
# cicd/crossplane/profiles/machinery/provider-configs/kustomization.yaml
components:
  - ../../../components/provider-configs/kubernetes
  - ../../../components/provider-configs/opentofu
```

```yaml
# cicd/platform/components/crossplane/ks-crossplane.yaml
spec:
  dependsOn:
    - name: crossplane-configs
  path: ./cicd/crossplane/profiles/${CROSSPLANE_PROFILE:-cicd-platform}/provider-configs
  postBuild:
    substitute:
      CROSSPLANE_NAMESPACE: "crossplane-system"
```

The selection lives in the profile rather than in `spec.components` on the Flux
Kustomization so that one path means one thing: `hack/check-shared-path-wiring.py`
and `hack/check-passthrough-defaults.py` both key on `spec.path`, and a single
path rendered three different ways is exactly the drift they exist to catch.

`dependsOn` names the **configs** Kustomization, not the install one: on a
machinery cluster the providers arrive through the Configurations, so being
behind the chart is not enough.

`CROSSPLANE_NAMESPACE` is read only by the opentofu component (its state Secret
lands there). Threading it is harmless for the other two.
