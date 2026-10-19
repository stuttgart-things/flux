# stuttgart-things/flux/cicd/tekton

Deploys the [Tekton Operator](https://tekton.dev/docs/operator/) v0.81.2 via vendored manifests + TektonConfig CR.

## Components

| Component | Description |
|---|---|
| `components/operator` | Tekton Operator (CRDs, RBAC, Deployments, ConfigMaps) |
| `components/config` | TektonConfig CR (controls which Tekton sub-components get installed) |
| `components/dashboard-httproute` | Gateway API HTTPRoute for Tekton Dashboard |
| `components/ci-namespace` | Opt-in: CI namespace annotated so the pruner skips it (see Caveat below) |

## Requirements

<details><summary>ADD GITREPOSITORY</summary>

```bash
kubectl apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-apps
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  url: https://github.com/stuttgart-things/flux.git
EOF
```

</details>

## Kustomization

```bash
kubectl apply -f - <<EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: tekton
  namespace: flux-system
spec:
  interval: 1h
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-apps
  path: ./cicd/tekton
  prune: true
  wait: true
  postBuild:
    substitute:
      TEKTON_TARGET_NAMESPACE: tekton-pipelines
      TEKTON_PROFILE: all
      TEKTON_ENABLE_API_FIELDS: beta
      TEKTON_DISABLE_INLINE_SPEC: ""
      TEKTON_PRUNER_DISABLED: "false"
      TEKTON_PRUNER_SCHEDULE: "0 8 * * *"
      TEKTON_PRUNER_KEEP_SINCE: "1440"
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator
      namespace: tekton-operator
    - apiVersion: apps/v1
      kind: Deployment
      name: tekton-operator-webhook
      namespace: tekton-operator
EOF
```

## TektonConfig Parameters

| Variable | Default | Description |
|---|---|---|
| `TEKTON_TARGET_NAMESPACE` | `tekton-pipelines` | Namespace for Tekton Pipelines components |
| `TEKTON_PROFILE` | `all` | Install profile: `all`, `basic`, or `lite` |
| `TEKTON_ENABLE_API_FIELDS` | `beta` | API fields stability level: `stable`, `beta`, `alpha` |
| `TEKTON_DISABLE_INLINE_SPEC` | `""` | Disable inline spec for: `pipeline`, `pipelinerun`, `taskrun` (comma-separated) |
| `TEKTON_PRUNER_DISABLED` | `false` | Disable automatic pruning of old runs |
| `TEKTON_PRUNER_SCHEDULE` | `0 8 * * *` | Cron schedule for pruner |
| `TEKTON_PRUNER_KEEP_SINCE` | `1440` | Keep runs newer than N minutes (mutually exclusive with `keep`) |

## Updating the Operator

To update to a new version, re-vendor the upstream Kubernetes `release.yaml`
(not `openshift-release.yaml`) with the script, then review the diff:

```bash
hack/vendor-tekton-operator.py v0.81.2
git diff --stat cicd/tekton/components/operator
```

The script downloads
`https://infra.tekton.dev/tekton-releases/operator/previous/<VERSION>/release.yaml`,
splits it by kind into `components/operator/` (one `crd-<plural>.yaml` per CRD)
and rewrites that directory's `kustomization.yaml`. Keep the directory flat:
the Argo CD catalog (`stuttgart-things/argocd` `cicd/tekton/operator`) reads it
as a `directory:` source with `recurse: false`, pinned to a flux tag -- move that
pin after the release that carries the re-vendor.

Then update the version in `components/operator/README.md` and here, and read
the operator release notes between the old and new version for changes to the
`TektonConfig` fields in `components/config/tekton-config.yaml`.

### Upgrade notes v0.79.0 -> v0.81.2

Bundled components move: Pipeline v1.10.0 -> v1.15.3, Triggers v0.35.0 -> v0.37.1,
Dashboard v0.66.0 -> v0.71.0, Chains v0.26.2 -> v0.29.7, Results v0.18.0 -> v0.20.0,
Pruner v0.3.5 -> v0.4.3. The Dashboard Service (`tekton-dashboard:9097`) is
unchanged, so `components/dashboard-httproute` needs no change.

- **CRDs now carry full OpenAPI schemas.** Up to v0.79 every CRD was
  `x-kubernetes-preserve-unknown-fields: true`; now a misspelled or unknown
  `TektonConfig` field is pruned by the API server instead of being kept. Every
  field in `components/config/tekton-config.yaml` exists in the v0.81.2 schema
  with the type the substitutions produce (`pruner.disabled` bool,
  `pruner.keep-since` int, `pipeline.*` strings, `result.disabled` bool).
- **`TektonHub` is gone** (CRD and reconciler). The CRD is no longer vendored, so
  `prune: true` deletes it -- and any `TektonHub` objects with it.
- **Pipelines-as-Code is installed by default on Kubernetes with `profile: all`.**
  New in v0.80: the operator's defaulting webhook sets
  `spec.platforms.kubernetes.pipelinesAsCode.enable: true` when the field is
  absent, and the operator then installs the PAC controller, watcher and webhook
  into the target namespace (new CRD `openshiftpipelinesascodes`). To keep it
  off, set `platforms.kubernetes.pipelinesAsCode.enable: false` in the
  TektonConfig -- but only once the cluster runs v0.81: the v0.79 webhook rejects
  `spec.platforms.kubernetes` as an unknown field, and since `./cicd/tekton`
  applies operator and TektonConfig together, shipping both in one change would
  fail the dry-run before the operator could be upgraded.
- **Operator-managed NetworkPolicies, on by default.** Pipelines, Triggers,
  Chains, Results, Pruner and the proxy-webhook get default-deny plus allow
  policies in the target namespace. Egress stays open (the "API server" rule is
  allow-all), webhooks accept ingress from anywhere, but **metrics ingress is
  allowed only from the namespace named `monitoring`** -- a Prometheus elsewhere
  stops scraping these pods. Opt out with `spec.networkPolicy.disabled: true`
  on the TektonConfig (propagated to every component; override single
  policies by name with `spec.networkPolicy.policies`). Like the PAC switch,
  that field is unknown to the v0.79 webhook -- set it only after the upgrade.
- **Operator metrics moved to OpenTelemetry** (`kn_workqueue_*` instead of
  `tekton_operator_lifecycle_*`); `tekton-config-observability` only ships an
  `_example` here, so nothing to migrate.

## Profiles

The TektonConfig `profile` controls which components the operator installs:

| Profile | Components |
|---|---|
| `lite` | Pipelines only |
| `basic` | Pipelines + Triggers |
| `all` | Pipelines + Triggers + Dashboard |

## Caveat: `profile: all` is not "everything you want"

`all` installs Tekton **Results**, and Results brings a PostgreSQL StatefulSet.
Two things follow, both seen on u26-rke2-1 on 2026-08-17:

1. A cluster that only runs PipelineRuns gets a database nobody asked for.
2. On a cluster with **no default StorageClass** the PVC stays `Pending`, the
   operator blocks on Results, and nothing after it installs — including the
   Dashboard, which is usually the reason `all` was chosen in the first place.

The symptom is quiet: `TektonConfig` reports
`Components not in ready state`, `TektonPipeline` and `TektonTrigger` are both
`Ready=True`, and the Dashboard CR simply never appears.

Results is therefore **disabled by default** (`TEKTON_RESULT_DISABLED`, default
`true`) rather than dropping the profile to `basic` — `basic` also drops the
Dashboard. Set it to `false` on a cluster that has a default StorageClass and
wants a run archive.

## `enable-api-fields` defaults to `beta`, and why that reversed

**`stable` breaks every AnsibleRun in this fleet.** Their pipelines are resolved
through a git resolver, and resolver params are gated behind alpha/beta, so the
admission webhook refuses the PipelineRun outright:

```
resolver params requires "enable-api-fields" feature gate to be "alpha" or "beta" but it is "stable"
```

Measured on `u26-rke2-1` (2026-08-17): the `AnsibleRun`'s Crossplane Object sat
at `ReconcileError` and **no PipelineRun was ever created**, so the symptom is a
VM stuck before provisioning, not something that looks like a Tekton problem.

### The reason it used to default to `stable`

The operator propagates this value from `TektonConfig` to every component, and
**Triggers accepts only `stable` or `alpha`**. An earlier attempt at `beta` left
the operator requeueing forever:

```
TektonConfig   Components not in ready state: TektonTrigger: reconcile again and proceed
TektonTrigger  Ready=True   (all sub-conditions True, all three pods Running)
```

That did **not** reproduce on operator **v0.79.0** (not re-measured on v0.81.2). After switching a live
cluster to `beta`: `TektonConfig` reported `beta`, `TektonTrigger` kept
`stable`, every component stayed `Ready`, and the operator logged zero requeue
messages.

So the trade is no longer "beta risks a stuck operator" but "stable guarantees
no AnsibleRun runs". If the loop returns on some operator version, set
`TEKTON_ENABLE_API_FIELDS=alpha` — going back to `stable` takes the resolvers
with it. A cluster that genuinely needs Triggers out of the picture can use
`profile: basic`.

## Caveat: Pruner + Crossplane-managed PipelineRuns

The operator's pruner is a single cluster-wide CronJob (`tekton-pipelines/tekton-resource-pruner-*`) built from `TektonConfig.spec.pruner`. It iterates every namespace containing TaskRuns/PipelineRuns and deletes anything older than `keep-since`.

This causes a **daily re-trigger loop** when PipelineRuns are managed by Crossplane's `provider-kubernetes` (e.g. via the `AnsibleRun` / `VMProvision` XRs rendered from `stage-time`):

1. Pruner fires at `TEKTON_PRUNER_SCHEDULE` (default `0 8 * * *`) and deletes PipelineRuns in `tekton-ci` older than `TEKTON_PRUNER_KEEP_SINCE` minutes.
2. The Crossplane `Object` wrapping each PipelineRun has `managementPolicies: ["*"]`, so its next reconcile recreates the missing PipelineRun.
3. A fresh run appears a few minutes after 08:00 UTC every day — the runs visible in the dashboard are not user-triggered.

### Mitigations

- **Skip a namespace cluster-wide**: annotate the namespace so the operator's pruner ignores it (leaves global pruning intact). Enable the opt-in `components/ci-namespace` component in `kustomization.yaml` — it manages the namespace with the required annotation:
  ```yaml
  components:
    - components/operator
    - components/config
    - components/ci-namespace
  ```
  Override the name with `TEKTON_CI_NAMESPACE` via Flux `postBuild.substitute`.
- **Increase retention**: raise `TEKTON_PRUNER_KEEP_SINCE` (e.g. `10080` = 7d) to reduce how often the loop fires.
- **Disable the pruner**: set `TEKTON_PRUNER_DISABLED: "true"` (loses pruning everywhere).
- **Detach the Crossplane Object**: set `managementPolicies: ["Observe"]` on the rendered `Object`s so deletions aren't reverted.

The namespace-skip annotation is the cleanest fix when Crossplane-managed PipelineRuns should live until their parent XR is deleted.
